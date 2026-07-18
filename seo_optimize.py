"""
seo_optimize.py — Mevcut listing'lerin title + 13 tag'ini rakip arama
verilerine dayandırarak agresif şekilde optimize eder.

Her listing için:
  1. Etsy arama API'sinden en başarılı 100 rakibi çeker
  2. Favori-ağırlıklı tag skorlaması yapar
  3. Zayıf tag'leri rakip verisinde yüksek skorlu tag'lerle değiştirir
  4. Title'ı SEO-dostu formatla düzeltir

Kullanım:
    python seo_optimize.py --preview              # Önizleme
    python seo_optimize.py --live                  # İlk 20'yi uygula
    python seo_optimize.py --live --offset 20      # 21-40 arası
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from etsy_client import EtsyClient, sanitize_tag

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
LISTINGS_JSON = DATA_DIR / "listings.json"
TITLE_MAX = 140
TAG_MAX = 13
TAG_CHAR_MAX = 20

GENERIC_STOPS = {
    "samsung", "frame", "tv", "art", "digital", "download", "instant",
    "4k", "print", "wall", "decor", "the", "a", "an", "of", "for",
    "and", "with", "oil", "painting", "vintage", "modern", "cozy",
    "high", "resolution", "screensaver", "wallpaper", "quality",
    "poster", "artwork", "canvas",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _extract_search_query(listing: dict) -> str:
    title = listing.get("title", "")
    words = re.findall(r"[A-Za-z]+", title)
    theme_words = [w for w in words if w.lower() not in GENERIC_STOPS and len(w) > 2][:4]
    return " ".join(theme_words) + " frame tv art"


def fetch_competitor_tags(client: EtsyClient, query: str, pages: int = 2) -> list[dict]:
    all_listings = []
    for page in range(pages):
        try:
            resp = client._send(
                "GET",
                "/listings/active",
                params={
                    "keywords": query,
                    "limit": 50,
                    "offset": page * 50,
                    "sort_on": "score",
                    "includes": "Tags",
                },
            )
        except Exception:
            break
        for lst in resp.get("results", []):
            all_listings.append({
                "title": lst.get("title", ""),
                "tags": lst.get("tags", []),
                "favs": lst.get("num_favorers", 0) or 0,
                "views": lst.get("views", 0) or 0,
            })
    return all_listings


def score_tags(competitor_listings: list[dict]) -> list[tuple[str, float]]:
    tag_scores: Counter = Counter()
    tag_count: Counter = Counter()
    for lst in competitor_listings:
        weight = max(1, lst["favs"])
        for tag in lst["tags"]:
            nt = _norm(tag)
            if len(nt) < 3 or len(nt) > TAG_CHAR_MAX:
                continue
            tag_scores[nt] += weight
            tag_count[nt] += 1
    scored = []
    for tag, score in tag_scores.most_common(200):
        count = tag_count[tag]
        if count >= 2:
            scored.append((tag, score, count))
    return scored


def _overlap(a: str, b: str) -> bool:
    """İki tag birbirinin substring'i mi veya %80+ kelime örtüşmesi var mı."""
    if a in b or b in a:
        return True
    wa = set(a.split())
    wb = set(b.split())
    if not wa or not wb:
        return False
    common = wa & wb
    return len(common) / min(len(wa), len(wb)) >= 0.8


