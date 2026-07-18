"""
authorize.py — Etsy OAuth2 PKCE akışını bir kez çalıştırıp ilk token'ları alır.

Akış:
  1. code_verifier + code_challenge (S256) üret.
  2. Etsy authorize URL'ini aç, kullanıcı onaylar.
  3. .env'deki ETSY_REDIRECT_URI portunda yerel bir dinleyici `code`'u yakalar.
  4. code + verifier ile token exchange yapılır.
  5. access/refresh token'lar .tokens.json'a (0600) yazılır.

Kullanım:
    python authorize.py

Not: ETSY_REDIRECT_URI, Etsy uygulama ayarlarında KAYITLI adresle birebir
aynı olmalı (ör. http://localhost:3003/callback).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
TOKENS_PATH = ROOT / ".tokens.json"
AUTHORIZE_URL = "https://www.etsy.com/oauth/connect"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"


def _pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) — S256."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    """Redirect'i yakalar; code + state'i sunucuya ekler."""

    expected_path = "/callback"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != self.expected_path:
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        self.server.auth_code = params.get("code", [None])[0]  # type: ignore[attr-defined]
        self.server.auth_state = params.get("state", [None])[0]  # type: ignore[attr-defined]
        self.server.auth_error = params.get("error", [None])[0]  # type: ignore[attr-defined]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = (
            "Yetkilendirme alindi. Bu sekmeyi kapatabilirsiniz."
            if self.server.auth_code  # type: ignore[attr-defined]
            else "Yetkilendirme basarisiz. Terminale donun."
        )
        self.wfile.write(
            f"<html><body style='font-family:sans-serif'><h3>{msg}</h3></body></html>".encode()
        )

    def log_message(self, *args: object) -> None:  # sessiz
        return


def main() -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("ETSY_API_KEY", "").strip()
    redirect_uri = os.getenv("ETSY_REDIRECT_URI", "").strip()
    scopes = os.getenv("ETSY_SCOPES", "listings_r shops_r").strip()

    if not api_key or not redirect_uri:
        raise SystemExit(
            "HATA: .env içinde ETSY_API_KEY ve ETSY_REDIRECT_URI dolu olmalı. "
            "Örnek için .env.example'a bak."
        )

    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80
    _CallbackHandler.expected_path = parsed.path or "/callback"

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)

    auth_url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": api_key,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    server = HTTPServer((host, port), _CallbackHandler)
    server.auth_code = None  # type: ignore[attr-defined]
    server.auth_state = None  # type: ignore[attr-defined]
    server.auth_error = None  # type: ignore[attr-defined]

    print("Tarayıcıda Etsy izin ekranı açılıyor…")
    print("Açılmazsa şu URL'i elle aç:\n")
    print(auth_url + "\n")
    webbrowser.open(auth_url)
    print(f"{host}:{port}{_CallbackHandler.expected_path} adresinde yanıt bekleniyor…")

    # Tek isteği bekle (callback) — sonra otomatik döner.
    server.handle_request()

    if server.auth_error:  # type: ignore[attr-defined]
        raise SystemExit(f"Etsy hata döndürdü: {server.auth_error}")  # type: ignore[attr-defined]
    if server.auth_state != state:  # type: ignore[attr-defined]
        raise SystemExit("HATA: state eşleşmedi (CSRF koruması). Tekrar deneyin.")
    code = server.auth_code  # type: ignore[attr-defined]
    if not code:
        raise SystemExit("HATA: authorization code alınamadı.")

    print("Code alındı, token exchange yapılıyor…")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": api_key,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": verifier,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise SystemExit(f"Token exchange başarısız ({resp.status_code}): {resp.text[:400]}")

    payload = resp.json()
    tokens = {
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "expires_at": time.time() + payload["expires_in"],
    }
    TOKENS_PATH.write_text(json.dumps(tokens, indent=2))
    try:
        os.chmod(TOKENS_PATH, 0o600)
    except OSError:
        pass

    print(f"\n✅ Token'lar {TOKENS_PATH.name} dosyasına yazıldı (0600).")
    print("   Artık `python etsy_client.py` ile bağlantıyı test edebilirsin.")


if __name__ == "__main__":
    main()
