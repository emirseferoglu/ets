"""
merge_erank.py — Adım 4: eRank export'larını kendi tag envanterimle birleştir.

Girdi:
  data/erank/*.csv   — iki tür dosya otomatik algılanır:
     (a) Keyword Tool export'u  → keyword metrikleri (hacim, rekabet, KD, char)
     (b) Shop listings export'u → rakip mağazanın ilanları (tags, satış, view)
  data/listings.json — kendi ilanlarım (fetch_listings.py çıktısı)

Çıktı:
  reports/keyword_gaps.md        — okunabilir rapor (3 kova + başlık adayları)
  data/opportunity_keywords.csv  — FIRSAT kovası, aksiyon alınabilir tablo

Kovalar:
  KALDIR : kullandığım, düşük hacim + yüksek rekabet
  FIRSAT : iyi hacim, düşük rekabet, hiç kullanmadığım (eRank + rakip açığı)
  KORU   : kullandığım ve iyi performans gösteren
20 karakteri aşan keyword'ler "tag'e sığmaz → başlık adayı" olarak işaretlenir.

Salt-okunur: yalnızca lokal dosyaları okur, API çağrısı yok.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent
ERANK_DIR = ROOT / "data" / "erank"
LISTINGS_JSON = ROOT / "data" / "listings.json"
REPORT_PATH = ROOT / "reports" / "keyword_gaps.md"
OPP_CSV = ROOT / "data" / "opportunity_keywords.csv"

# --- eşikler (ayarlanabilir) ---
VOLUME_GOOD = 100    # aylık arama >= → iyi hacim
VOLUME_LOW = 50      # aylık arama <  → düşük hacim
KD_LOW = 40          # KD <= → düşük rekabet
KD_HIGH = 70         # KD >= → yüksek rekabet
TAG_CHAR_LIMIT = 20  # > → tag'e sığmaz, başlık adayı
COMP_MIN_LISTINGS = 4  # rakip açığında: en az kaç rakip ilanında geçsin

# --- esnek kolon eşleme (normalize edilmiş başlık → alan) ---
KEYWORD_SYNONYMS = {
    "keyword": {"keywords", "keyword", "tag", "tags"},
    "avg_searches": {"average searches", "avg searches", "searches", "etsy searches"},
    "avg_clicks": {"average clicks", "avg clicks", "clicks"},
    "competition": {"competition", "etsy competition"},
    "kd": {"kd", "keyword difficulty", "difficulty"},
    "char_count": {"character count", "char count", "characters", "character"},
    "ctr": {"ctr"},
    "google_searches": {"google searches"},
}
SHOP_SYNONYMS = {
    "title": {"listing", "title"},
    "tags": {"tags"},
    "listing_id": {"listing id", "listing_id"},
    "views": {"total views", "views"},
    "favorites": {"favorites", "favorers", "favourites"},
    "sales": {"est. sales", "estimated sales", "sales", "est sales"},
    "revenue": {"est. revenue", "estimated revenue", "revenue", "est revenue"},
    "price": {"price"},
    "age": {"listing age", "age"},
    "daily_views": {"daily views"},
}


def _norm(s: str) -> str:
    return s.strip().lower()


def _nospace(s: str) -> str:
    """Marka eşleştirmesi için: küçük harf + boşluksuz ('antique white art'→'antiquewhiteart')."""
    return re.sub(r"\s+", "", s.strip().lower())


def _num(val: Any) -> float | None:
    """'6,156' / '€1,203.79' / '100' / 'N/A' → float | None."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.upper() in {"N/A", "NA", "-"}:
        return None
    s = re.sub(r"[^\d.\-]", "", s)  # para/virgül/boşluk temizle
    if s in {"", "-", ".", "-."}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _map_columns(header: list[str], synonyms: dict[str, set[str]]) -> dict[str, str]:
    """Normalize başlıklara göre {alan: gerçek_kolon_adı} eşlemesi."""
    mapping: dict[str, str] = {}
    for col in header:
        key = _norm(col)
        for field, names in synonyms.items():
            if key in names and field not in mapping:
                mapping[field] = col
    return mapping


