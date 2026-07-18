# HANDOFF — Lumiaerestudio Etsy Otomasyonu

Bu dosya, bu repoya yeni bağlanan herhangi bir Claude Code oturumunun (özellikle
telefondan) saniyeler içinde tam bağlam kazanması için yazıldı. Kullanıcı
(Emirhan) Lumiaerestudio adlı Etsy mağazasını işletiyor: Samsung Frame TV art
+ printable poster satıyor, ~200 satış geçmişi var, eşiyle birlikte yönetiyorlar.

## ⚠️ Kritik: bu repo sadece KOD içeriyor, ÇALIŞAN SİSTEM DEĞİL

Gerçek prodüksiyon **DigitalOcean droplet'inde** çalışıyor (`174.138.47.198`),
bu repo değil. Bu repo koddaki değişiklikleri düzenlemek/incelemek içindir.
`.env` (API anahtarları), `data/` (bestseller havuzları, üretim geçmişi) ve
`output/` (üretilmiş görseller) bilinçli olarak **gitignore edildi** — hem
gizlilik hem repo boyutu için. Yani bu repoyu klonlayan bir cloud sandbox
(mobil Claude Code dahil) kodu görebilir/düzenleyebilir ama:
- Etsy/OpenAI/fal.ai/Twilio API'lerini ÇAĞIRAMAZ (anahtar yok)
- Gerçek mağazada draft OLUŞTURAMAZ
- WhatsApp mesajı GÖNDEREMEZ

**Gerçek üretim tetiklemek için tek yol**: droplet'e SSH ile bağlanıp orada
çalıştırmak, ya da zaten kurulu olan **WhatsApp botu** üzerinden `yap X` /
`poster X` yazmak. Mobil oturumdan kod değişikliği yapıp bunu droplet'e
`rsync` ile göndermek gerekir (aşağıda komutlar var).

## Sistem mimarisi (özet)

```
Etsy API ──┐
OpenAI ─────┼─→ market_research.py (bestseller formülü) ─→ data/bestsellers*.json
fal.ai ─────┘         ↓
                 product_ideas.py / poster_daily.py (taklit fikir üretir)
                       ↓
                 generate_art.py (Ideogram V4) → ESRGAN 4x → mockup
                       ↓
                 Etsy draft listing
                       ↓
                 daily_digest.py → WhatsApp raporu (Twilio)
                       ↓
                 whatsapp_listener.py (webhook, port 8090, systemd)
                       ↓ kullanıcı "yap 3" yazınca
                 produce_specific.py → yeniden üretim + WhatsApp'a sonuç
```

Cron: her sabah 07:00 Europe/Istanbul, droplet'te `run_daily.sh` çalışır.

## Bestseller formülü (önemli — tersine mühendislikle bulundu)

Etsy API'de resmi "bestseller" filtresi YOK. Kullanıcının Etsy arama
sayfasından (Bestseller filtresi açık) topladığı 51 gerçek rozetli ilan +
API metrikleri karşılaştırılarak bulundu:

```
fav_per_day = favorites / age_days
views_per_day = views / age_days
BESTSELLER ≈ (fav_per_day >= 0.3) VEYA (views_per_day >= 5)
```

43 tekil üründe %97 doğruluk. `market_research.py` içinde `extract_bestsellers()`.
İki ayrı havuz taranır: `data/bestsellers.json` (Frame TV pazarı) ve
`data/bestsellers_poster.json` (printable poster pazarı — ayrı sorgularla,
"frame tv" kelimesi geçenler filtrelenir).

Doğrulanmış 51 gerçek rozetli listing_id kalıcı olarak
`data/ground_truth_bs_ids.json`'da saklanır, her taramada havuza eklenir.

## Sezon bekçisi

`product_ideas.py` içinde `holiday_season_status()` — geçmiş bayram
ürünlerini (örn. 4 Temmuz, Ekim ayında) otomatik atlar, yaklaşan bayramı
(75 gün penceresi) öne çeker. 20 bayram/kutlama tanımlı, ay ay kapsıyor.

## Taklit akışı (title + tag + görsel)

1. Bestseller listing'in **title ve 13 tag'i doğrudan kopyalanır**
   (SKU kodları, dükkan adı, markalı terimler temizlenerek) —
   `_clean_copied_title()`, `_copied_tags()`
2. **Görsel benzerlik** (`ref_images.py` + `ai_brief.py`):
   - Rakibin TÜM görselleri çekilir (Etsy API öncelikli, Firecrawl yedek)
   - Firecrawl ayrıca satıcının açıklama metninden görsel ipucu arar
   - GPT-4o görsellere bakıp Ideogram prompt'unu **DOĞRUDAN kendisi yazar**
     (`_write_replication_prompt` — ara "spec" katmanı yok, doğrudan prompt)
   - Konu sayıları, yerleşim, zemin, 4-6 kesin renk, teknik (impasto mı düz mü),
     işaret ölçeği/yoğunluğu hepsi prompt'ta zorunlu
   - Referans DÜZ teknikse (pastel/guaj/suluboya/çizim) impasto ev-stili
     otomatik KAPANIR (`apply_texture=False`) — aksi halde her şey yanlışlıkla
     kalın yağlı boyaya dönüşüyordu, bu düzeltildi
