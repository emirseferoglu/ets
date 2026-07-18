"""
daily_digest.py — Sabah üretiminden sonra WhatsApp özeti gönderir.

İçerik:
  * Bugün üretilen ürünler (draft linkleriyle)
  * Havuzda bekleyen popüler adaylar (numaralı) — "yap 3 5" veya
    "poster 4" cevabıyla ekstra üretim tetiklenir (whatsapp_listener.py).

Aday listesi data/daily_digest.json'a yazılır; listener numaraları buradan çözer.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from notify_whatsapp import send_whatsapp
from product_ideas import (_is_blocked, holiday_season_status,
                           load_produced_listing_ids)
from poster_daily import _load_produced_posters

ROOT = Path(__file__).resolve().parent
BS_PATH = ROOT / "data" / "bestsellers.json"
BS_POSTER_PATH = ROOT / "data" / "bestsellers_poster.json"
DIGEST_PATH = ROOT / "data" / "daily_digest.json"
PRODUCED = ROOT / "data" / "produced_themes.json"
PRODUCED_POSTERS = ROOT / "data" / "produced_posters.json"


def _today_produced() -> list[str]:
    today = time.strftime("%Y-%m-%d")
    lines = []
    for path, label in ((PRODUCED, "TV"), (PRODUCED_POSTERS, "Poster")):
        if path.exists():
            for e in json.loads(path.read_text()):
                if e.get("date") == today:
                    lines.append(f"  ✅ [{label}] {e.get('theme','?')}")
    return lines


def _candidates(path: Path, limit: int = 4) -> list[dict]:
    if not path.exists():
        return []
    used = load_produced_listing_ids() | _load_produced_posters()
    out = []
    for b in json.loads(path.read_text()):
        if b["listing_id"] in used or _is_blocked(b["title"]):
            continue
        season = holiday_season_status(b["title"])
        if season and season[0] == "skip":
            continue
        out.append(b)
        if len(out) >= limit:
            break
    return out


def main() -> None:
    tv_c = _candidates(BS_PATH)                 # Frame TV pazarından
    poster_c = _candidates(BS_POSTER_PATH)      # GERÇEK poster pazarından
    ordered = tv_c + poster_c
    digest = {str(i): b["listing_id"] for i, b in enumerate(ordered, 1)}
    DIGEST_PATH.write_text(json.dumps(
        {"date": time.strftime("%Y-%m-%d"), "map": digest}, indent=1))

    lines = ["🌅 Lumiaere sabah raporu", ""]
    produced = _today_produced()
    if produced:
        lines.append("Bugün üretilenler (draft):")
        lines += produced
        lines.append("")
    def _short_url(b: dict) -> str:
        return f"etsy.com/listing/{b['listing_id']}"

    n = 0
    if tv_c:
        lines.append("📺 Frame TV art adayları:")
        for b in tv_c:
            n += 1
            lines.append(f"{n}) {b['title'][:38]}… (fav/g {b['fav_per_day']})")
            lines.append(f"   {_short_url(b)}")
        lines.append("")
    if poster_c:
        lines.append("🖼 Poster adayları:")
        for b in poster_c:
            n += 1
            lines.append(f"{n}) {b['title'][:38]}… (fav/g {b['fav_per_day']})")
            lines.append(f"   {_short_url(b)}")
        lines.append("")
    if ordered:
        lines.append("Cevap yaz:")
        lines.append("• \"yap 1 2\" → TV art üretir")
        lines.append("• \"poster 5 6\" → poster üretir")
        lines.append("(her numara iki modda da kullanılabilir)")
    send_whatsapp("\n".join(lines))


if __name__ == "__main__":
    main()
