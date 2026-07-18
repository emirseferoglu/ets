"""
analyze_tags.py — Adım 3: tag envanteri ve performans analizi (lokal, API yok).

Girdi : data/listings.json  (fetch_listings.py çıktısı)
Çıktı : reports/tag_inventory.md  (okunabilir markdown rapor)

Analizler:
  * Tag frekans tablosu (hangi keyword kaç ilanda)
  * 13 tag'ini doldurmamış ilanlar
  * 140 karakterin altındaki başlıklar
  * "Yetim" tag'ler (sadece 1 ilanda geçen)
  * Performans sinyali: num_favorers / yaş(gün) → üst %20 vs alt %20 tag farkı
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "data" / "listings.json"
REPORT_PATH = ROOT / "reports" / "tag_inventory.md"
ORPHANS_PATH = ROOT / "reports" / "orphan_tags.txt"

# Rapor tablolarında gösterilecek maksimum satır (tam liste ayrı dosyada/CSV'de).
SHOW_SHORT_TITLES = 30
SHOW_ORPHANS = 80

MAX_TAGS = 13
TITLE_MIN = 140  # Etsy başlık üst sınırı ~140; altı = boşa giden alan.
TAG_CHAR_LIMIT = 20  # Etsy tag başına 20 karakter sınırı.


def _norm(tag: str) -> str:
    """Frekans için tag normalize: küçük harf + trim."""
    return tag.strip().lower()


def load() -> pd.DataFrame:
    if not JSON_PATH.exists():
        raise SystemExit(
            f"{JSON_PATH.relative_to(ROOT)} yok. Önce: python fetch_listings.py"
        )
    df = pd.DataFrame(json.loads(JSON_PATH.read_text()))
    now = time.time()
    # Gerçek yaş: original_creation_timestamp (auto-renew'de sıfırlanmaz).
    age_days = (now - df["original_creation_timestamp"]) / 86400.0
    df["age_days"] = age_days.clip(lower=1.0)  # <1 gün → 1 (bölme güvenliği)
    df["fav_per_day"] = df["num_favorers"] / df["age_days"]
    df["fav_per_100view"] = df.apply(
        lambda r: (r["num_favorers"] / r["views"] * 100) if r["views"] else 0.0,
        axis=1,
    )
    return df


def tag_frequency(df: pd.DataFrame) -> Counter:
    """Her tag kaç FARKLI ilanda geçiyor (normalize edilmiş)."""
    counter: Counter = Counter()
    for tags in df["tags"]:
        seen = {_norm(t) for t in tags}
        counter.update(seen)
    return counter


def build_report(df: pd.DataFrame) -> str:
    n = len(df)
    freq = tag_frequency(df)
    total_unique = len(freq)

    # --- kovalar ---
    incomplete = df[df["tag_count"] < MAX_TAGS].sort_values("tag_count")
    short_titles = df[df["title_length"] < TITLE_MIN].sort_values("title_length")
    orphans = sorted([t for t, c in freq.items() if c == 1])

    # --- performans: üst/alt %20 ---
    ranked = df.sort_values("fav_per_day", ascending=False).reset_index(drop=True)
    k = max(1, int(round(n * 0.20)))
    top = ranked.head(k)
    bottom = ranked.tail(k)
    top_tags = tag_frequency(top)
    bottom_tags = tag_frequency(bottom)

    # Üstte fazla, altta az geçen tag'ler (fırsat sinyali) ve tersi.
    def rate(counter: Counter, tag: str, size: int) -> float:
        return counter.get(tag, 0) / size

    all_perf_tags = set(top_tags) | set(bottom_tags)
    diffs = []
    for t in all_perf_tags:
        tr, br = rate(top_tags, t, k), rate(bottom_tags, t, k)
        diffs.append((t, tr - br, top_tags.get(t, 0), bottom_tags.get(t, 0)))
    winners = sorted(diffs, key=lambda x: x[1], reverse=True)[:15]
    losers = sorted(diffs, key=lambda x: x[1])[:15]

    # ---------------------------------------------------------------- markdown
    L: list[str] = []
    w = L.append
    w("# Tag Envanteri & Performans Raporu — Lumiaerestudio")
    w("")
    w(f"*Otomatik üretildi · {time.strftime('%Y-%m-%d %H:%M')} · kaynak: "
      f"`data/listings.json` ({n} aktif ilan)*")
    w("")

    w("## Özet")
    w("")
    w(f"- Aktif ilan: **{n}**")
    w(f"- Benzersiz tag (normalize): **{total_unique}**")
    w(f"- 13 tag'i **dolu** ilan: **{n - len(incomplete)} / {n}** "
      f"→ eksik: **{len(incomplete)}**")
    w(f"- Başlığı 140 karakterin **altında**: **{len(short_titles)} / {n}**")
    w(f"- **Yetim** tag (tek ilanda): **{len(orphans)}**")
    w(f"- Ort. favori/gün: **{df['fav_per_day'].mean():.3f}** · "
      f"ort. favori: **{df['num_favorers'].mean():.1f}** · "
      f"ort. görüntü: **{df['views'].mean():.0f}**")
    w("")

    w("## 1. En sık kullanılan tag'ler")
    w("")
    w("| # | tag | kaç ilanda | oran |")
    w("|---:|---|---:|---:|")
    for i, (tag, c) in enumerate(freq.most_common(40), 1):
        w(f"| {i} | {tag} | {c} | {c / n * 100:.0f}% |")
    w("")
    w(f"*(Toplam {total_unique} benzersiz tag; ilk 40 gösterildi.)*")
    w("")

    w(f"## 2. 13 tag'ini doldurmamış ilanlar ({len(incomplete)})")
    w("")
    if len(incomplete):
        w("| tag sayısı | başlık | listing_id |")
        w("|---:|---|---|")
        for _, r in incomplete.iterrows():
            w(f"| {r['tag_count']} | {r['title'][:70]} | "
              f"[{r['listing_id']}]({r['url']}) |")
    else:
        w("Hepsi 13 tag dolu. 👍")
    w("")

    w(f"## 3. 140 karakter altı başlıklar ({len(short_titles)} / {n})")
    w("")
    w("*Etsy başlık üst sınırı ~140; altı = boşa giden keyword alanı.*")
    w("")
    if len(short_titles) == n:
        w(f"⚠️ **Tüm {n} başlık 140 karakterin altında** "
          f"(en kısa {short_titles['title_length'].min()}, "
          f"en uzun {short_titles['title_length'].max()}). "
          "Yani her başlıkta ek keyword yeri var. En kısa "
          f"{SHOW_SHORT_TITLES} tanesi öncelikli:")
    w("")
    if len(short_titles):
        w("| uzunluk | başlık | listing_id |")
        w("|---:|---|---|")
        for _, r in short_titles.head(SHOW_SHORT_TITLES).iterrows():
            w(f"| {r['title_length']} | {r['title'][:70]} | "
              f"[{r['listing_id']}]({r['url']}) |")
        if len(short_titles) > SHOW_SHORT_TITLES:
            w("")
            w(f"*(+{len(short_titles) - SHOW_SHORT_TITLES} ilan daha; "
              "tam liste `data/listings.csv`'de `title_length` ile sırala.)*")
    else:
        w("Hepsi 140+ karakter.")
    w("")

    w(f"## 4. Yetim tag'ler — sadece 1 ilanda ({len(orphans)} / {total_unique})")
    w("")
    orphan_pct = len(orphans) / total_unique * 100 if total_unique else 0
    w(f"*Benzersiz tag'lerin **%{orphan_pct:.0f}**'i tek ilanda geçiyor — "
      "tag kullanımı çok dağınık. Tek seferlik tag'ler Etsy aramasında "
      "tekrar/otorite kazanamaz; güçlü keyword'lere konsolide et.*")
    w("")
    if orphans:
        w(f"İlk {min(SHOW_ORPHANS, len(orphans))} tanesi (tam liste → "
          f"`reports/orphan_tags.txt`):")
        w("")
        shown = orphans[:SHOW_ORPHANS]
        w("| | | | |")
        w("|---|---|---|---|")
        for i in range(0, len(shown), 4):
            row = shown[i : i + 4] + [""] * (4 - len(shown[i : i + 4]))
            w("| " + " | ".join(row) + " |")
    else:
        w("Yetim tag yok.")
    w("")

    w("## 5. Performans sinyali — üst %20 vs alt %20")
    w("")
    w(f"*Metrik: `num_favorers / yaş(gün)`. Üst/alt %20 = **{k}** ilan. "
      "Yaş için `original_creation_timestamp` kullanıldı.*")
    w("")
    w(f"- Üst %20 ort. favori/gün: **{top['fav_per_day'].mean():.3f}**")
    w(f"- Alt %20 ort. favori/gün: **{bottom['fav_per_day'].mean():.3f}**")
    w("")
    w("### 5a. Kazanan tag'ler (üst grupta baskın)")
    w("")
    w("*Üst %20'de alt %20'ye göre daha sık geçen tag'ler — koru/çoğalt.*")
    w("")
    w("| tag | üst %20 | alt %20 | fark |")
    w("|---|---:|---:|---:|")
    for t, d, tc, bc in winners:
        if d <= 0:
            continue
        w(f"| {t} | {tc} | {bc} | +{d * 100:.0f} puan |")
    w("")
    w("### 5b. Zayıf tag'ler (alt grupta baskın)")
    w("")
    w("*Alt %20'de daha sık geçen tag'ler — gözden geçir, değiştirmeyi düşün.*")
    w("")
    w("| tag | üst %20 | alt %20 | fark |")
    w("|---|---:|---:|---:|")
    for t, d, tc, bc in losers:
        if d >= 0:
            continue
        w(f"| {t} | {tc} | {bc} | {d * 100:.0f} puan |")
    w("")
    w("---")
    w("")
    w("> ⚠️ Performans sinyali gözlemseldir: yaş küçükken favori/gün oynak "
      "olabilir, tag dışı etkenler (görsel, fiyat, sezon) de rol oynar. "
      "Tag kararlarını Adım 4'teki eRank hacim/rekabet verisiyle birlikte ver.")
    w("")
    return "\n".join(L)


def main() -> None:
    df = load()
    report = build_report(df)
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(report)

    # Tam yetim tag listesini ayrı dosyaya yaz (rapor kısaltıyor).
    freq = tag_frequency(df)
    orphans = sorted(t for t, c in freq.items() if c == 1)
    ORPHANS_PATH.write_text("\n".join(orphans) + "\n")

    print(f"Rapor yazıldı: {REPORT_PATH.relative_to(ROOT)}")
    print(f"Yetim liste  : {ORPHANS_PATH.relative_to(ROOT)} ({len(orphans)} tag)")
    incomplete = int((df["tag_count"] < MAX_TAGS).sum())
    short = int((df["title_length"] < TITLE_MIN).sum())
    print(f"  benzersiz tag: {len(freq)} · yetim: {len(orphans)}")
    print(f"  13 tag eksik: {incomplete} · başlık<140: {short}")


if __name__ == "__main__":
    main()
