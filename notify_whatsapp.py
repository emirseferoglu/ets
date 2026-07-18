"""
notify_whatsapp.py — Twilio WhatsApp gönderimi.

.env değişkenleri:
  TWILIO_SID           = ACxxxxxxxx
  TWILIO_TOKEN         = xxxxxxxx
  TWILIO_WHATSAPP_FROM = whatsapp:+14155238886   (sandbox veya onaylı numara)
  WHATSAPP_TO          = whatsapp:+905xxxxxxxxx  (senin numaran)
"""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")


def send_whatsapp(body: str) -> bool:
    """WHATSAPP_TO virgülle ayrılmış birden çok numara olabilir."""
    sid = os.getenv("TWILIO_SID", "").strip()
    token = os.getenv("TWILIO_TOKEN", "").strip()
    from_ = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
    tos = [t.strip() for t in os.getenv("WHATSAPP_TO", "").split(",") if t.strip()]
    if not all((sid, token, from_)) or not tos:
        print("(WhatsApp atlandı: TWILIO_* / WHATSAPP_TO .env'de yok)")
        return False
    body = body[:1500]   # WhatsApp tek mesaj limiti ~1600 karakter
    ok = True
    for to in tos:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"From": from_, "To": to, "Body": body},
            timeout=30,
        )
        if r.status_code in (200, 201):
            print(f"WhatsApp gönderildi → {to}")
        else:
            ok = False
            print(f"WhatsApp hatası ({to}) {r.status_code}: {r.text[:150]}")
    return ok


if __name__ == "__main__":
    import sys
    send_whatsapp(sys.argv[1] if len(sys.argv) > 1 else "Test — ETS otomasyonu")
