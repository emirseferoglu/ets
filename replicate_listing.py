"""
replicate_listing.py — Kullanıcının verdiği TEK BİR Etsy linkini/ID'sini
(bestseller havuzunda olsun olmasın) taklit edip Etsy'de draft oluşturur.

produce_specific.py'den farkı: o yalnızca data/bestsellers*.json içindeki
otomatik taranmış ID'lerle çalışır. Bu script keyfi bir rakip linkini
doğrudan Etsy API'den (get_listing, public) çekip aynı taklit hattından
(title+tag kopya, görsel benzerlik, Ideogram üretim) geçirir.

Kullanım:
    python replicate_listing.py --url "https://www.etsy.com/listing/4485994177/..."
    python replicate_listing.py --id 4485994177 --mode tv
"""

from __future__ import annotations

import argparse
import re
import time


def _extract_id(url_or_id: str) -> int:
    m = re.search(r"/listing/(\d+)", url_or_id)
    if m:
        return int(m.group(1))
    if url_or_id.strip().isdigit():
        return int(url_or_id.strip())
    raise SystemExit(f"Listing ID bulunamadı: {url_or_id!r}")


def build_bestseller_dict(listing_id: int) -> dict:
    """Tek bir listing'i extract_bestsellers() ile aynı şekle sokar,
    böylece make_copy_idea() ve üretim hattı değişmeden kullanılabilir."""
    from etsy_client import EtsyClient

    c = EtsyClient()
    l = c.get_listing(listing_id)

    now = time.time()
    oc = l.get("original_creation_timestamp") or 0
    age = max((now - oc) / 86400.0, 1.0) if oc else 365.0
    fav = l.get("num_favorers") or 0
    views = l.get("views") or 0
    fpd, vpd = fav / age, views / age

    imgs = l.get("images") or []
    img = imgs[0].get("url_fullxfull") if imgs else None
    tags = l.get("tags") or []
    shop = l.get("shop") or {}

    return {
        "listing_id": listing_id,
        "shop_id": l.get("shop_id"),
        "shop_name": shop.get("shop_name", ""),
        "title": l.get("title") or "",
        "tags": tags,
        "url": (l.get("url") or "").split("?")[0],
        "image": img,
        "favorites": fav,
        "views": views,
        "age_days": round(age),
        "fav_per_day": round(fpd, 3),
        "views_per_day": round(vpd, 2),
        "bs_score": round(fpd / 0.59 + vpd / 7.9, 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="Etsy listing linki")
    src.add_argument("--id", type=int, help="Etsy listing_id")
    ap.add_argument("--mode", choices=["tv", "poster"], default="tv")
    args = ap.parse_args()

    listing_id = args.id if args.id is not None else _extract_id(args.url)

    print(f"Çekiliyor: listing_id={listing_id}")
    b = build_bestseller_dict(listing_id)
    if not b["title"] or len(b["tags"]) < 8:
        raise SystemExit(
            f"İlan tag'leri eksik/çekilemedi ({len(b['tags'])} tag) — "
            "sağlıklı taklit yapılamaz."
        )
    print(f"  başlık: {b['title'][:70]}")
    print(f"  tag: {len(b['tags'])}  fav/gün: {b['fav_per_day']}  view/gün: {b['views_per_day']}")

    from notify_whatsapp import send_whatsapp

    try:
        if args.mode == "poster":
            from poster_daily import produce_target
            ok = produce_target(b)
            if ok:
                send_whatsapp(
                    f"✅ Poster draft hazır ({b['title'][:50]}…) — "
                    "Etsy taslaklarını kontrol et."
                )
        else:
            from generate_products import process
            from product_ideas import make_copy_idea

            idea = make_copy_idea(b)
            if not idea:
                raise RuntimeError("fikir üretilemedi (tag eksik)")
            result = process(idea, publish=True)
            ok = bool(result.get("draft_url"))
            if ok:
                send_whatsapp(
                    f"✅ TV art hazır: {result['draft_url']}\n"
                    f"({idea['title'][:60]})"
                )
        if not ok:
            print("Üretim tamamlanamadı (draft linki yok).")
    except Exception as e:  # noqa: BLE001
        send_whatsapp(f"❌ Üretim hatası ({args.mode}, listing {listing_id}): {str(e)[:150]}")
        raise


if __name__ == "__main__":
    main()
