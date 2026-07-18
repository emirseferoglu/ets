"""
produce_specific.py — Belirli bir bestseller'ı (listing_id) üretir.

WhatsApp'tan "yap 3" / "poster 5" cevabı geldiğinde listener bunu çağırır.

Kullanım:
    python produce_specific.py --id 1234567890 --mode tv
    python produce_specific.py --id 1234567890 --mode poster
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BS_PATH = ROOT / "data" / "bestsellers.json"
BS_POSTER_PATH = ROOT / "data" / "bestsellers_poster.json"


def find_bestseller(listing_id: int) -> dict | None:
    for path in (BS_PATH, BS_POSTER_PATH):
        if not path.exists():
            continue
        for b in json.loads(path.read_text()):
            if b["listing_id"] == listing_id:
                return b
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--mode", choices=["tv", "poster"], default="tv")
    args = ap.parse_args()

    b = find_bestseller(args.id)
    if not b:
        raise SystemExit(f"bestsellers.json içinde {args.id} yok.")

    from notify_whatsapp import send_whatsapp

    try:
        if args.mode == "poster":
            from poster_daily import produce_target
            ok = produce_target(b)
        else:
            from generate_products import process
            from product_ideas import make_copy_idea
            idea = make_copy_idea(b)
            if not idea:
                raise RuntimeError("fikir üretilemedi (tag eksik)")
            result = process(idea, publish=True)
            ok = bool(result.get("draft_url"))
            if ok:
                send_whatsapp(f"✅ TV art hazır: {result['draft_url']}\n"
                              f"({idea['title'][:60]})")
                return
        if args.mode == "poster" and ok:
            send_whatsapp(f"✅ Poster draft hazır ({b['title'][:50]}…) — "
                          "Etsy taslaklarını kontrol et.")
    except Exception as e:  # noqa: BLE001
        send_whatsapp(f"❌ Üretim hatası ({args.mode} {args.id}): {str(e)[:150]}")
        raise


if __name__ == "__main__":
    main()
