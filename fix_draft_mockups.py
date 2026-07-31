"""
fix_draft_mockups.py — mevcut bir Etsy draft'ının mockup görsellerini,
sanat dosyasını YENİDEN ÜRETMEDEN (AI çağrısı yok, ücretsiz), sadece
düzeltilmiş poster_mockup.py ile yeniden oluşturup draft'a yükler.

"Aynısını yeniden üret" senaryosu için: sanat zaten output/'ta duruyor,
sadece mockup kalibrasyonu düzeldiği için görselleri tazelemek yeterli.

Kullanım:
    python fix_draft_mockups.py --listing-id 1234567890 --art output/poster-black-ink-flowers/poster_2x3.jpg
"""

from __future__ import annotations

import argparse
from pathlib import Path

from etsy_client import EtsyClient
from poster_mockup import render_all


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listing-id", type=int, required=True)
    ap.add_argument("--art", required=True, help="mevcut poster_2x3.jpg yolu")
    args = ap.parse_args()

    art_path = Path(args.art)
    if not art_path.exists():
        raise SystemExit(f"Sanat dosyası yok: {art_path}")

    mockup_dir = art_path.parent / "mockups"
    print(f"Mockup'lar yeniden oluşturuluyor: {mockup_dir}")
    mockups = render_all(art_path, mockup_dir)

    c = EtsyClient()
    lid = args.listing_id

    old_images = c.get_listing_images(lid)
    print(f"Mevcut {len(old_images)} görsel siliniyor…")
    for im in old_images:
        c.delete_listing_image(lid, im["listing_image_id"])

    print("Yeni mockup'lar yükleniyor…")
    for rank, img in enumerate(mockups, 1):
        c.upload_listing_image(lid, str(img), rank=rank)
        print(f"  ✓ {img.name} (rank {rank})")

    print(f"Tamamlandı: https://www.etsy.com/listing/{lid}")


if __name__ == "__main__":
    main()
