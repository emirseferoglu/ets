"""
action_plan.py — Adım 5: analiz bulgularını ilan-bazlı aksiyon planına çevir.

Girdi (hepsi lokal, API yok):
  data/listings.json          — kendi ilanlarım
  data/erank/*.csv            — eRank + rakip verisi (merge_erank mantığı yeniden kullanılır)

Her ilan için üretir:
  * ÇIKAR : ilandaki KALDIR tag'leri (düşük hacim + yüksek rekabet)
  * EKLE  : ilana tematik uyan, kullanılmayan FIRSAT/RAKİP tag'leri (boş slotları doldurur)
  * BAŞLIK: 20+ karakterlik, tag'e sığmayan ama uyumlu keyword önerileri

Çıktı:
  reports/action_plan.md      — öncelikli ilanlar detaylı + özet
  data/action_plan.csv        — tüm öneriler, makine-okunur (listing_id başına satırlar)

Eşleme: ilanın başlık+tag'lerinden "ayırt edici" kelimeler çıkarılır (kategori
geneli kelimeler — frame, tv, art, digital... — elenir), fırsat keyword'leriyle
kelime örtüşmesine göre tematik öneri yapılır.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from merge_erank import (
    ERANK_DIR,
    LISTINGS_JSON,
    TAG_CHAR_LIMIT,
    _norm,
    build_buckets,
    load_my_tags,
    read_all,
)

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "reports" / "action_plan.md"
CSV_PATH = ROOT / "data" / "action_plan.csv"

MAX_TAGS = 13
SHOW_DETAILED = 30  # markdown'da kaç ilan detaylı gösterilsin (gerisi CSV'de)
MAX_TITLE_SUGGEST = 4

# Eşleşmede işe yaramayan, kategori geneli kelimeler (ayırt edici değil).
STOP = {
    "frame", "tv", "art", "artwork", "samsung", "digital", "download",
    "downloadable", "print", "printable", "prints", "wall", "decor", "home",
    "4k", "screensaver", "instant", "the", "for", "and", "with", "of", "to",
    "a", "an", "in", "on", "set", "poster", "hd", "uhd", "tvs", "screen",
    "file", "files", "jpg", "png", "image", "images", "download.",
}


def tokens(text: str) -> set[str]:
    """Ayırt edici kelime kümesi: küçük harf, 3+ harf, stopword'süz."""
    raw = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in raw if len(t) >= 3 and t not in STOP}


def load_opportunities(buckets: dict[str, list[dict]]) -> list[dict]:
    """FIRSAT + RAKİP AÇIĞI kovalarını tek eşleştirilebilir listeye çevir."""
    opps: list[dict] = []
    for row in buckets["firsat"] + buckets["comp_gap"]:
        kw = row["keyword"]
        opps.append({
            "keyword": kw,
            "norm": _norm(kw),
            "tokens": tokens(kw),
            "char_count": row.get("char_count") or len(kw),
            "reason": row["bucket"],
            "avg_searches": row.get("avg_searches"),
            "kd": row.get("kd"),
            "competitor_est_sales": row.get("competitor_est_sales") or 0.0,
            # Sıralama değeri: arama hacmi + rakip satış (kaba ama iş görür).
            "value": (row.get("avg_searches") or 0) + (row.get("competitor_est_sales") or 0),
        })
    return opps


def match_for_listing(
    listing: dict[str, Any],
    kaldir: set[str],
    opps: list[dict],
) -> dict[str, list]:
    """Bir ilan için çıkar/ekle/başlık önerilerini üret."""
    tags = listing.get("tags") or []
    tag_norms = {_norm(t) for t in tags}
    title = listing.get("title") or ""
    theme = tokens(title + " " + " ".join(tags))

    # ÇIKAR: ilandaki KALDIR tag'leri.
    removals = [t for t in tags if _norm(t) in kaldir]

    # Çıkarımlardan sonra boşalacak slot sayısı.
    after_remove = len(tags) - len(removals)
    free_slots = max(0, MAX_TAGS - after_remove)

    # Aday öneriler: temaya değen, kullanılmayan fırsatlar.
    scored = []
    for o in opps:
        if o["norm"] in tag_norms:
            continue
        overlap = theme & o["tokens"]
        if not overlap:
            continue
        scored.append((len(overlap), o["value"], o))
    scored.sort(key=lambda x: (-x[0], -x[1]))

    tag_adds, title_adds = [], []
    for _, _, o in scored:
        if o["char_count"] > TAG_CHAR_LIMIT:
            if len(title_adds) < MAX_TITLE_SUGGEST:
                title_adds.append(o)
        elif len(tag_adds) < free_slots:
            tag_adds.append(o)
        if len(tag_adds) >= free_slots and len(title_adds) >= MAX_TITLE_SUGGEST:
            break

    return {"removals": removals, "tag_adds": tag_adds, "title_adds": title_adds,
            "free_slots": free_slots, "tag_count": len(tags)}


