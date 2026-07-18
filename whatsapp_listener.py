"""
whatsapp_listener.py — Twilio gelen WhatsApp mesajlarını dinler.

Komutlar (sabah digest'indeki numaralarla):
  "yap 2 5"     → 2 ve 5 numaralı adayları TV art olarak üretir
  "poster 3"    → 3 numaralı adayı poster olarak üretir
  "liste"       → güncel aday listesini tekrar gönderir

Kurulum:
  * Twilio Console → WhatsApp Sandbox → "WHEN A MESSAGE COMES IN":
      http://<droplet-ip>:8090/whatsapp   (POST)
  * systemd servisi: whatsapp-listener.service (kurulum scripti ekler)

Güvenlik: yalnızca WHATSAPP_TO'daki numaradan gelen mesajlar işlenir.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

DIGEST_PATH = ROOT / "data" / "daily_digest.json"
LOG = ROOT / "logs" / "whatsapp_listener.log"
# Virgülle ayrılmış yetkili numaralar (sen + eşin vb.)
ALLOWED = {t.strip() for t in os.getenv("WHATSAPP_TO", "").split(",") if t.strip()}

app = Flask(__name__)


def _twiml(msg: str) -> tuple[str, int, dict]:
    body = (f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>"
            f"{msg}</Message></Response>")
    return body, 200, {"Content-Type": "application/xml"}


def _digest_map() -> dict[str, int]:
    if DIGEST_PATH.exists():
        return json.loads(DIGEST_PATH.read_text()).get("map", {})
    return {}


def _spawn(listing_id: int, mode: str) -> None:
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a") as f:
        subprocess.Popen(
            [str(ROOT / ".venv" / "bin" / "python"),
             str(ROOT / "produce_specific.py"),
             "--id", str(listing_id), "--mode", mode],
            cwd=str(ROOT), stdout=f, stderr=f)


@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    frm = request.form.get("From", "")
    body = (request.form.get("Body", "") or "").strip().lower()
    if ALLOWED and frm not in ALLOWED:
        return _twiml("Yetkisiz numara.")

    m = _digest_map()

    if body.startswith("liste"):
        try:
            from daily_digest import main as digest_main
            digest_main()
            return _twiml("Liste yeniden gönderildi.")
        except Exception as e:  # noqa: BLE001
            return _twiml(f"Liste hatası: {str(e)[:100]}")

    mode = "poster" if body.startswith("poster") else (
        "tv" if body.startswith(("yap", "tv")) else None)
    if mode is None:
        return _twiml("Komutlar: 'yap 2 5' (TV art), 'poster 3', 'liste'")

    nums = re.findall(r"\d+", body)
    if not nums:
        return _twiml("Numara belirt: örn 'yap 2 5'")

    started, unknown = [], []
    for n in nums:
        lid = m.get(n)
        if lid:
            _spawn(int(lid), mode)
            started.append(n)
        else:
            unknown.append(n)
    parts = []
    if started:
        parts.append(f"🚀 Üretim başladı ({mode}): {', '.join(started)}. "
                     "Bitince draft linki gelecek.")
    if unknown:
        parts.append(f"Listede yok: {', '.join(unknown)} ('liste' yazabilirsin)")
    return _twiml(" ".join(parts))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