def detect_and_read(path: Path) -> tuple[str, list[dict[str, str]], dict[str, str]]:
    """
    Dosya türünü kolonlarından algıla.
    Döner: (kind, rows, mapping)  kind ∈ {'keywords','shop','unknown'}
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return "unknown", [], {}
    header = list(rows[0].keys())

    shop_map = _map_columns(header, SHOP_SYNONYMS)
    kw_map = _map_columns(header, KEYWORD_SYNONYMS)

    # Shop listings: tags + title birlikte varsa.
    if "tags" in shop_map and "title" in shop_map:
        return "shop", rows, shop_map
    # Keyword tool: keyword + en az bir metrik.
    if "keyword" in kw_map and (
        "avg_searches" in kw_map or "kd" in kw_map or "competition" in kw_map
    ):
        return "keywords", rows, kw_map
    return "unknown", rows, {header[i]: header[i] for i in range(len(header))}


# ------------------------------------------------------------------ aggregate
def load_my_tags() -> tuple[set[str], Counter]:
    if not LISTINGS_JSON.exists():
        raise SystemExit(
            f"{LISTINGS_JSON.relative_to(ROOT)} yok. Önce: python fetch_listings.py"
        )
    data = json.loads(LISTINGS_JSON.read_text())
    freq: Counter = Counter()
    for rec in data:
        freq.update({_norm(t) for t in (rec.get("tags") or [])})
    return set(freq), freq


def read_all() -> tuple[dict[str, dict], dict[str, dict], set[str], list[str]]:
    """
    data/erank/*.csv oku.
    Döner: (keyword_metrics, competitor_tags, brands, unknown_files)
      keyword_metrics[normkw] = {keyword, avg_searches, competition, kd, char_count,...}
      competitor_tags[normtag] = {tag, listings, est_sales, est_views}
      brands = rakip mağaza adları (boşluksuz normalize) — marka tag'lerini elemek için
    """
    keyword_metrics: dict[str, dict] = {}
    comp_tags: dict[str, dict] = defaultdict(
        lambda: {"tag": "", "listings": 0, "est_sales": 0.0, "est_views": 0.0}
    )
    brands: set[str] = set()
    unknown: list[str] = []

    files = sorted(ERANK_DIR.glob("*.csv"))
    for path in files:
        kind, rows, m = detect_and_read(path)
        if kind == "keywords":
            for r in rows:
                kw = (r.get(m["keyword"], "") or "").strip()
                if not kw:
                    continue
                nk = _norm(kw)
                char_count = _num(r.get(m.get("char_count", ""), "")) if "char_count" in m else None
                entry = {
                    "keyword": kw,
                    "avg_searches": _num(r.get(m.get("avg_searches", ""))),
                    "competition": _num(r.get(m.get("competition", ""))),
                    "kd": _num(r.get(m.get("kd", ""))),
                    "char_count": int(char_count) if char_count is not None else len(kw),
                }
                # Aynı keyword birden çok dosyada → en yüksek hacimliyi tut.
                old = keyword_metrics.get(nk)
                if not old or (entry["avg_searches"] or 0) > (old["avg_searches"] or 0):
                    keyword_metrics[nk] = entry
        elif kind == "shop":
            # Dosya adından rakip markasını çıkar ('AntiqueWhiteArt - Shop...').
            brands.add(_nospace(path.stem.split(" - ")[0]))
            for r in rows:
                raw_tags = r.get(m["tags"], "") or ""
                tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                sales = _num(r.get(m.get("sales", ""))) or 0.0
                views = _num(r.get(m.get("views", ""))) or 0.0
                for t in tags:
                    nt = _norm(t)
                    e = comp_tags[nt]
                    e["tag"] = e["tag"] or t
                    e["listings"] += 1
                    e["est_sales"] += sales
                    e["est_views"] += views
        else:
            unknown.append(path.name)

    return keyword_metrics, dict(comp_tags), brands, unknown


# -------------------------------------------------------------------- buckets
def _is_brand(nt: str, brands: set[str]) -> bool:
    """Tag, rakip mağaza markasıysa (boşluksuz eşleşme) True."""
    return _nospace(nt) in brands


def build_buckets(
    my_tags: set[str],
    my_freq: Counter,
    kw: dict[str, dict],
    comp: dict[str, dict],
    brands: set[str],
) -> dict[str, list[dict]]:
    remove, keep, firsat, comp_gap, title_cands = [], [], [], [], []

    # --- KALDIR / KORU: kendi tag'lerim, eRank verisiyle ---
    for nt in my_tags:
        m = kw.get(nt)
        if not m:
            continue  # eRank verisi yok → sınıflandırma dışı
        vol, kd = m["avg_searches"], m["kd"]
        row = {
            "keyword": m["keyword"], "avg_searches": vol,
            "competition": m["competition"], "kd": kd,
            "char_count": m["char_count"], "my_listings": my_freq[nt],
        }
        if vol is not None and vol < VOLUME_LOW and kd is not None and kd >= KD_HIGH:
            remove.append(row)
        elif vol is not None and vol >= VOLUME_GOOD:
            keep.append(row)  # kullandığım + iyi hacim = çekirdek, koru

    # --- FIRSAT (kesin): eRank iyi hacim + DÜŞÜK KD + kullanmadığım ---
    for nk, m in kw.items():
        if nk in my_tags:
            continue
        vol, kd = m["avg_searches"], m["kd"]
        if vol is not None and vol >= VOLUME_GOOD and kd is not None and kd <= KD_LOW:
            c = comp.get(nk)
            firsat.append({
                "keyword": m["keyword"], "bucket": "FIRSAT",
                "avg_searches": vol, "competition": m["competition"], "kd": kd,
                "char_count": m["char_count"],
                "is_title_candidate": m["char_count"] > TAG_CHAR_LIMIT,
                "competitor_listings": c["listings"] if c else 0,
                "competitor_est_sales": round(c["est_sales"], 1) if c else 0.0,
            })

    # --- RAKİP AÇIĞI: rakibin satan tag'leri, kullanmadığım, marka değil ---
    for nt, c in comp.items():
        if nt in my_tags or _is_brand(nt, brands):
            continue
        if c["listings"] < COMP_MIN_LISTINGS:
            continue
        m = kw.get(nt)
        comp_gap.append({
            "keyword": c["tag"], "bucket": "RAKIP",
            "avg_searches": m["avg_searches"] if m else None,
            "competition": m["competition"] if m else None,
            "kd": m["kd"] if m else None,
            "char_count": len(c["tag"]),
            "is_title_candidate": len(c["tag"]) > TAG_CHAR_LIMIT,
            "competitor_listings": c["listings"],
            "competitor_est_sales": round(c["est_sales"], 1),
        })

    # --- BAŞLIK ADAYLARI: 20+ karakter eRank keyword'leri, kullanmadığım ---
    for nk, m in kw.items():
        if nk in my_tags or m["char_count"] <= TAG_CHAR_LIMIT:
            continue
        vol = m["avg_searches"]
        if vol is not None and vol >= VOLUME_LOW:
            c = comp.get(nk)
            title_cands.append({
                "keyword": m["keyword"], "char_count": m["char_count"],
                "avg_searches": vol, "kd": m["kd"],
                "competitor_est_sales": round(c["est_sales"], 1) if c else 0.0,
            })

    remove.sort(key=lambda r: (r["avg_searches"] or 0))
    keep.sort(key=lambda r: -(r["avg_searches"] or 0))
    firsat.sort(key=lambda r: -(r["avg_searches"] or 0))
    comp_gap.sort(key=lambda r: -(r["competitor_est_sales"] or 0))
    title_cands.sort(key=lambda r: -(r["avg_searches"] or 0))
    return {
        "remove": remove, "keep": keep, "firsat": firsat,
        "comp_gap": comp_gap, "title_cands": title_cands,
    }


# --------------------------------------------------------------------- report
def build_report(
    buckets: dict[str, list[dict]],
    kw: dict[str, dict],
    comp: dict[str, dict],
    my_tags: set[str],
    brands: set[str],
    files_summary: list[str],
    unknown: list[str],
) -> str:
    L: list[str] = []
    w = L.append
    remove, keep = buckets["remove"], buckets["keep"]
    firsat, comp_gap, title_cands = (
        buckets["firsat"], buckets["comp_gap"], buckets["title_cands"]
    )

    w("# Keyword Gap Raporu — Lumiaerestudio")
    w("")
    w(f"*Kaynaklar: {', '.join(files_summary)}*")
    w("")
    w("## Özet")
    w("")
    w(f"- eRank keyword: **{len(kw)}** · rakip tag: **{len(comp)}** · "
      f"kendi benzersiz tag'im: **{len(my_tags)}**")
    w(f"- 🟢 KORU: **{len(keep)}** · 🔴 KALDIR: **{len(remove)}** · "
      f"🎯 FIRSAT (eRank): **{len(firsat)}** · 🔍 RAKİP AÇIĞI: **{len(comp_gap)}**")
    w(f"- 📝 Başlık adayı (20+ karakter): **{len(title_cands)}**")
    w("")
    w(f"*Eşikler: iyi hacim ≥{VOLUME_GOOD}, düşük hacim <{VOLUME_LOW}, "
      f"düşük rekabet KD≤{KD_LOW}, yüksek rekabet KD≥{KD_HIGH}.*")
    if brands:
        w(f"*Rakip marka tag'leri elendi: {', '.join(sorted(brands))}.*")
    if unknown:
        w("")
        w(f"> ⚠️ Tanınmayan dosya(lar): {', '.join(unknown)} — kolon eşlemesi "
          "kurulamadı, atlandı. Kolon başlıklarını paylaş, eşleme ekleyeyim.")
    w("")

    def table(rows: list[dict], cols: list[tuple[str, str]], limit: int | None = None):
        w("| " + " | ".join(h for h, _ in cols) + " |")
        w("|" + "|".join("---" for _ in cols) + "|")
        for r in (rows[:limit] if limit else rows):
            cells = []
            for _, key in cols:
                v = r.get(key)
                if key == "is_title_candidate":
                    v = "📝" if v else ""
                elif v is None:
                    v = "—"
                elif isinstance(v, float):
                    v = f"{v:.0f}"
                cells.append(str(v))
            w("| " + " | ".join(cells) + " |")

    w("## 🎯 FIRSAT — iyi hacim + DÜŞÜK rekabet, kullanmadığım (eRank)")
    w("")
    w(f"*Aylık arama ≥{VOLUME_GOOD} ve KD ≤{KD_LOW}. En güvenli kazanımlar — "
      "doğrudan tag/başlık olarak eklemeyi düşün. 📝 = 20+ karakter (başlıkta kullan).*")
    w("")
    if firsat:
        table(firsat, [
            ("keyword", "keyword"), ("arama", "avg_searches"), ("KD", "kd"),
            ("rekabet", "competition"), ("kar.", "char_count"),
            ("📝", "is_title_candidate"), ("rakip satış", "competitor_est_sales"),
        ], limit=50)
        if len(firsat) > 50:
            w("")
            w(f"*(+{len(firsat) - 50} fırsat daha → `data/opportunity_keywords.csv`)*")
    else:
        w("Eşikleri geçen düşük-rekabet fırsatı yok (KD_LOW'u yükseltmeyi düşün).")
    w("")

    w("## 🔍 RAKİP AÇIĞI — AntiqueWhiteArt'ın satan ama bende olmayan tag'leri")
    w("")
    w(f"*Rakibin ≥{COMP_MIN_LISTINGS} ilanında geçen, satış-kanıtlı tag'ler "
      "(rakip tahmini satışa göre sıralı). Talep kanıtı güçlü, ama rekabeti "
      "değişken — KD sütununa bak.*")
    w("")
    if comp_gap:
        table(comp_gap, [
            ("keyword", "keyword"), ("rakip ilan", "competitor_listings"),
            ("rakip satış", "competitor_est_sales"), ("arama", "avg_searches"),
            ("KD", "kd"),
        ], limit=40)
        if len(comp_gap) > 40:
            w("")
            w(f"*(+{len(comp_gap) - 40} tag daha → `data/opportunity_keywords.csv`)*")
    else:
        w("Rakip açığı bulunamadı.")
    w("")

    w("## 🔴 KALDIR — kullandığım, düşük hacim + yüksek rekabet")
    w("")
    w(f"*Aylık arama <{VOLUME_LOW} ve KD ≥{KD_HIGH}. Yer kaplıyor ama getirisi "
      "düşük — güçlü keyword'lerle değiştir.*")
    w("")
    if remove:
        table(remove, [
            ("keyword", "keyword"), ("arama", "avg_searches"), ("KD", "kd"),
            ("rekabet", "competition"), ("kaç ilanımda", "my_listings"),
        ])
    else:
        w("Bu eşikte kaldırılacak tag yok. 👍")
    w("")

    w("## 🟢 KORU — kullandığım ve iyi hacimli çekirdek keyword'ler")
    w("")
    w(f"*Kullandığım + aylık arama ≥{VOLUME_GOOD}. KD yüksek olsa da koru "
      "(kategorinin bel kemiği).*")
    w("")
    if keep:
        table(keep, [
            ("keyword", "keyword"), ("arama", "avg_searches"), ("KD", "kd"),
            ("rekabet", "competition"), ("kaç ilanımda", "my_listings"),
        ])
    else:
        w("Eşiği geçen güçlü tag bulunamadı.")
    w("")

    w(f"## 📝 Başlık adayları — 20+ karakter ({len(title_cands)})")
    w("")
    w("*Tag alanına (20 kr) sığmayan ama aramada hacimli keyword'ler — "
      "başlıklarda kullan.*")
    w("")
    if title_cands:
        table(title_cands, [
            ("keyword", "keyword"), ("kar.", "char_count"),
            ("arama", "avg_searches"), ("KD", "kd"),
            ("rakip satış", "competitor_est_sales"),
        ], limit=40)
    else:
        w("20+ karakterlik hacimli keyword yok.")
    w("")

    w("---")
    w("")
    w("> Eşikler `merge_erank.py` başındaki sabitlerden ayarlanabilir "
      f"(VOLUME_GOOD={VOLUME_GOOD}, KD_LOW={KD_LOW}, KD_HIGH={KD_HIGH}...). "
      "eRank rakamları tahmindir; kararları görsel/sezon/fiyatla birlikte ver.")
    w("")
    return "\n".join(L)


def main() -> None:
    if not ERANK_DIR.exists() or not list(ERANK_DIR.glob("*.csv")):
        raise SystemExit(
            f"{ERANK_DIR.relative_to(ROOT)} içinde CSV yok. "
            "eRank export'larını oraya koy."
        )
    my_tags, my_freq = load_my_tags()
    kw, comp, brands, unknown = read_all()

    files_summary = [p.name for p in sorted(ERANK_DIR.glob("*.csv"))]
    buckets = build_buckets(my_tags, my_freq, kw, comp, brands)

    report = build_report(buckets, kw, comp, my_tags, brands, files_summary, unknown)
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(report)

    # FIRSAT + RAKİP AÇIĞI kovalarını tek CSV'ye yaz (bucket sütunuyla).
    opp_cols = [
        "keyword", "bucket", "avg_searches", "kd", "competition",
        "char_count", "is_title_candidate",
        "competitor_listings", "competitor_est_sales",
    ]
    combined = buckets["firsat"] + buckets["comp_gap"]
    pd.DataFrame(combined, columns=opp_cols).to_csv(OPP_CSV, index=False)

    print(f"Rapor yazıldı: {REPORT_PATH.relative_to(ROOT)}")
    print(f"CSV yazıldı  : {OPP_CSV.relative_to(ROOT)}")
    print(f"  KORU: {len(buckets['keep'])} · KALDIR: {len(buckets['remove'])} · "
          f"FIRSAT: {len(buckets['firsat'])} · RAKİP AÇIĞI: {len(buckets['comp_gap'])}")
    if brands:
        print(f"  elenen marka: {', '.join(sorted(brands))}")
    if unknown:
        print(f"  ⚠️ tanınmayan dosya: {', '.join(unknown)}")


if __name__ == "__main__":
    main()
