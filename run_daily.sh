#!/usr/bin/env bash
# run_daily.sh — her sabah çalışan otomasyon (cron/launchd bunu tetikler).
# 1) product_ideas.py ile 3 taze tema seçer (üretilmiş temaları atlar)
# 2) generate_products.py ile 3 ürünü üretip Etsy'ye TASLAK olarak yükler
# Tüm çıktı logs/daily_<tarih>.log'a yazılır.

set -uo pipefail
cd "$(dirname "$0")"

mkdir -p logs
DATE="$(date +%Y-%m-%d)"
LOG="logs/daily_${DATE}.log"

# venv'i etkinleştir (yoksa hata logla ve çık).
if [ ! -f .venv/bin/activate ]; then
  echo "[$(date)] HATA: .venv yok" >> "$LOG"; exit 1
fi
source .venv/bin/activate

{
  echo "=================================================="
  echo "[$(date)] Günlük çalıştırma başladı"
  echo "--- Adım 0: canlı trend araştırması (Etsy API, ücretsiz) ---"
  python market_research.py --pages 3 || echo "(trend araştırması atlandı, eRank ile devam)"
  echo "--- Adım 1: tema seçimi (trend öncelikli) ---"
  python product_ideas.py --count 3
  echo "--- Adım 2: üretim + Etsy taslak ---"
  python generate_products.py --count 3 --publish-draft
  echo "[$(date)] Bitti"
} >> "$LOG" 2>&1

echo "Tamamlandı → $LOG"
