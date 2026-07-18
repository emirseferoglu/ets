"""
ref_images.py — Rakip listing'in TÜM görsellerini toplar (benzerlik için).

Sıra:
  1. Etsy API /listings/{id}/images  (ücretsiz, tam çözünürlük)
  2. Firecrawl scrape (FIRECRAWL_KEY doluysa; API görsel veremezse yedek)

Dönen liste generate_brief'e verilir — GPT-4o ilk 3 görseli analiz eder.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _from_etsy_api(listing_id: int) -> list[str]:
    try:
        from etsy_client import EtsyClient
        c = EtsyClient()
        r = c._request("GET", f"/listings/{listing_id}/images")
        urls = []
        for im in r.get("results", []):
            u = im.get("url_fullxfull") or im.get("url_570xN")
            if u:
                urls.append(u)
        return urls
    except Exception as e:  # noqa: BLE001
        print(f"  (etsy images hatası: {str(e)[:60]})")
        return []


def _from_firecrawl(listing_url: str) -> list[str]:
    key = os.getenv("FIRECRAWL_KEY", "").strip()
    if not key or not listing_url:
        return []
    try:
        r = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={"url": listing_url, "formats": ["html"]},
            timeout=90,
        )
        html = (r.json().get("data") or {}).get("html") or ""
        # il_fullxfull carousel görselleri
        urls = re.findall(
            r"https://i\.etsystatic\.com/[^\"'\s]+il_fullxfull[^\"'\s]+\.jpg", html)
        seen, out = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out[:6]
    except Exception as e:  # noqa: BLE001
        print(f"  (firecrawl hatası: {str(e)[:60]})")
        return []


def collect_reference_images(listing_id: int, listing_url: str = "",
                             fallback: str = "") -> list[str]:
    """En iyi referans görsel listesi; hiçbiri yoksa [fallback]."""
    urls = _from_etsy_api(listing_id)
    if not urls:
        urls = _from_firecrawl(listing_url)
    if not urls and fallback:
        urls = [fallback]
    return urls


_BOILER = re.compile(
    r"(instant download|digital download|no physical|smartthings|how to|"
    r"refund|3840|16:9|frame tv|usb|wi-?fi|purchase|file|jpg|png|resolution|"
    r"terms|copyright|shop|review|shipping|cart|favorites|personal use|"
    r"resale|prohibited|modification|public domain|contact|questions|"
    r"monitors|screens|colou?rs? may|easy to add|step by step)", re.I)

# Satır ancak SANATI tarif ediyorsa tutulur (renk/stil/konu kelimesi içermeli).
_VISUAL = re.compile(
    r"(paint|art(work)?|color|tone|hue|palette|style|vintage|antique|abstract|"
    r"landscape|floral|botanical|texture|inspired|warm|muted|soft|moody|"
    r"neutral|hand[- ]?(drawn|painted)|brush|watercolou?r|oil|pastel|sketch|"
    r"illustration|scene|motif|depict)", re.I)


def scrape_listing_description(listing_url: str) -> str:
    """Firecrawl ile rakip sayfasını tarar, SANATI TARİF EDEN cümleleri döndürür.

    Satıcının kendi açıklamasındaki görsel tarifler (stil, renk, konu) prompt
    kalitesini yükseltir; indirme/teslimat boilerplate'i atılır."""
    key = os.getenv("FIRECRAWL_KEY", "").strip()
    if not key or not listing_url:
        return ""
    try:
        r = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={"url": listing_url, "formats": ["markdown"]},
            timeout=90,
        )
        md = (r.json().get("data") or {}).get("markdown") or ""
        if not md:
            return ""
        # 1) Açıklama bölümünü izole et (varsa başlıklar arasında)
        low = md.lower()
        start = 0
        for marker in ("item details", "description"):
            i = low.find(marker)
            if i != -1:
                start = i
                break
        end = len(md)
        for marker in ("meet your seller", "reviews", "shipping",
                       "you may also like", "related searches"):
            i = low.find(marker, start + 20)
            if i != -1:
                end = min(end, i)
        segment = md[start:end]
        # 2) Link/nav/boilerplate satırlarını at, sanat tarifi kalsın
        keep = []
        for line in segment.splitlines():
            s = line.strip(" #*-•>")
            if not (20 < len(s) < 300):
                continue
            if "](" in s or s.startswith("[") or "etsy.com" in s or "http" in s:
                continue
            if _BOILER.search(s) or not _VISUAL.search(s):
                continue
            keep.append(s)
            if len(keep) >= 12:
                break
        return "\n".join(keep)[:1200]
    except Exception as e:  # noqa: BLE001
        print(f"  (firecrawl desc hatası: {str(e)[:60]})")
        return ""
