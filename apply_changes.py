"""
apply_changes.py — Adım 6: analiz önerilerini CANLI ilanlara uygula (YAZMA).

⚠️ Bu script Etsy'de gerçek değişiklik yapar. `listings_w` scope'u gerekir
(authorize.py'yi listings_w ile yeniden çalıştır).

Hedef  : en çok görüntülenen ilanlar (--min-views eşiği).
Değişim: KALDIR tag'lerini çıkar + tematik tag ekle (13'e doldur) + başlığa
         sığan keyword'leri güvenli ekle (140 kr sınırı, tekrar yok, metni bozmaz).

Kullanım:
    python apply_changes.py                 # ÖNİZLEME (hiçbir şey yazmaz)
    python apply_changes.py --live          # CANLI uygula (önce yedek alır)
    python apply_changes.py --min-views 100 # eşiği değiştir
    python apply_changes.py --limit 5       # ilk N ilanla sınırla (güvenli deneme)
    python apply_changes.py --rollback data/backups/backup_XXX.json  # geri al

Yedek: her canlı çalıştırma öncesi hedef ilanların mevcut title+tags'i
       data/backups/ altına yazılır; --rollback ile eski hâle dönülür.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from etsy_client import EtsyClient
from merge_erank import (
    ERANK_DIR,
    LISTINGS_JSON,
    _norm,
    build_buckets,
    load_my_tags,
    read_all,
)
from action_plan import load_opportunities, match_for_listing

ROOT = Path(__file__).resolve().parent
BACKUP_DIR = ROOT / "data" / "backups"
TITLE_MAX = 140
TAG_MAX_LEN = 20
MAX_TAGS = 13


def _sanitize_tag(tag: str) -> str:
    """Etsy tag: fazla boşlukları topla, kırp, 20 karaktere sınırla."""
    return re.sub(r"\s+", " ", tag).strip()[:TAG_MAX_LEN]


def build_new_tags(old_tags: list[str], removals: list[str], adds: list[dict]) -> list[str]:
    """KALDIR'ları çıkar, tematik önerileri ekle; benzersiz, ≤13, ≤20 kr."""
    rem = {_norm(t) for t in removals}
    result, seen = [], set()
    for t in old_tags:
        nt = _norm(t)
        if nt in rem or nt in seen:
            continue
        result.append(t)
        seen.add(nt)
    for o in adds:
        if len(result) >= MAX_TAGS:
            break
        tag = _sanitize_tag(o["keyword"])
        nt = _norm(tag)
        if not tag or nt in seen:
            continue
        result.append(tag)
        seen.add(nt)
    return result


def build_new_title(old_title: str, title_adds: list[dict]) -> str:
    """Başlığa güvenli ekle: 140 kr'yi aşma, tekrar etme, mevcut metni koru."""
    title = (old_title or "").strip()
    words = set(re.findall(r"[a-z0-9]+", title.lower()))
    for o in title_adds:
        kw = re.sub(r"\s+", " ", o["keyword"]).strip()
        kw_words = set(re.findall(r"[a-z0-9]+", kw.lower()))
        if not kw_words or kw_words <= words:  # tamamı zaten varsa atla
            continue
        candidate = f"{title} | {kw}"
        if len(candidate) <= TITLE_MAX:
            title = candidate
            words |= kw_words
    return title


def compute_plan(min_views: int, limit: int | None) -> list[dict]:
    """Hedef ilanlar için (yeni title, yeni tags) hesapla; sadece değişenler."""
    listings = json.loads(LISTINGS_JSON.read_text())
    my_tags, my_freq = load_my_tags()
    kw, comp, brands, _ = read_all()
    buckets = build_buckets(my_tags, my_freq, kw, comp, brands)
    kaldir = {_norm(r["keyword"]) for r in buckets["remove"]}
    opps = load_opportunities(buckets)

    # En çok görüntülenenler önce.
    targets = [l for l in listings if (l.get("views") or 0) >= min_views]
    targets.sort(key=lambda l: -(l.get("views") or 0))
    if limit:
        targets = targets[:limit]

    plan = []
    for lst in targets:
        m = match_for_listing(lst, kaldir, opps)
        old_tags = lst.get("tags") or []
        old_title = lst.get("title") or ""
        new_tags = build_new_tags(old_tags, m["removals"], m["tag_adds"])
        new_title = build_new_title(old_title, m["title_adds"])

        tags_changed = new_tags != old_tags
        title_changed = new_title != old_title
        if not (tags_changed or title_changed):
            continue
        plan.append({
            "listing_id": lst["listing_id"],
            "url": lst["url"],
            "views": lst.get("views"),
            "old_title": old_title, "new_title": new_title,
            "old_tags": old_tags, "new_tags": new_tags,
            "tags_changed": tags_changed, "title_changed": title_changed,
        })
    return plan


