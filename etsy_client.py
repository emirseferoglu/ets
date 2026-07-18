"""
etsy_client.py — Etsy API v3 için salt-okunur istemci.

Sorumluluklar:
  * OAuth2 token'larını (.tokens.json) yükle, süresi dolmadan otomatik yenile.
  * 5 QPS'i aşmayan throttle + 429/5xx'te exponential backoff.
  * get_shop(), get_all_listings() (otomatik pagination), get_listing_images().

NOT: Okuma metodları (_request) yalnızca GET yapar. Tek yazma yolu, açıkça
çağrılan update_listing()'dir (PATCH, listings_w scope'u gerekir). İlk token'ı
almak için `authorize.py` kullan.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Any, Iterable

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.etsy.com/v3/application"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

# Proje kökü — bu dosyanın bulunduğu dizin.
ROOT = Path(__file__).resolve().parent
TOKENS_PATH = ROOT / ".tokens.json"


def sanitize_tag(tag: str) -> str:
    """Etsy tag: yalnızca harf/rakam/boşluk, ≤20 kr (Etsy özel karakter kabul etmez)."""
    t = re.sub(r"[^0-9A-Za-zÀ-ÿ ]", " ", tag)
    return re.sub(r"\s+", " ", t).strip()[:20]

# Access token bu kadar saniye içinde dolacaksa peşinen yenile.
_REFRESH_BUFFER_SECONDS = 120


class EtsyAuthError(RuntimeError):
    """Token yok / yenilenemedi — authorize.py çalıştırılmalı."""


class RateLimiter:
    """Kayan 1 saniyelik pencerede en fazla `max_per_sec` istek."""

    def __init__(self, max_per_sec: int = 5) -> None:
        self.max_per_sec = max_per_sec
        self._calls: deque[float] = deque()

    def acquire(self) -> None:
        now = time.monotonic()
        # Pencere dışındaki (1sn'den eski) kayıtları at.
        while self._calls and now - self._calls[0] >= 1.0:
            self._calls.popleft()
        if len(self._calls) >= self.max_per_sec:
            sleep_for = 1.0 - (now - self._calls[0]) + 0.01
            if sleep_for > 0:
                time.sleep(sleep_for)
            return self.acquire()
        self._calls.append(time.monotonic())


class EtsyClient:
    def __init__(self, env_path: str | os.PathLike[str] | None = None) -> None:
        load_dotenv(env_path or (ROOT / ".env"))
        self.api_key = os.getenv("ETSY_API_KEY", "").strip()
        if not self.api_key:
            raise EtsyAuthError(".env içinde ETSY_API_KEY tanımlı değil.")
        # Etsy politikası (2026): her v3 isteğinde x-api-key = keystring:shared_secret.
        self.shared_secret = os.getenv("ETSY_SHARED_SECRET", "").strip()
        if not self.shared_secret:
            raise EtsyAuthError(
                ".env içinde ETSY_SHARED_SECRET tanımlı değil. "
                "Etsy artık her istekte x-api-key = keystring:shared_secret istiyor."
            )
        self.configured_shop_id = os.getenv("ETSY_SHOP_ID", "").strip() or None
        self.shop_name = os.getenv("ETSY_SHOP_NAME", "").strip() or None

        self._limiter = RateLimiter(max_per_sec=5)
        self._session = requests.Session()
        self._tokens = self._load_tokens()
        self._shop_id: int | None = (
            int(self.configured_shop_id) if self.configured_shop_id else None
        )

    # ------------------------------------------------------------------ tokens
    def _load_tokens(self) -> dict[str, Any]:
        if not TOKENS_PATH.exists():
            raise EtsyAuthError(
                f"{TOKENS_PATH.name} bulunamadı. Önce `python authorize.py` çalıştır."
            )
        data = json.loads(TOKENS_PATH.read_text())
        for key in ("access_token", "refresh_token", "expires_at"):
            if key not in data:
                raise EtsyAuthError(f"{TOKENS_PATH.name} bozuk: '{key}' eksik.")
        return data

    def _save_tokens(self, data: dict[str, Any]) -> None:
        # 0600 izinle yaz — secret'ları başkası okuyamasın.
        TOKENS_PATH.write_text(json.dumps(data, indent=2))
        try:
            os.chmod(TOKENS_PATH, 0o600)
        except OSError:
            pass
        self._tokens = data

    def _refresh_if_needed(self) -> None:
        if time.time() < self._tokens["expires_at"] - _REFRESH_BUFFER_SECONDS:
            return
        self._limiter.acquire()
        resp = self._session.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self.api_key,
                "refresh_token": self._tokens["refresh_token"],
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise EtsyAuthError(
                f"Token yenilenemedi ({resp.status_code}). "
                f"Refresh token süresi dolmuş olabilir → `python authorize.py`. "
                f"Yanıt: {resp.text[:300]}"
            )
        payload = resp.json()
        # Etsy refresh yanıtı yeni bir refresh_token da döner; onu da sakla.
        self._save_tokens(
            {
                "access_token": payload["access_token"],
                "refresh_token": payload.get(
                    "refresh_token", self._tokens["refresh_token"]
                ),
                "expires_at": time.time() + payload["expires_in"],
            }
        )

    # ----------------------------------------------------------------- request
    def _auth_headers(self) -> dict[str, str]:
        return {
            # Etsy 2026: keystring:shared_secret formatı zorunlu.
            "x-api-key": f"{self.api_key}:{self.shared_secret}",
            "Authorization": f"Bearer {self._tokens['access_token']}",
        }

    def _send(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Ortak istek gönderici: refresh + throttle + 429/5xx backoff."""
        self._refresh_if_needed()
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        headers = self._auth_headers()

        max_attempts = 6
        backoff = 1.0
        for attempt in range(1, max_attempts + 1):
            self._limiter.acquire()
            resp = self._session.request(method, url, headers=headers, timeout=30, **kwargs)

            if resp.status_code in (200, 201):
                return resp.json() if resp.content else {}

            # 429 / 5xx → geri çekil ve tekrar dene.
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                if attempt == max_attempts:
                    resp.raise_for_status()
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else backoff
                time.sleep(wait)
                backoff = min(backoff * 2, 30.0)
                continue

            if resp.status_code in (401, 403):
                raise EtsyAuthError(
                    f"Yetki hatası ({resp.status_code}) {path}. "
                    f"Scope eksik olabilir ya da token geçersiz. Yanıt: {resp.text[:300]}"
                )

            # Diğer 4xx → anlamlı hata fırlat.
            raise RuntimeError(
                f"İstek başarısız ({resp.status_code}) {method} {path}: {resp.text[:300]}"
            )

        raise RuntimeError("Ulaşılamaz: retry döngüsü beklenmedik şekilde bitti.")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        # Okuma yolu: yalnızca GET. Yazma için update_listing() kullan.
        if method.upper() != "GET":
            raise ValueError(f"_request sadece GET yapar, '{method}' engellendi.")
        return self._send("GET", path, **kwargs)

    # ------------------------------------------------------------------ public
    def resolve_shop_id(self) -> int:
        """
        Shop id'yi belirle. Öncelik sırası:
          1. .env → ETSY_SHOP_ID (varsa doğrudan kullanılır)
          2. .env → ETSY_SHOP_NAME → findShops (/shops?shop_name=...) ile ara

        Not: /users/me endpoint'i kişisel app'lerde "Shared secret is required"
        hatası verdiği için kullanılmıyor.
        """
        if self._shop_id is not None:
            return self._shop_id
        if self.shop_name:
            page = self._request(
                "GET", "/shops", params={"shop_name": self.shop_name, "limit": 100}
            )
            results = page.get("results", [])
            # Önce birebir isim eşleşmesi ara, yoksa ilk sonucu al.
            for shop in results:
                if (shop.get("shop_name") or "").lower() == self.shop_name.lower():
                    self._shop_id = int(shop["shop_id"])
                    return self._shop_id
            if results:
                self._shop_id = int(results[0]["shop_id"])
                return self._shop_id
            raise EtsyAuthError(
                f"'{self.shop_name}' adıyla mağaza bulunamadı. "
                f"ETSY_SHOP_NAME'i kontrol et ya da ETSY_SHOP_ID'yi elle gir."
            )
        raise EtsyAuthError(
            "Shop belirlenemedi. .env içine ETSY_SHOP_NAME (mağaza adı) "
            "ya da ETSY_SHOP_ID ekle."
        )

    def get_shop(self) -> dict[str, Any]:
        """Mağaza meta verisi."""
        shop_id = self.resolve_shop_id()
        return self._request("GET", f"/shops/{shop_id}")

    def get_all_listings(
        self, state: str = "active", page_size: int = 100
    ) -> list[dict[str, Any]]:
        """
        Mağazanın tüm ilanlarını (varsayılan: aktif) pagination'ı otomatik
        çözerek döndürür. Tags ve description dahildir.
        """
        shop_id = self.resolve_shop_id()
        results: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._request(
                "GET",
                f"/shops/{shop_id}/listings/active"
                if state == "active"
                else f"/shops/{shop_id}/listings",
                params={
                    "limit": page_size,
                    "offset": offset,
                    "includes": "Tags",
                    **({} if state == "active" else {"state": state}),
                },
            )
            batch = page.get("results", [])
            results.extend(batch)
            total = page.get("count", len(results))
            offset += page_size
            if len(batch) < page_size or offset >= total:
                break
        return results

    def update_listing(
        self,
        listing_id: int,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Bir ilanın başlık ve/veya tag'lerini günceller (updateListing, PATCH).
        YAZMA işlemi — `listings_w` scope'u ve açık niyet gerektirir.
        Sadece verilen alanlar gönderilir (kısmi güncelleme).
        """
        shop_id = self.resolve_shop_id()
        data: dict[str, str] = {}
        if title is not None:
            data["title"] = title
        if tags is not None:
            if len(tags) > 13:
                raise ValueError(f"En fazla 13 tag; {len(tags)} verildi.")
            # Etsy tag'leri virgülle ayrılmış tek string bekler.
            data["tags"] = ",".join(tags)
        if not data:
            raise ValueError("Güncellenecek alan yok (title/tags ver).")
        return self._send(
            "PATCH", f"/shops/{shop_id}/listings/{listing_id}", data=data
        )

    def create_draft_listing(
        self,
        *,
        title: str,
        description: str,
        price: float,
        tags: list[str],
        taxonomy_id: int,
        quantity: int = 999,
        who_made: str = "i_did",
        when_made: str = "2020_2025",
        listing_type: str = "download",
        is_supply: bool = False,
    ) -> dict[str, Any]:
        """
        Yeni TASLAK ilan oluşturur (draft; yayınlanana kadar müşteriye görünmez).
        Dijital ürün için listing_type='download'. YAZMA — listings_w gerekir.
        """
        shop_id = self.resolve_shop_id()
        data = {
            "quantity": quantity,
            "title": title[:140],
            "description": description,
            "price": f"{price:.2f}",
            "who_made": who_made,
            "when_made": when_made,
            "taxonomy_id": taxonomy_id,
            "type": listing_type,
            "is_supply": "true" if is_supply else "false",
            "tags": ",".join(t for t in (sanitize_tag(x) for x in tags[:13]) if t),
        }
        return self._send("POST", f"/shops/{shop_id}/listings", data=data)

    def upload_listing_image(
        self, listing_id: int, image_path: str, rank: int = 1
    ) -> dict[str, Any]:
        """İlana görsel yükler (mockup). YAZMA."""
        shop_id = self.resolve_shop_id()
        img = Path(image_path).read_bytes()
        files = {"image": (Path(image_path).name, img, "image/jpeg")}
        return self._send(
            "POST",
            f"/shops/{shop_id}/listings/{listing_id}/images",
            data={"rank": rank},
            files=files,
        )

    def upload_listing_file(
        self, listing_id: int, file_path: str, name: str | None = None
    ) -> dict[str, Any]:
        """İlana indirilebilir dijital dosya ekler (teslim edilen 4K JPG). YAZMA."""
        shop_id = self.resolve_shop_id()
        fname = name or Path(file_path).name
        blob = Path(file_path).read_bytes()
        files = {"file": (fname, blob, "image/jpeg")}
        return self._send(
            "POST",
            f"/shops/{shop_id}/listings/{listing_id}/files",
            data={"name": fname},
            files=files,
        )

    def get_listing_images(self, listing_id: int) -> list[dict[str, Any]]:
        """Bir ilanın görsellerini döndürür."""
        shop_id = self.resolve_shop_id()
        page = self._request(
            "GET", f"/shops/{shop_id}/listings/{listing_id}/images"
        )
        return page.get("results", [])

    def get_listing(self, listing_id: int) -> dict[str, Any]:
        """Herhangi bir (kendi ya da rakip) ilanı public endpoint'ten çeker.
        Shop-scope gerekmez — findListing tüm aktif ilanlar için açık."""
        return self._request(
            "GET", f"/listings/{listing_id}",
            params={"includes": "Tags,Images,Shop"},
        )


def _redact(value: str) -> str:
    """Bir secret'ı loglanabilir hale getir (tamamını asla gösterme)."""
    if not value:
        return "<boş>"
    return f"{value[:4]}…{value[-2:]} (uzunluk {len(value)})"


if __name__ == "__main__":
    # Hızlı bağlantı testi. Secret basmaz.
    client = EtsyClient()
    print(f"API key   : {_redact(client.api_key)}")
    shop = client.get_shop()
    print(f"Shop      : {shop.get('shop_name')} (id={shop.get('shop_id')})")
    print(f"Aktif ilan: {shop.get('listing_active_count')}")
    listings = client.get_all_listings()
    print(f"Çekilen ilan sayısı: {len(listings)}")
    if listings:
        first = listings[0]
        print(f"Örnek ilan: {first.get('title', '')[:60]!r}")
        print(f"  tags: {first.get('tags')}")