def main() -> None:
    if not LISTINGS_JSON.exists():
        raise SystemExit("data/listings.json yok. Önce: python fetch_listings.py")
    if not ERANK_DIR.exists() or not list(ERANK_DIR.glob("*.csv")):
        raise SystemExit("data/erank/*.csv yok. Önce eRank export'larını koy.")

    listings = json.loads(LISTINGS_JSON.read_text())
    my_tags, my_freq = load_my_tags()
    kw, comp, brands, _ = read_all()
    buckets = build_buckets(my_tags, my_freq, kw, comp, brands)
    kaldir = {_norm(r["keyword"]) for r in buckets["remove"]}
    opps = load_opportunities(buckets)

    plans = []
    for lst in listings:
        p = match_for_listing(lst, kaldir, opps)
        p["listing"] = lst
        p["action_count"] = len(p["removals"]) + len(p["tag_adds"]) + len(p["title_adds"])
        p["incomplete"] = p["tag_count"] < MAX_TAGS
        plans.append(p)

    # Öncelik: eksik tag'liler + en çok aksiyonu olanlar önce.
    plans.sort(key=lambda p: (not p["incomplete"], -p["action_count"]))

    # --- CSV (tüm öneriler) ---
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["listing_id", "url", "title", "action", "keyword",
                     "reason", "avg_searches", "kd", "competitor_est_sales"])
        for p in plans:
            lst = p["listing"]
            base = [lst["listing_id"], lst["url"], lst["title"]]
            for t in p["removals"]:
                wr.writerow(base + ["REMOVE_TAG", t, "KALDIR", "", "", ""])
            for o in p["tag_adds"]:
                wr.writerow(base + ["ADD_TAG", o["keyword"], o["reason"],
                                    o["avg_searches"] or "", o["kd"] or "",
                                    o["competitor_est_sales"] or ""])
            for o in p["title_adds"]:
                wr.writerow(base + ["ADD_TITLE", o["keyword"], o["reason"],
                                    o["avg_searches"] or "", o["kd"] or "",
                                    o["competitor_est_sales"] or ""])

    # --- Markdown (öncelikli ilanlar detaylı) ---
    total_removals = sum(len(p["removals"]) for p in plans)
    total_adds = sum(len(p["tag_adds"]) for p in plans)
    total_titles = sum(len(p["title_adds"]) for p in plans)
    incomplete_n = sum(1 for p in plans if p["incomplete"])

    L: list[str] = []
    w = L.append
    w("# Aksiyon Planı — Lumiaerestudio")
    w("")
    w("*İlan-bazlı tag/başlık önerileri. Kaynak: `data/listings.json` + "
      "`data/erank/*.csv`. Tam liste: `data/action_plan.csv`.*")
    w("")
    w("## Özet")
    w("")
    w(f"- İlan: **{len(plans)}** · 13 tag eksik: **{incomplete_n}**")
    w(f"- Toplam öneri: **{total_removals}** çıkar · **{total_adds}** tag ekle · "
      f"**{total_titles}** başlık keyword'ü")
    w(f"- Aşağıda en öncelikli **{min(SHOW_DETAILED, len(plans))}** ilan detaylı; "
      "gerisi CSV'de.")
    w("")
    w("> Öneriler tematik kelime örtüşmesine dayanır; eklemeden önce göz at. "
      "eRank rakamları tahmindir.")
    w("")

    for p in plans[:SHOW_DETAILED]:
        lst = p["listing"]
        flag = "⚠️ eksik" if p["incomplete"] else ""
        w(f"### [{lst['title'][:65]}]({lst['url']})")
        w("")
        w(f"`{lst['listing_id']}` · tag: **{p['tag_count']}/13** {flag} · "
          f"boş slot (çıkarım sonrası): {p['free_slots']}")
        w("")
        if p["removals"]:
            w(f"- 🔴 **Çıkar** ({len(p['removals'])}): "
              + ", ".join(f"`{t}`" for t in p["removals"]))
        if p["tag_adds"]:
            adds = ", ".join(
                f"`{o['keyword']}`"
                f"({o['reason'][:4]}"
                + (f",{int(o['avg_searches'])}ar" if o["avg_searches"] else "")
                + (f",sat{int(o['competitor_est_sales'])}" if o["competitor_est_sales"] else "")
                + ")"
                for o in p["tag_adds"]
            )
            w(f"- 🟢 **Ekle tag** ({len(p['tag_adds'])}): {adds}")
        if p["title_adds"]:
            w("- 📝 **Başlığa** (20+ kr): "
              + ", ".join(f"`{o['keyword']}`" for o in p["title_adds"]))
        if not (p["removals"] or p["tag_adds"] or p["title_adds"]):
            w("- ✅ Belirgin aksiyon yok (tag'ler dolu, tematik açık az).")
        w("")

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(L))

    print(f"Rapor yazıldı: {REPORT_PATH.relative_to(ROOT)}")
    print(f"CSV yazıldı  : {CSV_PATH.relative_to(ROOT)}")
    print(f"  {total_removals} çıkar · {total_adds} tag ekle · "
          f"{total_titles} başlık · {incomplete_n} eksik ilan")


if __name__ == "__main__":
    main()
