"""
market_research.py — CANLI trend araştırması (kendi Etsy API'miz, ÜCRETSİZ).

Etsy findAllListingsActive ile "frame tv art" pazarını tarar, en çok ranking
alan + favori toplayan ilanların TAG'lerini favoriye göre ağırlıklandırıp
"yükselen temaları" çıkarır. Apify'a gerek yok — tag'ler resmi API'den gelir.

Çıktı: data/trending_themes.json  (product_ideas bunu okuyup temaları önceliklendirir)

Kullanım:
    python market_research.py                 # "frame tv art"
    python market_research.py --keyword "frame tv art" --pages 3
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from etsy_client import EtsyClient
from product_ideas import THEME_STOP, _is_blocked, tokens

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "trending_themes.json"
BS_OUT = ROOT / "data" / "bestsellers.json"
BS_POSTER_OUT = ROOT / "data" / "bestsellers_poster.json"

# Bestseller taraması için ek niche sorgular (ana keyword'e ek).
BS_QUERIES = [
    "frame tv art",
    "samsung frame tv art",
    "frame tv art oil painting",
    "frame tv art vintage",
    "frame tv art textured",
]

# POSTER pazarı sorguları (ayrı havuz — digest'in poster bölümü bunu kullanır).
POSTER_QUERIES = [
    "printable wall art vintage",
    "botanical print digital download",
    "wall art print digital download",
    "vintage poster printable",
    "nursery printable wall art",
]
# Poster havuzuna TV ürünleri sızmasın.
_TV_WORDS = ("frame tv", "samsung", "screensaver", "tv art")

# Bundle/koleksiyon ilanları taklit hedefi DEĞİL (binlerce dosya satıyorlar).
BUNDLE_WORDS = ("bundle", "set of", "collection", "mega", "lifetime",
                "all-in-one", "all in one", "complete store", "entire store",
                "5000", "7500", "10000", "16000", "40000", "200+", "100+",
                "450+", "500+", "850+", "320")

# Trend sinyali için işe yaramayan çekirdek/jenerik tag'ler (tema değil).
STAPLE_STOP = THEME_STOP | {
    "samsung", "frame", "tv", "art", "digital", "download", "instant",
    "wall", "decor", "print", "screensaver", "wallpaper", "background",
    "artful", "instantly", "lg",
}


def fetch_market(keyword: str, pages: int, per_page: int = 100) -> list[dict]:
    c = EtsyClient()
    out: list[dict] = []
    for i in range(pages):
        page = c._request("GET", "/listings/active", params={
            "keywords": keyword, "sort_on": "score", "sort_order": "down",
            "limit": per_page, "offset": i * per_page, "includes": "Tags,Images",
        })
        batch = page.get("results", [])
        out.extend(batch)
        if len(batch) < per_page:
            break
    return out


def trending_themes(listings: list[dict]) -> list[dict]:
    """
    Tag'leri favoriye göre ağırlıklandırıp tema kelimelerini sırala.
    Her tema için, o temayı içeren gerçek tag'leri de sakla (product_ideas
    bunları başlık/tag/prompt üretiminde kullanır).
    """
    score: dict[str, float] = defaultdict(float)
    breadth: dict[str, int] = defaultdict(int)  # kaç farklı ilanda
    tag_weight: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    # Her tema için en yüksek favorili ilanın referans görseli (OpenAI benchmark).
    ref: dict[str, tuple[int, str]] = {}  # theme -> (favori, image_url)
    now = time.time()
    for l in listings:
        fav = l.get("num_favorers") or 0
        views = l.get("views") or 0
        # VELOCITY: favori/gün (gerçek yaşla) — eski-birikmiş bias'ını kırar.
        oc = l.get("original_creation_timestamp") or 0
        age = max((now - oc) / 86400.0, 7.0) if oc else 365.0
        weight = 0.2 + fav / age + (views / age) / 50.0
        imgs = l.get("images") or []
        img_url = imgs[0].get("url_fullxfull") if imgs else None
        seen = set()
        for tag in l.get("tags") or []:
            if _is_blocked(tag):
                continue
            for tok in tokens(tag) - STAPLE_STOP:
                score[tok] += weight
                tag_weight[tok][tag] += weight
                if tok not in seen:
                    breadth[tok] += 1
                    seen.add(tok)
                    # bu temayı içeren en yüksek favorili ilanın görselini sakla
                    if img_url and fav > ref.get(tok, (-1, ""))[0]:
                        ref[tok] = (fav, img_url)
    ranked = sorted(score.items(), key=lambda x: -x[1])
    result = []
    for tok, s in ranked:
        if breadth[tok] < 2:  # en az 2 ilanda geçsin
            continue
        top_tags = sorted(tag_weight[tok].items(), key=lambda x: -x[1])[:8]
        keywords = [
            {"keyword": t, "avg_searches": round(w),
             "competitor_est_sales": 0, "value": round(w)}
            for t, w in top_tags
        ]
        result.append({"theme": tok, "score": round(s), "listings": breadth[tok],
                        "keywords": keywords,
                        "reference_images": [ref[tok][1]] if tok in ref else []})
    return result


def _is_bundle(title: str) -> bool:
    t = title.lower()
    return any(b in t for b in BUNDLE_WORDS)


def extract_bestsellers(listings: list[dict]) -> list[dict]:
    """
    Bestseller formülü (veriden tersine mühendislik, 2026-07):
      fav/gün >= 0.3  VEYA  view/gün >= 5  → yüksek olasılıkla Bestseller rozetli.
    (51 gerçek rozetli ilanla doğrulandı: 43 tekil üründe %97 yakalama.
     Kontrol grubu maks. 0.38/6.4 olduğundan yanlış pozitif riski düşük;
     seçim zaten bs_score sıralı olduğundan sınırdakiler alt sırada kalır.
     Rozet listing bazlı ve son-6-ay satış hızına bağlı; API satış vermediği
     için fav/view hızı en iyi vekil.)
    """
    now = time.time()
    out, seen = [], set()
    for l in listings:
        lid = l.get("listing_id")
        if not lid or lid in seen:
            continue
        seen.add(lid)
        title = l.get("title") or ""
        if _is_bundle(title) or _is_blocked(title):
            continue
        oc = l.get("original_creation_timestamp") or 0
        if not oc:
            continue
        age = max((now - oc) / 86400.0, 1.0)
        fav = l.get("num_favorers") or 0
        views = l.get("views") or 0
        fpd, vpd = fav / age, views / age
        if fpd < 0.3 and vpd < 5:
            continue
        imgs = l.get("images") or []
        img = imgs[0].get("url_fullxfull") if imgs else None
        out.append({
            "listing_id": lid,
            "shop_id": l.get("shop_id"),
            "title": title,
            "tags": l.get("tags") or [],
            "url": (l.get("url") or "").split("?")[0],
            "image": img,
            "favorites": fav,
            "views": views,
            "age_days": round(age),
            "fav_per_day": round(fpd, 3),
            "views_per_day": round(vpd, 2),
            # p25-normalize kombine skor: iki sinyali eşit ağırlıkla birleştirir
            "bs_score": round(fpd / 0.59 + vpd / 7.9, 2),
        })
    out.sort(key=lambda x: -x["bs_score"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", default="frame tv art")
    ap.add_argument("--pages", type=int, default=3, help="100'erlik sayfa sayısı")
    args = ap.parse_args()

    print(f"Pazar taranıyor: '{args.keyword}' ({args.pages} sayfa)…")
    listings = fetch_market(args.keyword, args.pages)
    print(f"  {len(listings)} ilan tarandı.")
    themes = trending_themes(listings)
    OUT.write_text(json.dumps(themes, ensure_ascii=False, indent=2))
    print(f"Yazıldı: {OUT.relative_to(ROOT)}  ({len(themes)} tema)\n")
    print("— En çok yükselen 15 tema (favori-ağırlıklı) —")
    for i, t in enumerate(themes[:15], 1):
        print(f"{i:>2}. {t['theme']:<18} skor {t['score']:>6}  ({t['listings']} ilan)")

    # --- BESTSELLER TARAMASI (taklit hedefleri) ---
    print("\nBestseller taraması (çoklu sorgu)…")
    all_listings = {l.get("listing_id"): l for l in listings}
    for q in BS_QUERIES:
        if q == args.keyword:
            continue
        try:
            batch = fetch_market(q, pages=2)
            for l in batch:
                all_listings.setdefault(l.get("listing_id"), l)
            print(f"  '{q}': +{len(batch)} ilan")
        except Exception as e:  # noqa: BLE001
            print(f"  '{q}' atlandı: {str(e)[:60]}")
    # Doğrulanmış rozetliler (browser bestseller sayfasından parse edilen
    # listing_id'ler) — havuza her taramada dahil edilir; formül eşiğinden
    # geçemeyenler (sezonu geçmiş vb.) elenmiş olur.
    c = EtsyClient()
    gt_path = ROOT / "data" / "ground_truth_bs_ids.json"
    if gt_path.exists():
        try:
            gt_ids = json.loads(gt_path.read_text())
            got = c._request("GET", "/listings/batch", params={
                "listing_ids": ",".join(map(str, gt_ids)), "includes": "Images"})
            n_new = 0
            for l in got.get("results", []):
                if l.get("listing_id") not in all_listings:
                    all_listings[l["listing_id"]] = l
                    n_new += 1
            print(f"  doğrulanmış rozetli havuzu: +{n_new} ilan")
        except Exception as e:  # noqa: BLE001
            print(f"  (doğrulanmış havuz atlandı: {str(e)[:60]})")

    def _fill_shop_names(items):
        for b in items[:25]:
            if b.get("shop_id"):
                try:
                    b["shop_name"] = c._request(
                        "GET", f"/shops/{b['shop_id']}").get("shop_name", "")
                except Exception:  # noqa: BLE001
                    b["shop_name"] = ""

    bestsellers = extract_bestsellers(list(all_listings.values()))
    _fill_shop_names(bestsellers)
    BS_OUT.write_text(json.dumps(bestsellers, ensure_ascii=False, indent=2))
    print(f"Yazıldı: {BS_OUT.relative_to(ROOT)}  ({len(bestsellers)} bestseller)\n")
    print("— En hızlı satan 10 (bs_score) —")
    for i, b in enumerate(bestsellers[:10], 1):
        print(f"{i:>2}. skor {b['bs_score']:>6}  fav/g {b['fav_per_day']:>5}  "
              f"view/g {b['views_per_day']:>7}  {b['title'][:55]}")

    # --- POSTER PAZARI TARAMASI (ayrı havuz) ---
    print("\nPoster pazarı taranıyor…")
    poster_listings: dict = {}
    for q in POSTER_QUERIES:
        try:
            batch = fetch_market(q, pages=2)
            for l in batch:
                poster_listings.setdefault(l.get("listing_id"), l)
            print(f"  '{q}': +{len(batch)} ilan")
        except Exception as e:  # noqa: BLE001
            print(f"  '{q}' atlandı: {str(e)[:60]}")
    posters = [l for l in poster_listings.values()
               if not any(w in (l.get("title") or "").lower() for w in _TV_WORDS)]
    poster_bs = extract_bestsellers(posters)
    _fill_shop_names(poster_bs)
    BS_POSTER_OUT.write_text(json.dumps(poster_bs, ensure_ascii=False, indent=2))
    print(f"Yazıldı: {BS_POSTER_OUT.relative_to(ROOT)}  ({len(poster_bs)} poster bestseller)")
    for i, b in enumerate(poster_bs[:8], 1):
        print(f"{i:>2}. skor {b['bs_score']:>6}  fav/g {b['fav_per_day']:>5}  "
              f"view/g {b['views_per_day']:>7}  {b['title'][:55]}")


if __name__ == "__main__":
    main()
