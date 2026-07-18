"""
product_ideas.py — Otomasyonun "beyni": her sabah üretilecek ürünlere karar verir.

Girdi (lokal, dış bağımlılık YOK):
  data/opportunity_keywords.csv  — FIRSAT + RAKİP AÇIĞI (merge_erank çıktısı)
  data/listings.json             — kendi ilanlarım (neyi zaten kapsıyorum)

Her ürün fikri için üretir:
  * theme            — az kapsanan, talep-kanıtlı tema (ör. "wildflower", "cottage")
  * art_prompt       — Flux/fal.ai için görsel prompt'u (16:9, 4K, Frame TV)
  * title            — Etsy başlığı (≤140, güçlü keyword öne)
  * tags             — 13 çok-kelimeli tag (≤20 kr, benzersiz)
  * description      — keyword ilk cümlede + dijital indirme detayı

Çıktı:
  reports/product_ideas.md   — okunabilir
  data/product_ideas.json    — bir sonraki adım (görsel+mockup+taslak) bunu okur

Kullanım:
    python product_ideas.py            # 3 fikir
    python product_ideas.py --count 5
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from action_plan import STOP, tokens  # tema kelimesi çıkarımı için

ROOT = Path(__file__).resolve().parent
OPP_CSV = ROOT / "data" / "opportunity_keywords.csv"
LISTINGS_JSON = ROOT / "data" / "listings.json"
REPORT = ROOT / "reports" / "product_ideas.md"
OUT_JSON = ROOT / "data" / "product_ideas.json"
# Daha önce üretilen temalar (tema-tekrar koruması) — generate_products doldurur.
PRODUCED_PATH = ROOT / "data" / "produced_themes.json"
# Canlı yükselen temalar — market_research.py (Etsy API) doldurur.
TRENDING_PATH = ROOT / "data" / "trending_themes.json"
# Bestseller taklit hedefleri — market_research.py doldurur.
BESTSELLERS_PATH = ROOT / "data" / "bestsellers.json"


def load_produced() -> set[str]:
    if PRODUCED_PATH.exists():
        return {e["theme"] for e in json.loads(PRODUCED_PATH.read_text())}
    return set()


def load_produced_listing_ids() -> set[int]:
    """Daha önce taklit edilen bestseller listing_id'leri (tekrar üretme)."""
    if PRODUCED_PATH.exists():
        return {e["source_listing_id"] for e in json.loads(PRODUCED_PATH.read_text())
                if e.get("source_listing_id")}
    return set()


def load_trending() -> list[dict]:
    """market_research çıktısı: [{theme, score, listings, keywords:[...]}]."""
    if TRENDING_PATH.exists():
        return json.loads(TRENDING_PATH.read_text())
    return []


_BUNDLE = ("set of", "collection", "bundle", "all-in-one", "5000", "40000",
          "10000", "200+", "+5000", "lifetime", "complete store")


def fetch_reference(theme: str) -> dict | None:
    """
    Tema için Etsy'de en yüksek favorili KAZANAN tekil ilanı bul.
    Hem OpenAI görsel-benchmark'ı hem izlenebilirlik (provenance) için kullanılır.
    Her tema (trend olsun olmasın) bir kazanandan benchmark alsın diye.
    """
    try:
        from etsy_client import EtsyClient
        c = EtsyClient()
        # 1) Ara — kazanan tekil ilanı bul (search endpoint görsel DÖNDÜRMEZ).
        page = c._request("GET", "/listings/active", params={
            "keywords": f"{theme} frame tv art", "sort_on": "score",
            "sort_order": "down", "limit": 25})
        best = None
        for l in page.get("results", []):
            title = l.get("title") or ""
            if any(b in title.lower() for b in _BUNDLE):
                continue
            if _is_blocked(title):  # markalı/telifli kazananı referans ALMA
                continue
            if best is None or (l.get("num_favorers") or 0) > (best.get("num_favorers") or 0):
                best = l
        if not best:
            return None
        # 2) O ilanın görselini AYRI çağrıyla al (getListing images döndürür).
        img = None
        try:
            d = c._request("GET", f"/listings/{best['listing_id']}",
                           params={"includes": "Images"})
            imgs = d.get("images") or []
            if imgs:
                img = imgs[0].get("url_fullxfull") or imgs[0].get("url_570xN")
        except Exception:  # noqa: BLE001
            pass
        return {
            "title": best.get("title"),
            "url": (best.get("url") or "").split("?")[0],
            "favorites": best.get("num_favorers"),
            "views": best.get("views"),
            "image": img,
        }
    except Exception:  # noqa: BLE001
        return None