def optimize_listing(
    listing: dict,
    scored_tags: list[tuple[str, float, int]],
) -> dict:
    old_title = listing.get("title", "")
    old_tags = listing.get("tags", [])
    listing_id = listing["listing_id"]

    competitor_tag_set = {t for t, s, c in scored_tags[:50]}

    existing_scored = []
    for t in old_tags:
        nt = _norm(sanitize_tag(t))
        found_score = 0
        for ct, cs, cc in scored_tags:
            if ct == nt or _overlap(ct, nt):
                found_score = cs
                break
        existing_scored.append((t, nt, found_score))

    existing_scored.sort(key=lambda x: x[2], reverse=True)

    new_tags = []
    seen = set()

    essentials = ["samsung frame tv art", "frame tv art", "digital download"]
    for e in essentials:
        ne = _norm(e)
        if ne not in seen:
            already_present = any(_norm(sanitize_tag(t)) == ne for t in old_tags)
            if already_present:
                new_tags.append(sanitize_tag(e))
                seen.add(ne)

    for orig, nt, score in existing_scored:
        if len(new_tags) >= TAG_MAX:
            break
        if nt in seen:
            continue
        if _overlap_any(nt, seen):
            continue
        new_tags.append(sanitize_tag(orig))
        seen.add(nt)

    for tag_text, tag_score, tag_count in scored_tags:
        if len(new_tags) >= TAG_MAX:
            break
        cleaned = sanitize_tag(tag_text)
        nc = _norm(cleaned)
        if not cleaned or nc in seen or len(nc) > TAG_CHAR_MAX:
            continue
        if _overlap_any(nc, seen):
            continue
        new_tags.append(cleaned)
        seen.add(nc)

    for e in essentials:
        ne = _norm(e)
        if ne not in seen and not _overlap_any(ne, seen) and len(new_tags) < TAG_MAX:
            new_tags.append(e)
            seen.add(ne)

    new_tags = new_tags[:TAG_MAX]

    weakest = []
    for t in new_tags:
        nt = _norm(t)
        found = 0
        for ct, cs, cc in scored_tags:
            if ct == nt or _overlap(ct, nt):
                found = cs
                break
        weakest.append((t, found))

    strong_replacements = []
    used_new = {_norm(t) for t in new_tags}
    for tag_text, tag_score, tag_count in scored_tags:
        nc = _norm(sanitize_tag(tag_text))
        if nc in used_new or not nc or len(nc) > TAG_CHAR_MAX:
            continue
        if _overlap_any(nc, used_new):
            continue
        strong_replacements.append((sanitize_tag(tag_text), tag_score))
        if len(strong_replacements) >= 5:
            break

    weakest.sort(key=lambda x: x[1])
    replaced = 0
    for weak_tag, weak_score in weakest:
        if replaced >= len(strong_replacements):
            break
        strong_tag, strong_score = strong_replacements[replaced]
        if strong_score > weak_score * 2 and weak_score < 50:
            idx = new_tags.index(weak_tag)
            old_nt = _norm(weak_tag)
            new_nt = _norm(strong_tag)
            new_tags[idx] = strong_tag
            used_new.discard(old_nt)
            used_new.add(new_nt)
            replaced += 1

    new_title = _optimize_title(old_title)

    return {
        "listing_id": listing_id,
        "old_title": old_title,
        "new_title": new_title,
        "old_tags": old_tags,
        "new_tags": new_tags,
        "title_changed": new_title != old_title,
        "tags_changed": [_norm(t) for t in new_tags] != [_norm(t) for t in old_tags],
    }


def _overlap_any(tag: str, existing: set) -> bool:
    for e in existing:
        if _overlap(tag, e):
            return True
    return False


def _optimize_title(title: str) -> str:
    new_title = title.strip()

    if "Samsung Frame TV Art" in new_title:
        pass
    elif "Samsung Frame TV" in new_title:
        new_title = new_title.replace("Samsung Frame TV", "Samsung Frame TV Art", 1)
    elif "Frame TV Art" in new_title:
        new_title = new_title.replace("Frame TV Art", "Samsung Frame TV Art", 1)
    elif "Frame TV" in new_title:
        new_title = new_title.replace("Frame TV", "Samsung Frame TV Art", 1)

    if "Samsung Frame TV Art" in new_title:
        c = new_title.count("Samsung")
        if c > 1:
            first = new_title.index("Samsung")
            parts = []
            pos = 0
            found = 0
            while True:
                idx = new_title.find("Samsung", pos)
                if idx == -1:
                    parts.append(new_title[pos:])
                    break
                found += 1
                if found == 1:
                    parts.append(new_title[pos:idx + len("Samsung")])
                    pos = idx + len("Samsung")
                else:
                    before = new_title[pos:idx]
                    after_samsung = new_title[idx + len("Samsung"):]
                    parts.append(before)
                    parts.append(after_samsung)
                    break
            new_title = "".join(parts).strip()
            new_title = re.sub(r"\s+", " ", new_title)

    if "Digital Download" not in new_title and "Download" not in new_title:
        candidate = new_title.rstrip() + " | Digital Download"
        if len(candidate) <= TITLE_MAX:
            new_title = candidate

    if len(new_title) > TITLE_MAX:
        new_title = new_title[:TITLE_MAX].rsplit(" ", 1)[0]

    return new_title


