"""
airtable_log.py — üretilen her ürünü Airtable'a satır olarak yazar (izlenebilirlik).

Base: etsy-otomasyon-kararları · Tablo: Ürünler. Alanlar Türkçe isimleriyle yazılır.
AIRTABLE_TOKEN yoksa sessizce atlar (otomasyonu bloklamaz).
"""

from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

TOKEN = os.getenv("AIRTABLE_TOKEN", "")
BASE = os.getenv("AIRTABLE_BASE_ID", "")
TABLE = os.getenv("AIRTABLE_TABLE_ID", "")


def log_product(idea: dict, draft_url: str, date: str) -> bool:
    """Bir ürünü Airtable'a yaz. Başarı=True. Token yoksa/hata olursa False (sessiz)."""
    if not (TOKEN and BASE and TABLE):
        return False
    ref = idea.get("reference") or {}
    fields = {
        "Başlık": idea.get("title", ""),
        "Tarih": date,
        "Tema": idea.get("theme", ""),
        "Kaynak": idea.get("market_source", ""),
        "Neden Seçildi": idea.get("why", ""),
        "Bende İlan": idea.get("my_coverage"),
        "Referans İlan": (ref.get("title") or "")[:200] if ref else "",
        "Referans Link": ref.get("url") or "" if ref else "",
        "Referans Favori": ref.get("favorites") if ref else None,
        "Referans Görsel": ref.get("image") or "" if ref else "",
        "Taglar": " | ".join(idea.get("tags", [])),
        "Brief Kaynağı": "OpenAI" if idea.get("brief_source") == "openai" else "Şablon",
        "Taslak Link": draft_url,
        "Durum": "Taslak",
    }
    if idea.get("trend_score") is not None:
        fields["Trend Skoru"] = idea["trend_score"]
    # None değerleri temizle (Airtable boş string/None istemez bazı tiplerde)
    fields = {k: v for k, v in fields.items() if v not in (None, "")}
    try:
        r = requests.post(
            f"https://api.airtable.com/v0/{BASE}/{TABLE}",
            headers={"Authorization": f"Bearer {TOKEN}",
                     "Content-Type": "application/json"},
            json={"records": [{"fields": fields}], "typecast": True},
            timeout=30,
        )
        if r.status_code in (200, 201):
            return True
        print(f"    (Airtable {r.status_code}: {r.text[:150]})")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"    (Airtable hata: {str(e)[:100]})")
        return False


if __name__ == "__main__":
    ok = log_product(
        {"title": "TEST ürün", "theme": "test", "market_source": "Canlı Trend",
         "why": "test", "my_coverage": 0, "reference": None, "tags": ["a", "b"],
         "brief_source": "openai", "trend_score": 123},
        "https://www.etsy.com/listing/0", "2026-07-16")
    print("Airtable testi:", "✓" if ok else "✗")
