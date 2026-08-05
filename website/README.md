# Tasarruf Finansmanı — Hesaplama & Karşılaştırma Sitesi

`tasarruffinansmani.com` mantığını taban alan, bağımlılıksız (vanilla HTML/CSS/JS) tek sayfalık replika.

## Çalıştırma
Statik site — sunucu gerekmez. `website/index.html` dosyasını tarayıcıda açın
veya klasörde basit bir sunucu başlatın:

```bash
cd website && python3 -m http.server 8000
# http://localhost:8000
```

## Hesaplama Mantığı (`assets/calculator.js`)
Faizsiz model — tek maliyet **organizasyon ücreti**:

| Değer | Formül |
|---|---|
| Aylık taksit | `(Tutar − Peşinat) / Vade` |
| Organizasyon ücreti | `Tutar × (oran / 100)` |
| Toplam ödenecek | `(Tutar − Peşinat) + Organizasyon ücreti` |
| Efektif maliyet oranı | `Organizasyon ücreti / Tutar` |
| Teslim (çekilişsiz) | `max(6, ceil(Vade × 0.40))` — %40 birikim, en erken 180. gün |
| Teslim (çekilişli) | `max(6, round(Vade × 0.66))` — garanti ay; kura ile daha erken olabilir |

## Bölümler
- **Hesaplama** (`#calculator-section`): ürün tipi, tutar, vade, peşinat, teslim modeli, org. ücreti oranı
- **Karşılaştır**: temsilî BDDK lisanslı firma oranlarıyla maliyet tablosu (en uygun vurgulanır)
- **Nasıl Çalışır / S.S.S.**

## Not
Firma oranları ve hesaplamalar **temsilîdir**, gerçek kampanya verisi değildir.
Bilgilendirme amaçlıdır; finansman tavsiyesi değildir.
