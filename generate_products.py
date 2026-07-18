"""
generate_products.py — Orchestrator: ürün fikirlerini uçtan uca ürüne çevirir.

Zincir (her fikir için):
  1. fal.ai Flux ile 16:9 görsel üret
  2. 4K teslim dosyası (şimdilik LANCZOS upscale; ileride fal AI upscaler)
  3. Mockup (#1 şablonu) — satış görseli
  4. (--publish-draft ile) Etsy TASLAK oluştur + mockup görselini + 4K dosyayı yükle

Varsayılan: sadece LOKAL üretir (output/<tema>/), Etsy'ye DOKUNMAZ.
--publish-draft: mağazada gerçek taslak oluşturur (müşteriye görünmez).

Kullanım:
    python product_ideas.py --count 3          # önce fikirler
    python generate_products.py                # lokal üret (Etsy yok)
    python generate_products.py --only cottagecore --publish-draft
    python generate_products.py --count 3 --publish-draft
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from generate_art import generate, upscale_4k
from mockup import load_templates, render

ROOT = Path(__file__).resolve().parent
IDEAS_JSON = ROOT / "data" / "product_ideas.json"
OUT_DIR = ROOT / "output"

PRICE = 3.00
TAXONOMY_ID = 2078          # kendi ilanlarındaki dijital duvar sanatı kategorisi


PRODUCED_PATH = ROOT / "data" / "produced_themes.json"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def record_theme(theme: str, source_listing_id: int | None = None) -> None:
    """Üretilen temayı kaydet — product_ideas ertesi gün bunu atlar.
    Bestseller taklitlerinde kaynak listing_id de saklanır (tekrar koruması)."""
    import time
    data = json.loads(PRODUCED_PATH.read_text()) if PRODUCED_PATH.exists() else []
    entry = {"theme": theme, "date": time.strftime("%Y-%m-%d")}
    if source_listing_id:
        entry["source_listing_id"] = source_listing_id
    data.append(entry)
    PRODUCED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def process(idea: dict, publish: bool) -> dict:
    theme = idea["theme"]
    slug = slugify(theme)
    d = OUT_DIR / slug
    d.mkdir(parents=True, exist_ok=True)

    art = d / "art_16x9.jpg"
    deliverable = d / "deliverable_4k.jpg"

    print(f"\n▶ {theme}")
    print("  görsel üretiliyor (Ideogram V4)…")
    generate(idea["art_prompt"], art,
             apply_texture=idea.get("apply_texture", True))
    print("  4K teslim dosyası (fal upscaler)…")
    upscale_4k(art, deliverable)

    # 6 listeleme görselini şablon sırasına göre üret (framed/fullbleed/static).
    templates = load_templates()
    order = templates.get("_order", ["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg", "6.jpg"])
    print(f"  {len(order)} listeleme görseli üretiliyor…")
    images = []
    for i, tname in enumerate(order, 1):
        out = d / f"img_{i}.jpg"
        render(deliverable, tname, out)
        images.append(out)

    (d / "listing.json").write_text(json.dumps({
        "title": idea["title"], "tags": idea["tags"],
        "description": idea["description"], "price": PRICE,
    }, ensure_ascii=False, indent=2))

    result = {"theme": theme, "dir": str(d.relative_to(ROOT)),
              "images": len(images), "draft_url": None}

    if publish:
        from etsy_client import EtsyClient
        client = EtsyClient()
        print("  Etsy taslak oluşturuluyor…")
        listing = client.create_draft_listing(
            title=idea["title"], description=idea["description"],
            price=PRICE, tags=idea["tags"], taxonomy_id=TAXONOMY_ID,
        )
        lid = listing["listing_id"]
        print(f"    taslak id={lid}, {len(images)} görsel yükleniyor…")
        for rank, img in enumerate(images, 1):
            client.upload_listing_image(lid, str(img), rank=rank)
        print("    4K dijital dosya yükleniyor…")
        client.upload_listing_file(lid, str(deliverable), name=f"{slug}-frame-tv-art-4k.jpg")
        result["draft_url"] = f"https://www.etsy.com/listing/{lid}"
        result["listing_id"] = lid
        record_theme(theme, idea.get("source_listing_id"))  # tekrar koruması
        print(f"    ✓ taslak hazır: {result['draft_url']}")
        # Airtable'a izlenebilirlik kaydı (token yoksa sessizce atlar)
        try:
            import time as _t
            from airtable_log import log_product
            if log_product(idea, result["draft_url"], _t.strftime("%Y-%m-%d")):
                print("    ✓ Airtable'a yazıldı")
        except Exception as e:  # noqa: BLE001
            print(f"    (Airtable atlandı: {str(e)[:80]})")

    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3, help="Kaç ürün işlensin.")
    ap.add_argument("--only", help="Sadece bu temayı işle.")
    ap.add_argument("--publish-draft", action="store_true",
                    help="Etsy'de gerçek taslak oluştur (yoksa sadece lokal).")
    args = ap.parse_args()

    if not IDEAS_JSON.exists():
        raise SystemExit("data/product_ideas.json yok. Önce: python product_ideas.py")
    ideas = json.loads(IDEAS_JSON.read_text())
    if args.only:
        ideas = [i for i in ideas if i["theme"] == args.only]
        if not ideas:
            raise SystemExit(f"'{args.only}' temalı fikir yok.")
    ideas = ideas[: args.count]

    mode = "ETSY TASLAK" if args.publish_draft else "sadece LOKAL"
    print(f"=== {len(ideas)} ürün · mod: {mode} ===")
    results = [process(i, args.publish_draft) for i in ideas]

    print("\n=== ÖZET ===")
    for r in results:
        line = f"• {r['theme']} → {r['dir']}"
        if r.get("draft_url"):
            line += f"  |  {r['draft_url']}"
        print(line)
    if not args.publish_draft:
        print("\nLokal üretildi. Etsy taslağı için: --publish-draft ekle.")


if __name__ == "__main__":
    main()
