"""
show_applied.py — hangi ilanlarda ne değişti? Yedeklerden (eski hâl) yeniden
hesaplayıp okunabilir rapor üretir. Salt-okunur, API çağrısı yok.

Kullanım:
    python show_applied.py data/backups/backup_A.json data/backups/backup_B.json
    python show_applied.py            # argümansız: data/backups/*.json hepsi
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from merge_erank import LISTINGS_JSON, _norm, build_buckets, load_my_tags, read_all
from action_plan import load_opportunities, match_for_listing
from apply_changes import BACKUP_DIR, build_new_tags, build_new_title

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "reports" / "applied_changes.md"


def main() -> None:
    files = [Path(a) for a in sys.argv[1:]] or sorted(BACKUP_DIR.glob("*.json"))
    files = [f if f.is_absolute() else ROOT / f for f in files]

    # id → url eşlemesi (varsa).
    urls = {}
    if LISTINGS_JSON.exists():
        for r in json.loads(LISTINGS_JSON.read_text()):
            urls[r["listing_id"]] = r.get("url", "")

    my_tags, my_freq = load_my_tags()
    kw, comp, brands, _ = read_all()
    buckets = build_buckets(my_tags, my_freq, kw, comp, brands)
    kaldir = {_norm(r["keyword"]) for r in buckets["remove"]}
    opps = load_opportunities(buckets)

    # Yedekleri birleştir (listing_id başına en eski hâli tut).
    seen: dict[int, dict] = {}
    for f in files:
        for entry in json.loads(f.read_text()):
            seen.setdefault(entry["listing_id"], entry)

    rows = []
    for lid, entry in seen.items():
        old_tags = entry.get("tags") or []
        old_title = entry.get("title") or ""
        m = match_for_listing({"tags": old_tags, "title": old_title}, kaldir, opps)
        new_tags = build_new_tags(old_tags, m["removals"], m["tag_adds"])
        new_title = build_new_title(old_title, m["title_adds"])
        if new_tags == old_tags and new_title == old_title:
            continue
        rows.append({
            "listing_id": lid, "url": urls.get(lid, ""),
            "old_title": old_title, "new_title": new_title,
            "removed": [t for t in old_tags if t not in new_tags],
            "added": [t for t in new_tags if t not in old_tags],
            "title_changed": new_title != old_title,
        })

    L = [f"# Uygulanan Değişiklikler ({len(rows)} ilan)", "",
         "*Yedeklerden yeniden hesaplandı. Kaynak: " +
         ", ".join(f.name for f in files) + "*", ""]
    for i, r in enumerate(rows, 1):
        title = r["old_title"][:70]
        link = f"[{title}]({r['url']})" if r["url"] else title
        L.append(f"### {i}. {link}")
        L.append(f"`{r['listing_id']}`")
        if r["removed"]:
            L.append(f"- 🔴 çıkan tag: {', '.join('`'+t+'`' for t in r['removed'])}")
        if r["added"]:
            L.append(f"- 🟢 eklenen tag: {', '.join('`'+t+'`' for t in r['added'])}")
        if r["title_changed"]:
            L.append(f"- 📝 başlık: `{r['old_title']}` → `{r['new_title']}`")
        L.append("")

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(L))

    # Terminale özet.
    print(f"Rapor: {REPORT.relative_to(ROOT)}  ({len(rows)} ilan)\n")
    for i, r in enumerate(rows, 1):
        chg = []
        if r["removed"]:
            chg.append(f"-{len(r['removed'])} tag")
        if r["added"]:
            chg.append(f"+{len(r['added'])} tag")
        if r["title_changed"]:
            chg.append("başlık")
        print(f"{i:>2}. {r['listing_id']}  {r['old_title'][:52]}  ({', '.join(chg)})")


if __name__ == "__main__":
    main()