def print_preview(plan: list[dict], min_views: int) -> None:
    print(f"\n=== ÖNİZLEME · views ≥ {min_views} · {len(plan)} ilan değişecek ===\n")
    for p in plan:
        print(f"• [{p['views']} views] {p['listing_id']}")
        if p["title_changed"]:
            print(f"    başlık:  {p['old_title']}")
            print(f"       →     {p['new_title']}")
        if p["tags_changed"]:
            added = [t for t in p["new_tags"] if t not in p["old_tags"]]
            removed = [t for t in p["old_tags"] if t not in p["new_tags"]]
            if removed:
                print(f"    çıkan:   {', '.join(removed)}")
            if added:
                print(f"    eklenen: {', '.join(added)}")
        print()
    print("Canlıya uygulamak için:  python apply_changes.py --live"
          + (f" --min-views {min_views}" if min_views != 50 else ""))


def do_backup(plan: list[dict]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"backup_{stamp}.json"
    snapshot = [
        {"listing_id": p["listing_id"], "title": p["old_title"], "tags": p["old_tags"]}
        for p in plan
    ]
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return path


def apply_live(plan: list[dict], min_views: int) -> None:
    if not plan:
        print("Değişecek ilan yok.")
        return
    backup = do_backup(plan)
    print(f"Yedek alındı: {backup.relative_to(ROOT)} ({len(plan)} ilan)")
    print(f"CANLI uygulanıyor ({len(plan)} ilan)…\n")

    client = EtsyClient()
    ok, fail = 0, 0
    for p in plan:
        try:
            client.update_listing(
                p["listing_id"],
                title=p["new_title"] if p["title_changed"] else None,
                tags=p["new_tags"] if p["tags_changed"] else None,
            )
            ok += 1
            print(f"  ✓ {p['listing_id']} güncellendi")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  ✗ {p['listing_id']} HATA: {str(e)[:150]}")
    print(f"\nBitti: {ok} başarılı, {fail} hata.")
    if fail:
        print("Hatalılar için scope (listings_w) ve yanıt mesajını kontrol et.")
    print(f"Geri almak için:  python apply_changes.py --rollback {backup.relative_to(ROOT)}")


def rollback(path_str: str) -> None:
    path = Path(path_str)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise SystemExit(f"Yedek bulunamadı: {path}")
    snapshot = json.loads(path.read_text())
    print(f"Geri alınıyor: {len(snapshot)} ilan ({path.name})…\n")
    client = EtsyClient()
    ok, fail = 0, 0
    for s in snapshot:
        try:
            client.update_listing(s["listing_id"], title=s["title"], tags=s["tags"])
            ok += 1
            print(f"  ✓ {s['listing_id']} eski hâline döndü")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  ✗ {s['listing_id']} HATA: {str(e)[:150]}")
    print(f"\nBitti: {ok} geri alındı, {fail} hata.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Analiz önerilerini canlı ilanlara uygula.")
    ap.add_argument("--live", action="store_true", help="Canlı uygula (yoksa önizleme).")
    ap.add_argument("--min-views", type=int, default=50, help="Hedef için min görüntülenme.")
    ap.add_argument("--limit", type=int, default=None, help="İlk N ilanla sınırla.")
    ap.add_argument("--rollback", metavar="YEDEK.json", help="Yedekten geri al.")
    args = ap.parse_args()

    if args.rollback:
        rollback(args.rollback)
        return
    if not LISTINGS_JSON.exists() or not (ERANK_DIR.exists() and list(ERANK_DIR.glob("*.csv"))):
        raise SystemExit("Önce fetch_listings.py çalıştır ve data/erank/*.csv koy.")

    plan = compute_plan(args.min_views, args.limit)
    if args.live:
        apply_live(plan, args.min_views)
    else:
        print_preview(plan, args.min_views)


if __name__ == "__main__":
    main()