def do_backup(changes: list[dict]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"seo_backup_{stamp}.json"
    snapshot = [
        {"listing_id": c["listing_id"], "title": c["old_title"], "tags": c["old_tags"]}
        for c in changes
    ]
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", default=True)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--count", type=int, default=20)
    args = ap.parse_args()

    if not LISTINGS_JSON.exists():
        raise SystemExit("Önce: python fetch_listings.py --refresh")

    listings = json.loads(LISTINGS_JSON.read_text())

    edited_ids = set()
    for f in BACKUP_DIR.glob("*.json"):
        for entry in json.loads(f.read_text()):
            edited_ids.add(entry["listing_id"])

    unedited = [l for l in listings if l["listing_id"] not in edited_ids]
    unedited.sort(key=lambda x: -(x.get("views") or 0))

    batch = unedited[args.offset : args.offset + args.count]
    if not batch:
        print("İşlenecek listing kalmadı.")
        return

    print(f"SEO optimizasyonu: {len(batch)} listing (offset={args.offset})")
    print("=" * 70)

    client = EtsyClient()
    changes = []

    for i, listing in enumerate(batch, 1):
        query = _extract_search_query(listing)
        print(f"\n[{i}/{len(batch)}] {listing['listing_id']}: {listing['title'][:60]}...")
        print(f"  Arama: '{query}'")

        competitors = fetch_competitor_tags(client, query, pages=2)
        print(f"  {len(competitors)} rakip bulundu")

        scored = score_tags(competitors)
        top_tags = [t for t, s, c in scored[:10]]
        print(f"  Top tag'ler: {', '.join(top_tags[:8])}")

        result = optimize_listing(listing, scored)
        changes.append(result)

        if result["tags_changed"] or result["title_changed"]:
            if result["title_changed"]:
                print(f"  TITLE ESKİ: {result['old_title'][:80]}")
                print(f"  TITLE YENİ: {result['new_title'][:80]}")

            old_set = {_norm(t) for t in result["old_tags"]}
            new_set = {_norm(t) for t in result["new_tags"]}
            added = new_set - old_set
            removed = old_set - new_set
            if removed:
                print(f"  - ÇIKAN:  {', '.join(sorted(removed))}")
            if added:
                print(f"  + GELEN:  {', '.join(sorted(added))}")
            print(f"  YENİ TAGS: {result['new_tags']}")
        else:
            print("  (değişiklik yok)")

        time.sleep(0.3)

    actual = [c for c in changes if c["tags_changed"] or c["title_changed"]]
    print(f"\n{'=' * 70}")
    print(f"Toplam: {len(actual)}/{len(batch)} listing'de değişiklik var.")

    if args.live and actual:
        backup = do_backup(actual)
        print(f"\nYedek alındı: {backup.relative_to(ROOT)}")
        print(f"CANLI uygulanıyor ({len(actual)} listing)...\n")

        ok, fail = 0, 0
        for c in actual:
            try:
                client.update_listing(
                    c["listing_id"],
                    title=c["new_title"] if c["title_changed"] else None,
                    tags=c["new_tags"] if c["tags_changed"] else None,
                )
                ok += 1
                print(f"  ✓ {c['listing_id']} — {c['new_title'][:50]}")
            except Exception as e:
                fail += 1
                print(f"  ✗ {c['listing_id']}: {str(e)[:150]}")
        print(f"\nBitti: {ok} başarılı, {fail} hata.")
        if fail:
            print(f"Geri al: python apply_changes.py --rollback {backup.relative_to(ROOT)}")
    elif not args.live:
        print("\nCanlıya uygulamak için: python seo_optimize.py --live")


if __name__ == "__main__":
    main()
