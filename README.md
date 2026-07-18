# Lumiaerestudio — Etsy SEO Analiz Pipeline

Etsy mağazasının ilanlarını **salt-okunur** çekip SEO analizi yapan pipeline.
Hiçbir script write (updateListing vb.) API'si çağırmaz.

## Kurulum

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # sonra .env'i doldur
```

`.env` içine:
- `ETSY_API_KEY` — Etsy dev konsolundaki keystring
- `ETSY_REDIRECT_URI` — uygulamada **kayıtlı** callback (ör. `http://localhost:3003/callback`)

## Adım 1 — OAuth + istemci  ✅ hazır (test bekliyor)

```bash
python authorize.py        # bir kez: PKCE akışı, tarayıcıda izin ver → .tokens.json
python etsy_client.py      # bağlantı testi: shop + ilan sayısı basar
```

- `authorize.py` — OAuth2 PKCE, tokenları `.tokens.json`'a (0600) yazar.
- `etsy_client.py` — `get_shop()`, `get_all_listings()` (oto-pagination),
  `get_listing_images()`. Token'ı otomatik yeniler, 5 QPS throttle + 429 backoff.

Secret'lar (`.env`, `.tokens.json`) `.gitignore`'da; commit edilmez.

## Adım 2 — veri çekme  ✅

```bash
python fetch_listings.py            # cache'den okur
python fetch_listings.py --refresh  # API'den taze çeker
```
Çıktı: `data/listings.json` (tags liste) + `data/listings.csv`. 180 aktif ilan,
`views` dahil tüm kolonlar. Cache'li; `--refresh` ile yenilenir.

## Adım 3 — tag envanteri (lokal, API yok)  ✅

```bash
python analyze_tags.py
```
Çıktı: `reports/tag_inventory.md` (frekans, eksik tag'ler, kısa başlıklar,
yetim tag'ler, üst/alt %20 performans) + `reports/orphan_tags.txt` (tam yetim liste).

## Adım 4 — eRank merge  ✅

```bash
# eRank export'larını (Keyword Tool ve/veya Shop listings) buraya koy:
#   data/erank/*.csv
python merge_erank.py
```
İki dosya türünü otomatik algılar (keyword metrikleri + rakip mağaza ilanları),
esnek kolon eşlemesi yapar, rakip marka tag'lerini eler. Çıktı:
`reports/keyword_gaps.md` (KORU / KALDIR / FIRSAT / RAKİP AÇIĞI + başlık adayları)
+ `data/opportunity_keywords.csv`. Eşikler script başındaki sabitlerden ayarlanır.

## Adım 5 (bonus) — aksiyon planı  ✅

```bash
python action_plan.py
```
Adım 3+4 bulgularını ilan-bazlı somut öneriye çevirir: her ilan için **çıkar**
(KALDIR tag'leri), **ekle** (tematik uyan FIRSAT/RAKİP tag'leri), **başlık öner**.
Çıktı: `reports/action_plan.md` (öncelikli ilanlar detaylı) + `data/action_plan.csv`
(tüm öneriler). Eşleme, başlık+tag kelime örtüşmesine dayanır.

---
**Not:** Tüm pipeline salt-okunur. Hiçbir yazma (updateListing) API'si çağrılmaz.
