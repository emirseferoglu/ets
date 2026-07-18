"""
fetch_listings.py — Adım 2: tüm aktif ilanları çekip diske yaz.

Çıktı:
  data/listings.json  — tam kayıtlar (tags liste olarak), Adım 3 bunu okur.
  data/listings.csv   — aynı veri, tablo formatı (tags '|' ile birleşik).

Cache: data/listings.json varsa API'ye GİTMEZ, dosyadan okur.
       Taze veri için:  python fetch_listings.py --refresh

Salt-okunur: sadece EtsyClient'ın GET metodlarını kullanır.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from etsy_client import EtsyClient

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
JSON_PATH = DATA_DIR / "listings.json"
CSV_PATH = DATA_DIR / "listings.csv"

# CSV'de kolon sırası (ve JSON kayıtlarındaki alan seti).
COLUMNS = [
    "listing_id",
    "title",
    "title_length",
    "tags",
    "tag_count",
    "description",
    "price",
    "currency",
    "taxonomy_id",
    "num_favorers",
    "views",
    "created_timestamp",
    "original_creation_timestamp",
    "url",
]


def _price(raw: dict[str, Any] | None) -> float | None:
    """Etsy price {amount, divisor} → float."""
    if not raw:
        return None
    try:
        return round(raw["amount"] / raw["divisor"], 2)
    except (KeyError, TypeError, ZeroDivisionError):
        return None


def _shape(listing: dict[str, Any]) -> dict[str, Any]:
    """Ham Etsy listing → sadece ihtiyacımız olan alanlar."""
    tags = listing.get("tags") or []
    title = listing.get("title") or ""
    price_obj = listing.get("price") or {}
    return {
        "listing_id": listing.get("listing_id"),
        "title": title,
        "title_length": len(title),
        "tags": tags,
        "tag_count": len(tags),
        "description": listing.get("description") or "",
        "price": _price(price_obj),
        "currency": price_obj.get("currency_code"),
        "taxonomy_id": listing.get("taxonomy_id"),
        "num_favorers": listing.get("num_favorers"),
        "views": listing.get("views"),
        "created_timestamp": listing.get("created_timestamp"),
        "original_creation_timestamp": listing.get("original_creation_timestamp"),
        "url": listing.get("url"),
    }


def fetch(refresh: bool = False) -> list[dict[str, Any]]:
    """İlanları getir. Cache varsa ve --refresh yoksa dosyadan okur."""
    if JSON_PATH.exists() and not refresh:
        print(f"Cache'den okunuyor: {JSON_PATH.relative_to(ROOT)} "
              "(taze veri için --refresh)")
        return json.loads(JSON_PATH.read_text())

    print("Etsy API'den çekiliyor…")
    client = EtsyClient()
    raw = client.get_all_listings(state="active")
    records = [_shape(x) for x in raw]
    print(f"  {len(records)} aktif ilan çekildi.")
    return records


def save(records: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    # JSON — tags liste olarak korunur.
    JSON_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2))

    # CSV — tags '|' ile birleşik, kolon sırası sabit.
    df = pd.DataFrame(records, columns=COLUMNS)
    df_csv = df.copy()
    df_csv["tags"] = df_csv["tags"].apply(
        lambda t: "|".join(t) if isinstance(t, list) else ""
    )
    df_csv.to_csv(CSV_PATH, index=False)

    print(f"Yazıldı: {JSON_PATH.relative_to(ROOT)}  ({len(records)} kayıt)")
    print(f"Yazıldı: {CSV_PATH.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Etsy ilanlarını çek ve kaydet.")
    parser.add_argument(
        "--refresh", action="store_true",
        help="Cache'i yok say, API'den taze çek.",
    )
    args = parser.parse_args()

    records = fetch(refresh=args.refresh)
    save(records)

    # Kısa özet.
    if records:
        df = pd.DataFrame(records)
        full_tags = int((df["tag_count"] == 13).sum())
        print("\n— özet —")
        print(f"  ilan sayısı           : {len(df)}")
        print(f"  13 tag'i dolu ilan     : {full_tags} / {len(df)}")
        print(f"  ort. başlık uzunluğu   : {df['title_length'].mean():.0f} karakter")
        print(f"  ort. favori / görüntü  : {df['num_favorers'].mean():.1f} / "
              f"{df['views'].mean():.0f}")


if __name__ == "__main__":
    main()