# Tema OLAMAYACAK jenerik kelimeler (STOP'a ek).
THEME_STOP = STOP | {
    "downloadable", "gallery", "printable", "bedroom", "living", "room",
    "house", "houses", "print", "prints", "vintage", "modern", "neutral",
    "oil", "painting", "wall", "decor", "style", "scene", "artwork",
    "frames", "canvas", "wallpaper", "background", "screensaver",
    "downloads", "tvs", "hd", "uhd",
    # sanat-dışı / gürültü konseptler
    "png", "svg", "jpeg", "chart", "display", "numbers", "number", "sticker",
    "decal", "mockup", "logo", "template", "bundle", "clipart",
}

# TELİF/MARKA GUARD (Sentinel): bu terimlerden birini içeren keyword komple
# atlanır — marka, tescilli isim, gerçek kişi, lisanslı karakter Etsy'de yasak.
# Kullanıcı buraya ekleme yapabilir.
BRAND_BLOCKLIST = {
    "porsche", "ferrari", "lamborghini", "mercedes", "bmw", "audi", "tesla",
    "nike", "adidas", "puma", "jordan", "supreme", "gucci", "chanel", "prada",
    "versace", "louis vuitton", "dior", "burberry",
    "disney", "pixar", "marvel", "dc comics", "star wars", "harry potter",
    "pokemon", "nintendo", "mario", "sonic", "hello kitty", "barbie",
    "coca cola", "pepsi", "starbucks", "apple", "google",
    "michael jackson", "taylor swift", "beyonce", "elvis", "marilyn monroe",
    "kobe", "messi", "ronaldo", "jordan", "nfl", "nba", "fifa", "world cup",
    "olympics", "grammy", "oscar",
}


def _is_blocked(keyword: str) -> bool:
    kw = keyword.lower()
    return any(b in kw for b in BRAND_BLOCKLIST)

# Her Frame TV ürününe uyan güvenli tag havuzu (tema tag'i az kalırsa doldurur).
EVERGREEN_TAGS = [
    "Samsung Frame TV", "Frame TV Art", "Digital Download", "TV Wall Art",
    "Samsung TV Art", "Digital Wall Art", "Art for Frame TV", "4K TV Art",
    "Instant Download", "TV Screensaver", "Frame TV Digital", "Home TV Decor",
]

# Görsel stil varyasyonları — vintage yağlı boya / fine-art estetiği hedeflenir.
STYLES = [
    "in the style of a 19th century European oil painting",
    "antique impressionist oil painting",
    "Dutch Golden Age fine art painting",
    "romantic vintage landscape oil painting",
    "old master oil painting on aged canvas",
]
LIGHTS = ["soft atmospheric light", "moody diffused daylight",
          "warm muted golden light", "misty morning haze"]


def _norm(s: str) -> str:
    return s.strip().lower()