3. **Önemli sınır**: soyut/desenli eserlerde "birebir" kopya teknik olarak
   mümkün değil (metin→görsel modeli piksel kopyalayamaz) — "aynı palet/enerji,
   özgün desen" seviyesinde kalır. Bilinçli olarak image-to-image kullanılmıyor
   (telif riski — Etsy mağazayı kapatabilir). Somut konularda (kuş, bulut,
   çiçek dalı vb.) çok yüksek benzerlik elde ediliyor.

## Üretim hattı

- **TV Art**: `generate_products.py` → `generate_art.py` (Ideogram V4,
  1536×864) → `esrgan_4x` (fal-ai/esrgan, 4x) → LANCZOS downscale 3840×2160
  → `mockup.py` (assets/mockup/ şablonları, 6 görsel) → Etsy draft
- **Poster**: `poster_daily.py` → dikey 2:3 master → ESRGAN 4x → `poster_pack.py`
  (5 farklı en-boy oranı: 2:3, 3:4, 4:5, ISO, 11:14 — hepsi 300 DPI, Etsy'nin
  5-dosya limitiyle tam uyumlu) → `poster_mockup.py` (poster-mockup/ şablonları,
  perspektif warp ile açılı çerçevelere bindirme) → Etsy draft
  - **Description ayrı yazılır** (brief'in description'ı KULLANILMAZ) —
    poster açıklamasında asla "Frame TV/16:9/3840/SmartThings" geçmemeli.
    Bu bug bir kez yaşandı ve düzeltildi, tekrar açılmasın.

## WhatsApp botu (Twilio Sandbox)

- `notify_whatsapp.py` — gönderim, `WHATSAPP_TO` virgülle çoklu numara destekler
  (kullanıcı + eşi)
- `daily_digest.py` — sabah raporu: bugün üretilenler + 📺 TV adayları (4) +
  🖼 poster adayları (4), her birinin Etsy linkiyle. `data/daily_digest.json`'a
  numara→listing_id haritası yazılır.
- `whatsapp_listener.py` — Flask webhook, port 8090, systemd servisi
  (`whatsapp-listener.service`). Komutlar: `liste`, `yap 2 5`, `poster 3`.
  Sadece `WHATSAPP_TO`'daki numaralardan gelen mesajları işler.
- `produce_specific.py` — listener'ın çağırdığı, tek bir listing_id'yi
  TV art veya poster olarak üretip WhatsApp'a sonuç linkini geri gönderen script.
- **Sandbox kısıtı**: Twilio trial hesabı, sandbox'a "join hollow-cost" ile
  katılan numaralara mesaj atabilir; katılım ~72 saatte bir mesaj
  gönderilmeden düşebilir. Kalıcı çözüm: gerçek Twilio numarası (~$1/ay,
  henüz yapılmadı).

## Droplet bilgileri

- IP: `174.138.47.198`, proje yolu: `/root/ets-api`
- venv: `/root/ets-api/.venv` (aktive: `source .venv/bin/activate`)
- Cron: `crontab -l` → `0 7 * * * bash /root/ets-api/run_daily.sh`
- Log: `/root/ets-api/logs/daily_<tarih>.log`
- WhatsApp listener: `systemctl status whatsapp-listener`,
  loglar `journalctl -u whatsapp-listener -f`

**Yerelden droplet'e deploy** (kod değişikliği sonrası):
```bash
rsync -avz <değişen_dosya.py> root@174.138.47.198:/root/ets-api/
ssh root@174.138.47.198 'systemctl restart whatsapp-listener'  # listener kodu değiştiyse
```

## .env'de olması gereken anahtarlar (droplet'te dolu, bu repoda YOK)

```
FAL_KEY=              # fal.ai (Ideogram V4 + ESRGAN)
OPENAI_API_KEY=       # GPT-4o brief + replikasyon prompt
ETSY_API_KEY= / ETSY_SHARED_SECRET= / ETSY_SHOP_ID=  # (etsy_client.py'ye bak)
FIRECRAWL_KEY=        # rakip sayfası scrape yedek
TWILIO_SID= / TWILIO_TOKEN= / TWILIO_WHATSAPP_FROM= / WHATSAPP_TO=
AIRTABLE_*            # opsiyonel provenance log
```

## Kullanıcı tercihleri (biriktirilen geri bildirim)

- Onay istemekten hoşlanmıyor — "bulduğun ürünlerden gerçekten satan bestseller
  olsun, rastgele olmasın, düşünmeden yap" tarzı net talimatlar veriyor,
  gereksiz "yapayım mı?" sorularını sevmiyor.
  cardinal önem: **bestseller formülü rastgele değil, veriden çıkarılmış ve
  doğrulanmış** — bunu asla gevşetme veya "yaklaşık" hale getirme.
- Poster ve TV art'ın karıştırılmasına çok duyarlı: her ikisinin ayrı pazar
  taraması, ayrı açıklama şablonu, ayrı mockup seti olması ısrarla istendi.
- Görsel benzerlik konusunda kalite standardı yüksek — "buldum, taklit ettim"
  yetmiyor, gerçekten görsel olarak yakın olmalı.
