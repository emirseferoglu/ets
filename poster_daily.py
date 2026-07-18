"""
poster_daily.py — Günlük 1 POSTER üretir ve Etsy taslağı açar.

Tema: data/bestsellers.json'dan (bestseller formülü) poster için henüz
kullanılmamış en yüksek skorlu TEKİL ürün. Frame TV temaları (botanik,
manzara, floral...) poster pazarında da aynı şekilde satar; title/tag'ler
TV dilinden poster diline çevrilir.

Akış: tema seç → OpenAI brief (referans görselle) → Ideogram V4 dikey master
→ ESRGAN 4x → 5-size baskı paketi → 6 mockup → Etsy taslak.

Kullanım:
    python poster_daily.py            # üret + taslak
    python poster_daily.py --dry      # sadece seçimi göster
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from product_ideas import (_is_blocked, _norm, holiday_season_status,
                           load_produced_listing_ids)

ROOT = Path(__file__).resolve().parent
BS_PATH = ROOT / "data" / "bestsellers.json"
PRODUCED_POSTERS = ROOT / "data" / "produced_posters.json"
OUT_DIR = ROOT / "output"
PRICE = 4.99
TAXONOMY_ID = 2078

# TV diline özgü tag'ler → poster karşılıkları
TV_TAG_PAT = re.compile(r"\btv\b|frame tv|samsung|screensaver|television|4k|"
                        r"hisense|\blg\b|\btcl\b|16x9|16 9", re.I)
POSTER_EVERGREEN = [
    "printable wall art", "digital print", "wall art print", "digital download",
    "vintage poster", "printable art", "home decor print", "instant download",
    "botanical print", "living room art", "bedroom wall art", "gallery wall art",
]


def _load_produced_posters() -> set[int]:
    if PRODUCED_POSTERS.exists():
        return {e["source_listing_id"] for e in json.loads(PRODUCED_POSTERS.read_text())}
    return set()


def _record_poster(listing_id: int, theme: str) -> None:
    data = json.loads(PRODUCED_POSTERS.read_text()) if PRODUCED_POSTERS.exists() else []
    data.append({"source_listing_id": listing_id, "theme": theme,
                 "date": time.strftime("%Y-%m-%d")})
    PRODUCED_POSTERS.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _posterize_title(title: str) -> str:
    """TV title'ını poster title'ına çevir."""
    t = title
    t = re.sub(r"Samsung Frame TV Art", "Wall Art Print", t, flags=re.I)
    t = re.sub(r"Frame TV Art", "Wall Art Print", t, flags=re.I)
    t = re.sub(r"Samsung Frame TV", "Printable Wall Art", t, flags=re.I)
    t = re.sub(r"Frame TV", "Wall Art", t, flags=re.I)
    t = re.sub(r"TV (Screensaver|Download|Decor|Art)", "Printable Art", t, flags=re.I)
    t = re.sub(r"\bScreensaver\b", "Print", t, flags=re.I)
    t = re.sub(r"\bTV\b", "Wall", t, flags=re.I)
    t = re.sub(r"\|?\s*#?[A-Z]{1,4}\d{1,6}[-\d]*\s*$", "", t)
    t = re.sub(r"\b16\s*[x:]\s*9\b", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" |,–-")
    if "digital download" not in t.lower():
        cand = t + " | Digital Download"
        t = cand if len(cand) <= 140 else t
    return t[:140]


def _posterize_tags(tags: list[str], shop_name: str = "") -> list[str]:
    out, seen = [], set()
    shop_key = _norm(shop_name).replace(" ", "")

    def add(x: str):
        x = re.sub(r"[^0-9A-Za-zÀ-ÿ ]", " ", str(x))
        x = re.sub(r"\s+", " ", x).strip()[:20]
        if not x or _norm(x) in seen or _is_blocked(x):
            return
        if shop_key and _norm(x).replace(" ", "") == shop_key:
            return
        out.append(x)
        seen.add(_norm(x))

    for t in tags:
        if len(out) >= 13:
            break
        if TV_TAG_PAT.search(t):
            continue                      # TV'ye özgü tag'i alma
        add(t)
    for e in POSTER_EVERGREEN:
        if len(out) >= 13:
            break
        add(e)
    return out[:13]


def _poster_pool() -> list[dict]:
    """Önce gerçek poster pazarı havuzu; yoksa TV havuzuna düş."""
    pp = ROOT / "data" / "bestsellers_poster.json"
    if pp.exists():
        pool = json.loads(pp.read_text())
        if pool:
            return pool
    return json.loads(BS_PATH.read_text()) if BS_PATH.exists() else []


def pick_poster_target() -> dict | None:
    produced = _load_produced_posters() | load_produced_listing_ids()
    for b in _poster_pool():
        if b["listing_id"] in produced:
            continue
        if _is_blocked(b["title"]):
            continue
        season = holiday_season_status(b["title"])
        if season and season[0] == "skip":
            continue
        if len(b.get("tags") or []) < 8:
            continue
        return b
    return None


def produce_one(args) -> bool:
    b = pick_poster_target()
    if not b:
        print("Poster için uygun bestseller kalmadı.")
        return False
    return produce_target(b, dry=args.dry)


def produce_target(b: dict, dry: bool = False) -> bool:
    """Verilen bestseller kaydından poster üret (webhook'tan da çağrılır)."""
    title = _posterize_title(b["title"])
    tags = _posterize_tags(b.get("tags") or [], b.get("shop_name", ""))
    theme_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:30]

    print(f"POSTER hedefi: {b['title'][:60]}")
    print(f"  bs_score={b['bs_score']}  fav/g={b['fav_per_day']}  view/g={b['views_per_day']}")
    print(f"  Yeni title: {title}")
    print(f"  Tags ({len(tags)}): {tags}")
    if dry:
        # dry modda da kaydet ki bir sonraki secim farkli olsun; sonra geri al
        _record_poster(b["listing_id"], theme_slug + "-DRY")
        return True

    # Brief SADECE art_prompt için kullanılır — description'ı TV diliyle
    # yazdığından poster açıklaması her zaman temiz şablondan üretilir.
    art_prompt = (f"Vintage painting recreating the subject of: {b['title']}. "
                  "Composed as a VERTICAL 2:3 poster with generous margins, "
                  "textured brushstrokes, muted palette, museum quality. "
                  "No text, no watermark, no frame, no border, no signature.")
    try:
        from ai_brief import generate_brief
        from ref_images import collect_reference_images, scrape_listing_description
        ref_imgs = collect_reference_images(
            b["listing_id"], b.get("url", ""), b.get("image", ""))
        ref_desc = scrape_listing_description(b.get("url", ""))
        print(f"  referans görsel: {len(ref_imgs)} adet, "
              f"firecrawl açıklama: {len(ref_desc)} kr")
        brief = generate_brief(theme_slug, tags[:12], ref_imgs,
                               reference_title=b["title"],
                               reference_description=ref_desc)
        art_prompt = brief["art_prompt"] + \
            " Composed as a VERTICAL 2:3 poster with balanced margins."
    except Exception as e:  # noqa: BLE001
        print(f"  (OpenAI brief atlandı: {str(e)[:60]} → şablon)")

    from poster_pack import included_files_text, make_pack
    description = (
        f"{title.split('|')[0].split(',')[0].strip()} — a beautiful printable "
        "art piece for living rooms, bedrooms, hallways and gallery walls.\n\n"
        + included_files_text() +
        "\n\n★ HOW TO PRINT\nDownload instantly after purchase and print at "
        "home, at a local print shop, or via an online print service. Frame it "
        "in any standard size up to 24x36 inch.\n\n"
        "★ NOTE\nThis is a digital product — no physical item will be shipped. "
        "Colors may vary slightly depending on your screen and printer. Due to "
        "the instant-download nature, this purchase is non-refundable.")

    flat = re.search(r"pastel|chalk|gouache|watercolou?r|crayon|flat|matte|"
                     r"\bink\b|sketch|drawing|line art|minimal", art_prompt, re.I)
    d = OUT_DIR / f"poster-{theme_slug}"
    result = make_pack(art_prompt, d, apply_texture=not flat)

    from poster_mockup import render_all
    mockups = render_all(d / "poster_2x3.jpg", d / "mockups")

    from etsy_client import EtsyClient
    client = EtsyClient()
    print("  Etsy taslak oluşturuluyor…")
    listing = client.create_draft_listing(
        title=title, description=description, price=PRICE,
        tags=tags, taxonomy_id=TAXONOMY_ID)
    lid = listing["listing_id"]
    for rank, img in enumerate(mockups, 1):
        client.upload_listing_image(lid, str(img), rank=rank)
    for name in ("2x3", "3x4", "4x5", "ISO", "11x14"):
        client.upload_listing_file(lid, str(d / f"poster_{name}.jpg"),
                                   name=f"{theme_slug}-{name}.jpg")
    _record_poster(b["listing_id"], theme_slug)
    print(f"  ✓ POSTER taslak hazır: https://www.etsy.com/listing/{lid}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--count", type=int, default=2, help="Kaç poster üretilsin.")
    args = ap.parse_args()
    for i in range(args.count):
        print(f"\n=== Poster {i + 1}/{args.count} ===")
        if not produce_one(args):
            break
    if args.dry:
        # dry kayıtlarını temizle
        import json as _json
        if PRODUCED_POSTERS.exists():
            data = [e for e in _json.loads(PRODUCED_POSTERS.read_text())
                    if not e.get("theme", "").endswith("-DRY")]
            PRODUCED_POSTERS.write_text(_json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