def load_opportunities() -> list[dict]:
    if not OPP_CSV.exists():
        raise SystemExit(f"{OPP_CSV.name} yok. Önce: python merge_erank.py")
    rows = []
    with open(OPP_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            def num(k):
                v = (r.get(k) or "").strip()
                try:
                    return float(v)
                except ValueError:
                    return 0.0
            rows.append({
                "keyword": r["keyword"].strip(),
                "avg_searches": num("avg_searches"),
                "competitor_est_sales": num("competitor_est_sales"),
                "competitor_listings": num("competitor_listings"),
                "value": num("avg_searches") + num("competitor_est_sales"),
            })
    return rows


def my_theme_coverage() -> dict[str, int]:
    """Her tema kelimesini kaç ilanımda kullanıyorum (az = fırsat)."""
    cov: dict[str, int] = defaultdict(int)
    if not LISTINGS_JSON.exists():
        return cov
    for rec in json.loads(LISTINGS_JSON.read_text()):
        seen = set()
        for t in rec.get("tags") or []:
            for tok in tokens(t) - THEME_STOP:
                seen.add(tok)
        for tok in seen:
            cov[tok] += 1
    return cov


def _upcoming_holiday_themes() -> list[dict]:
    """Yaklaşan tatil/bayram/kutlama temalarını döndür (60 gün penceresi)."""
    from datetime import datetime, timedelta
    today = datetime.now()
    year = today.year

    HOLIDAYS = [
        (f"{year}-01-01", "new year celebration", ["new year frame tv art", "happy new year decor", "new year wall art", "new year digital art"]),
        (f"{year}-02-14", "valentines day romantic", ["valentines frame tv art", "romantic wall art", "love decor", "valentines day gift"]),
        (f"{year}-03-17", "st patricks day clover", ["st patricks day art", "shamrock decor", "irish wall art", "green clover art"]),
        (f"{year}-03-20", "nowruz persian spring", ["nowruz frame tv art", "persian new year", "haft sin decor", "spring equinox art"]),
        (f"{year}-04-12", "easter spring bunny", ["easter frame tv art", "easter bunny art", "spring decor", "easter egg art"]),
        (f"{year}-05-10", "mothers day floral", ["mothers day gift art", "mothers day frame tv", "floral gift art", "mom wall art"]),
        (f"{year}-06-21", "fathers day masculine", ["fathers day gift art", "fathers day frame tv", "gift for dad art", "masculine wall art"]),
        (f"{year}-07-04", "independence day patriotic", ["4th of july art", "patriotic frame tv", "american flag art", "independence day"]),
        (f"{year}-09-07", "labor day american", ["labor day decor", "labor day frame tv", "american holiday art", "patriotic wall art"]),
        (f"{year}-09-12", "rosh hashanah jewish", ["rosh hashanah art", "jewish new year", "shana tova decor", "jewish holiday art"]),
        (f"{year}-10-20", "diwali festival lights", ["diwali frame tv art", "diwali decor", "festival of lights", "diwali wall art"]),
        (f"{year}-10-31", "halloween spooky", ["halloween frame tv art", "spooky decor", "halloween wall art", "gothic halloween"]),
        (f"{year}-11-26", "thanksgiving harvest", ["thanksgiving frame tv", "thanksgiving decor", "harvest wall art", "fall thanksgiving"]),
        (f"{year}-12-15", "hanukkah menorah", ["hanukkah frame tv art", "hanukkah decor", "menorah wall art", "jewish holiday art"]),
        (f"{year}-12-25", "christmas winter cozy", ["christmas frame tv art", "christmas decor", "cozy christmas", "holiday wall art"]),
    ]

    upcoming = []
    for date_str, theme, keywords in HOLIDAYS:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        days_until = (dt - today).days
        if -3 <= days_until <= 60:
            kw_dicts = [{"keyword": k, "avg_searches": 500, "competitor_est_sales": 0,
                         "competitor_listings": 0, "value": 800} for k in keywords]
            upcoming.append({
                "theme": theme.split()[0],
                "full_theme": theme,
                "days_until": days_until,
                "keywords": kw_dicts,
                "boost": max(1000, 3000 - days_until * 30),
            })
    return upcoming


def pick_themes(opps: list[dict], count: int) -> list[dict]:
    """Az kapsanan + talep-kanıtlı temaları seç. Yaklaşan tatiller öncelikli."""
    coverage = my_theme_coverage()
    produced = load_produced()
    theme_val: dict[str, float] = defaultdict(float)
    theme_kws: dict[str, list[dict]] = defaultdict(list)
    for o in opps:
        if _is_blocked(o["keyword"]):
            continue
        toks = tokens(o["keyword"]) - THEME_STOP
        if not toks:
            continue
        theme = max(toks, key=len)
        theme_val[theme] += o["value"]
        theme_kws[theme].append(o)

    # --- CANLI TREND ENJEKSİYONU ---
    theme_refs: dict[str, list] = {}
    for entry in load_trending():
        th = entry["theme"]
        if _is_blocked(th) or th in THEME_STOP or not entry.get("keywords"):
            continue
        theme_val[th] += entry["score"]
        theme_kws[th].extend(entry["keywords"])
        theme_refs[th] = entry.get("reference_images", [])

    # --- YAKLAŞAN TATİL/BAYRAM ENJEKSİYONU ---
    holiday_themes = _upcoming_holiday_themes()
    for h in holiday_themes:
        th = h["theme"]
        theme_val[th] += h["boost"]
        theme_kws[th].extend(h["keywords"])
        print(f"  📅 Tatil enjeksiyonu: {h['full_theme']} ({h['days_until']} gün, boost={h['boost']})")

    scored = []
    for theme, val in theme_val.items():
        cov = coverage.get(theme, 0)
        score = val / (1 + cov)
        scored.append((score, theme, cov, val))
    scored.sort(reverse=True)

    chosen = []
    for score, theme, cov, val in scored:
        if len(chosen) >= count:
            break
        if theme in produced:
            continue
        if any(
            theme.startswith(c["theme"][:5]) or c["theme"].startswith(theme[:5])
            or theme in c["theme"] or c["theme"] in theme
            for c in chosen
        ):
            continue
        chosen.append({"theme": theme, "coverage": cov, "value": round(val),
                       "keywords": sorted(theme_kws[theme],
                                          key=lambda x: -x["value"]),
                       "reference_images": theme_refs.get(theme, [])})
    return chosen


def build_tags(theme_row: dict) -> list[str]:
    """13 benzersiz, ≤20 kr tag: önce tema keyword'leri, sonra evergreen."""
    tags, seen = [], set()

    def add(t: str):
        t = re.sub(r"\s+", " ", t).strip()[:20]
        if t and _norm(t) not in seen:
            tags.append(t)
            seen.add(_norm(t))

    # Tema keyword'leri (değere göre) — çekirdek staple'lara 3 slot bırak.
    for o in theme_row["keywords"]:
        if len(tags) >= 10:
            break
        add(o["keyword"])
    # Evergreen havuzuyla 13'e tamamla (güvenli, her üründe geçerli).
    for e in EVERGREEN_TAGS:
        if len(tags) >= 13:
            break
        add(e)
    return tags[:13]


def build_title(theme_row: dict, tags: list[str]) -> str:
    """≤140, güçlü keyword öne; okunur bir başlık."""
    # En yüksek aramalı keyword'ü öne al (tema zaten içinde geçer, tekrar etme).
    lead = max(theme_row["keywords"], key=lambda x: x["avg_searches"])["keyword"]
    parts = [
        f"{lead.title()} Samsung Frame TV Art",
        "Digital Download",
        "Vintage Wall Art for TV",
    ]
    title = " | ".join(parts)
    if len(title) > 140:
        title = title[:140].rsplit("|", 1)[0].strip(" |")
    return title


def build_description(theme_row: dict, title: str) -> str:
    theme = theme_row["theme"]
    lead = max(theme_row["keywords"], key=lambda x: x["avg_searches"])["keyword"]
    kws = [o["keyword"] for o in theme_row["keywords"][:6]]
    kw_line = ", ".join(kws)
    return (
        f"{lead.title()} for your Samsung Frame TV — an elegant {theme}-inspired "
        "vintage oil painting that transforms your TV into a piece of fine art. "
        "Designed to bring warmth, character, and a timeless gallery feel to your "
        "living room, bedroom, or entryway in just seconds.\n\n"
        "Inspired by classic museum paintings, this piece features rich brushwork, "
        "a moody yet cozy palette, and a painterly texture that looks stunning on "
        "the Frame TV's matte display.\n\n"
        "──────────────────────\n"
        "★ INSTANT DIGITAL DOWNLOAD\n"
        "No physical item will be shipped. You'll receive the file(s) instantly "
        "after purchase.\n\n"
        "★ WHAT YOU GET\n"
        "• 1 high-resolution file in stunning 4K (3840 × 2160 px)\n"
        "• 16:9 aspect ratio — a perfect fit for Samsung The Frame TV\n"
        "• Crisp, gallery-quality detail with true-to-art color\n\n"
        "★ HOW TO USE\n"
        "1) Purchase and download the file to your phone or computer.\n"
        "2) Open the SmartThings app (or USB) and upload to your Frame TV.\n"
        "3) Set it as your Art Mode background and enjoy!\n\n"
        "★ WORKS WITH\n"
        "Samsung The Frame TV (all sizes) and most digital photo frames that "
        "support 16:9 images.\n\n"
        "──────────────────────\n"
        f"Perfect for lovers of {kw_line}.\n\n"
        "★ NOTE\n"
        "Colors may vary slightly depending on your screen. This is a digital "
        "product for personal use only — no physical item, frame, or TV included. "
        "Due to the instant-download nature, this purchase is non-refundable."
    )


def build_art_prompt(theme_row: dict) -> str:
    theme = theme_row["theme"]
    # Tema kelimelerinden görsel ipuçları topla.
    hints = []
    for o in theme_row["keywords"][:6]:
        hints += [t for t in tokens(o["keyword"]) - THEME_STOP if t != theme]
    hint_txt = ", ".join(sorted(set(hints))[:4])
    style = random.choice(STYLES)
    light = random.choice(LIGHTS)
    extra = f", featuring {hint_txt}" if hint_txt else ""
    return (
        f"Vintage oil painting of a {theme} scene{extra}, {style}, {light}, "
        "textured visible brushstrokes, muted moody color palette, aged canvas texture, "
        "classical composition, fine art, museum quality, richly detailed, "
        "16:9 aspect ratio, wall art for a Samsung Frame TV. "
        "No text, no watermark, no frame, no border, no signature."
    )


# --- SEZON BEKÇİSİ ---------------------------------------------------------
# Tatile bağlı ürünler: bayram GEÇTİYSE atla, YAKLAŞIYORSA öne çek.
# Tarihe-özgü keyword'ler o güne kilitli; jenerik olanlar (patriotic vb.)
# en yakın uygun bayrama bakar. Pencere: bayramdan 75 gün öncesi → bayram günü.
_HOLIDAY_KEYWORDS: list[tuple[str, list[str], list[tuple[int, int]]]] = [
    # (ad, keyword'ler, [(ay, gün), ...] — birden çok tarih = en yakını geçerli)
    ("new year",      ["new year", "happy new year"],                      [(1, 1)]),
    ("valentines",    ["valentine"],                                       [(2, 14)]),
    ("mardi gras",    ["mardi gras", "bourbon street"],                    [(2, 17)]),
    ("chinese ny",    ["chinese new year", "lunar new year"],              [(2, 10)]),
    ("st patricks",   ["st patrick", "shamrock", "irish holiday"],         [(3, 17)]),
    ("nowruz",        ["nowruz", "persian new year"],                      [(3, 20)]),
    ("easter",        ["easter"],                                          [(4, 5)]),
    ("mothers day",   ["mother's day", "mothers day"],                     [(5, 10)]),
    ("memorial day",  ["memorial day"],                                    [(5, 25)]),
    ("fathers day",   ["father's day", "fathers day"],                     [(6, 21)]),
    ("4th of july",   ["4th of july", "fourth of july", "july 4",
                       "independence day"],                               [(7, 4)]),
    ("labor day",     ["labor day"],                                       [(9, 7)]),
    ("rosh hashanah", ["rosh hashanah", "shana tova"],                     [(9, 15)]),
    ("halloween",     ["halloween", "spooky", "jack o lantern"],           [(10, 31)]),
    ("diwali",        ["diwali"],                                          [(10, 20)]),
    ("day of dead",   ["dia de los muertos", "day of the dead"],           [(11, 1)]),
    ("thanksgiving",  ["thanksgiving"],                                    [(11, 26)]),
    ("hanukkah",      ["hanukkah", "menorah"],                             [(12, 15)]),
    ("christmas",     ["christmas", "santa claus", "xmas"],                [(12, 25)]),
    ("kwanzaa",       ["kwanzaa"],                                         [(12, 26)]),
    # Jenerik vatansever — en yakın vatansever bayrama (Memorial/4Temmuz/Labor)
    ("patriotic",     ["patriotic", "american flag", "americana",
                       "stars and stripes"],                              [(5, 25), (7, 4), (9, 7)]),
]
_SEASON_LEAD_DAYS = 75   # bayramdan en fazla bu kadar gün önce üretmeye başla


def holiday_season_status(title: str) -> tuple[str, str, int] | None:
    """
    TITLE tatile bağlıysa: ("keep"|"skip", bayram_adı, kalan_gün); değilse None.
    Yalnızca title'a bakılır (tag'ler gürültülü: evergreen ürünler "christmas
    gift" gibi tag'ler taşıyabilir). Tarihe-ÖZGÜ bayram adı (örn "4th of July")
    jenerik eşleşmeden (örn "patriotic") ÖNCELİKLİDİR: title'ında geçmiş bir
    bayramın adı yazan ürün, jenerik kelimeyle bir sonraki bayrama bağlanamaz.
    """
    from datetime import datetime
    low = title.lower()
    today = datetime.now()

    def next_days(dates: list[tuple[int, int]]) -> int:
        min_days = 999
        for (m, d) in dates:
            for year in (today.year, today.year + 1):
                try:
                    dt = datetime(year, m, d)
                except ValueError:
                    continue
                delta = (dt - today).days
                if 0 <= delta < min_days:
                    min_days = delta
        return min_days

    specific_best, generic_best = None, None
    for name, kws, dates in _HOLIDAY_KEYWORDS:
        if not any(k in low for k in kws):
            continue
        days = next_days(dates)
        if name == "patriotic":   # tek jenerik giriş
            if generic_best is None or days < generic_best[1]:
                generic_best = (name, days)
        else:
            if specific_best is None or days < specific_best[1]:
                specific_best = (name, days)

    best = specific_best or generic_best   # özgül olan her zaman kazanır
    if best is None:
        return None
    name, days = best
    return ("keep" if days <= _SEASON_LEAD_DAYS else "skip", name, days)


def _clean_copied_title(title: str) -> str:
    """Rakip title'ını kopyalarken SKU kodu / dükkan-imzası kalıntılarını sil."""
    import html
    t = html.unescape(title)                                     # &quot; → "
    t = re.sub(r"\|?\s*#?[A-Z]{1,4}\d{1,6}[-\d]*\s*$", "", t)   # |TV629, #FF2, TS108
    t = re.sub(r'["\'“”]\s*[A-Z]{2,8}\s*\d{0,4}\s*["\'“”]', "", t)  # "TEX 4" seri adı
    t = re.sub(r"\|\s*\|", "|", t)                               # boşalan çift ayraç
    t = re.sub(r",\s*\|", " |", t)                               # ", |" kalıntısı
    t = re.sub(r"\s+", " ", t).strip(" |,–-")
    return t[:140]


def _copied_tags(tags: list[str], shop_name: str = "") -> list[str]:
    """Rakip tag'lerini kopyala: sanitize + blocklist + dükkan-adı filtresi +
    13'e evergreen ile tamamla."""
    out, seen = [], set()
    shop_key = _norm(shop_name).replace(" ", "")

    def add(t: str):
        t = re.sub(r"[^0-9A-Za-zÀ-ÿ ]", " ", str(t))
        t = re.sub(r"\s+", " ", t).strip()[:20]
        if not t or _norm(t) in seen or _is_blocked(t):
            return
        # Rakibin kendi dükkan adını tag olarak KOPYALAMA (marka ihlali + işe yaramaz)
        if shop_key and _norm(t).replace(" ", "") == shop_key:
            return
        out.append(t)
        seen.add(_norm(t))

    for t in tags:
        if len(out) >= 13:
            break
        add(t)
    for e in EVERGREEN_TAGS:
        if len(out) >= 13:
            break
        add(e)
    return out[:13]


def _my_title_starts() -> set[str]:
    """Kendi ilanlarımın normalize edilmiş title başlangıçları (çakışma kontrolü)."""
    starts = set()
    if LISTINGS_JSON.exists():
        for rec in json.loads(LISTINGS_JSON.read_text()):
            starts.add(_norm(rec.get("title", ""))[:40])
    return starts


def bestseller_ideas(count: int) -> list[dict]:
    """
    data/bestsellers.json'dan (formül: fav/gün>=0.5 VEYA view/gün>=7) en hızlı
    satan, henüz taklit edilmemiş ilanları seç. Görsel benzer üretilir; title +
    13 tag rakipten kopyalanır (SKU/marka temizliğiyle).
    """
    if not BESTSELLERS_PATH.exists():
        return []
    bestsellers = json.loads(BESTSELLERS_PATH.read_text())
    produced_ids = load_produced_listing_ids()
    my_starts = _my_title_starts()

    # SEZON BEKÇİSİ: geçmiş bayram ürünlerini ele, yaklaşanları öne çek.
    pool = []
    for b in bestsellers:
        season = holiday_season_status(b["title"])
        score = b["bs_score"]
        if season:
            status, hname, days = season
            if status == "skip":
                print(f"  ⏭  sezon dışı ({hname}, {days} gün sonra): {b['title'][:50]}")
                continue
            # Yaklaşan bayram: ne kadar yakınsa o kadar güçlü boost (1.0→1.5x)
            score *= 1.0 + 0.5 * (1 - days / _SEASON_LEAD_DAYS)
            print(f"  📅 yaklaşan bayram ({hname}, {days} gün): {b['title'][:50]}")
        pool.append((score, b))
    pool.sort(key=lambda x: -x[0])

    ideas = []
    for _score, b in pool:
        if len(ideas) >= count:
            break
        if b["listing_id"] in produced_ids:
            continue
        if _is_blocked(b["title"]):
            continue
        if _norm(b["title"])[:40] in my_starts:   # zaten bende varsa atla
            continue
        idea = make_copy_idea(b)
        if idea:
            ideas.append(idea)
    return ideas


def make_copy_idea(b: dict) -> dict | None:
    """Tek bir bestseller kaydından taklit fikri üret (title+tag kopyalı)."""
    title = _clean_copied_title(b["title"])
    tags = _copied_tags(b.get("tags") or [], b.get("shop_name", ""))
    if len(tags) < 8:      # tag'i çekilememiş ilan — sağlıklı taklit olmaz
        return None

    # Tema slug'ı: title'ın ilk anlamlı kelimeleri (üretim klasörü + kayıt).
    words = [w for w in tokens(title) - THEME_STOP][:2]
    theme = " ".join(words) if words else f"bs{b['listing_id']}"

    # Görsel prompt: OpenAI benchmark (referans görselden), yoksa şablon.
    art_prompt = (
        f"Vintage oil painting recreating the subject of: {title}. "
        "Textured visible brushstrokes, muted moody palette, museum quality, "
        "16:9. No text, no watermark, no frame, no border, no signature."
    )
    description = build_description(
        {"theme": theme, "keywords": [
            {"keyword": t, "avg_searches": 1} for t in tags]}, title)
    brief_source = "template"
    try:
        from ai_brief import generate_brief
        from ref_images import collect_reference_images, scrape_listing_description
        ref_imgs = collect_reference_images(
            b["listing_id"], b.get("url", ""), b.get("image", ""))
        ref_desc = scrape_listing_description(b.get("url", ""))
        print(f"  referans görsel: {len(ref_imgs)} adet, "
              f"firecrawl açıklama: {len(ref_desc)} kr")
        brief = generate_brief(theme, tags[:12], ref_imgs,
                               reference_title=b["title"],
                               reference_description=ref_desc)
        art_prompt = brief["art_prompt"]
        description = brief["description"] or description
        brief_source = "openai"
    except Exception as e:  # noqa: BLE001
        print(f"  (OpenAI brief atlandı [{theme}]: {str(e)[:70]} → şablon)")

    # Typography/text ürünlerinde "no text" talimatı çelişir — kaldır.
    if re.search(r"typography|lettering|happy birthday|text screen", title, re.I):
        art_prompt = re.sub(r"no text,\s*", "", art_prompt, flags=re.I)

    # Referans DÜZ teknikse (pastel/guaj/suluboya/çizim) impasto ekini kapat.
    flat = re.search(r"pastel|chalk|gouache|watercolou?r|crayon|flat|matte|"
                     r"\bink\b|sketch|drawing|line art|minimal",
                     art_prompt, re.I)

    return {
        "apply_texture": not flat,
        "theme": theme,
        "source_listing_id": b["listing_id"],
        "my_coverage": 0,
        "demand_value": b["bs_score"],
        "market_source": "BESTSELLER Taklit",
        "trend_score": None,
        "why": (f"Bestseller formülü: fav/gün {b['fav_per_day']}, "
                f"view/gün {b['views_per_day']}, yaş {b['age_days']}g "
                f"(bs_score {b['bs_score']}) · title+tag kopyalandı."),
        "reference": {"title": b["title"], "url": b["url"],
                      "favorites": b["favorites"], "views": b["views"],
                      "image": b.get("image")},
        "brief_source": brief_source,
        "art_prompt": art_prompt,
        "title": title,                      # KOPYA (temizlenmiş)
        "title_length": len(title),
        "tags": tags,                        # KOPYA (13 tag)
        "description": description,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3, help="Kaç ürün fikri.")
    ap.add_argument("--seed", type=int, default=None, help="Tekrarlanabilir çıktı.")
    args = ap.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    # --- 1) BESTSELLER TAKLİT (öncelikli): gerçekten satanları kopyala ---
    ideas = bestseller_ideas(args.count)
    if ideas:
        print(f"Bestseller taklit: {len(ideas)} fikir "
              f"({', '.join(i['theme'] for i in ideas)})")
    remaining = args.count - len(ideas)

    # --- 2) Kalan slotlar: eski akış (opportunity + trend temaları) ---
    opps = load_opportunities()
    themes = pick_themes(opps, remaining) if remaining > 0 else []

    # Kaynak/skor: tema canlı trendde mi, skoru ne?
    trend_map = {e["theme"]: e["score"] for e in load_trending()}
    for row in themes:
        theme = row["theme"]
        # Her temaya KAZANAN referans ilan (benchmark + iz) — trend olsun olmasın
        ref = fetch_reference(theme)
        ref_imgs = [ref["image"]] if ref and ref.get("image") else row.get("reference_images", [])

        in_trend = theme in trend_map
        market_source = "Canlı Trend" if in_trend else "Rakip/Opportunity"
        trend_score = trend_map.get(theme)
        why = (f"Canlı trendde yükseliyor (skor {trend_score}) · bende {row['coverage']} "
               "ilan · az kapsadığım için seçildi."
               if in_trend else
               f"Rakip/eRank talebi (opportunity, değer {row['value']}) · bende "
               f"{row['coverage']} ilan · trend değil ama kanıtlanmış boşluk.")

        # Şablon (yedek) çıktısı
        tags = build_tags(row)
        title = build_title(row, tags)
        art_prompt = build_art_prompt(row)
        description = build_description(row, title)
        brief_source = "template"
        try:
            from ai_brief import generate_brief
            kw = [o["keyword"] for o in row["keywords"][:12]]
            ref_title = (ref or {}).get("title", "")
            brief = generate_brief(theme, kw, ref_imgs, reference_title=ref_title)
            title, tags = brief["title"], brief["tags"]
            art_prompt = brief["art_prompt"]
            description = brief["description"] or description
            brief_source = "openai"
        except Exception as e:  # noqa: BLE001
            print(f"  (OpenAI brief atlandı [{theme}]: {str(e)[:70]} → şablon)")

        ideas.append({
            "theme": theme,
            "my_coverage": row["coverage"],
            "demand_value": row["value"],
            "market_source": market_source,   # Canlı Trend / Rakip-Opportunity
            "trend_score": trend_score,
            "why": why,
            "reference": ref,                 # {title,url,favorites,image} | None
            "brief_source": brief_source,      # openai / template
            "art_prompt": art_prompt,
            "title": title,
            "title_length": len(title),
            "tags": tags,
            "description": description,
        })

    OUT_JSON.write_text(json.dumps(ideas, ensure_ascii=False, indent=2))

    L = [f"# Ürün Fikirleri ({len(ideas)})", "",
         "*Otomasyonun 'beyin' çıktısı. Kaynak: `data/opportunity_keywords.csv` "
         "+ `data/listings.json`. Sonraki adım (görsel+mockup+taslak) "
         "`data/product_ideas.json`'ı okuyacak.*", ""]
    for i, idea in enumerate(ideas, 1):
        L += [
            f"## {i}. Tema: **{idea['theme']}** "
            f"(bende {idea['my_coverage']} ilan · talep-değeri {idea['demand_value']})",
            "",
            f"**🎨 Görsel prompt (Flux):**",
            f"> {idea['art_prompt']}", "",
            f"**📝 Başlık** ({idea['title_length']} kr):",
            f"> {idea['title']}", "",
            f"**🏷️ Tag'ler (13):** {', '.join('`'+t+'`' for t in idea['tags'])}", "",
            f"**📄 Açıklama:**", "```", idea["description"], "```", "",
        ]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(L))

    print(f"Rapor : {REPORT.relative_to(ROOT)}")
    print(f"JSON  : {OUT_JSON.relative_to(ROOT)}  ({len(ideas)} fikir)\n")
    for i, idea in enumerate(ideas, 1):
        print(f"{i}. {idea['theme']:<14} → {idea['title'][:60]}")


if __name__ == "__main__":
    main()
