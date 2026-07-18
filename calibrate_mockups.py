"""
calibrate_mockups.py — mockup şablonlarını sınıflandırıp config üretir.

Şablon türleri:
  * framed    : ahşap çerçeveli; sanat ekran bölgesine bindirilir (1, 2, 5)
  * fullbleed : tam-ekran; sanatın kare crop'u gösterilir (3, 4)
  * static    : sabit görsel (ör. "HOW IT WORKS"); olduğu gibi yüklenir (6)

Framed şablonlarda iç ekran bölgesi, ahşap rengini merkezden ÇOK ÇİZGİLİ
tarayarak (medyan) bulunur — tek çizgi anomalilerine dayanıklı.

Çıktı: assets/mockup/templates.json + assets/mockup/_debug/ overlay'leri.

Kullanım: python calibrate_mockups.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
MOCKUP_DIR = ROOT / "assets" / "mockup"
DEBUG_DIR = MOCKUP_DIR / "_debug"
TEMPLATES = MOCKUP_DIR / "templates.json"

# Otomatik tespitin başarısız olduğu şablonlar için elle ekran bölgesi.
# (5.jpg placeholder'ının ortasındaki dikey ek çizgisi sağ taramayı bozuyor.)
MANUAL_REGIONS = {"5.jpg": [155, 268, 1829, 1205]}

# Şablon türleri (sıra = Etsy görsel sırası).
FRAMED = ["1.jpg", "2.jpg", "5.jpg"]
FULLBLEED = {"3.jpg": {"frac": 1.0, "cx": 0.5, "cy": 0.5},   # geniş kare
             "4.jpg": {"frac": 0.62, "cx": 0.5, "cy": 0.5}}  # yakın kare
STATIC = ["6.jpg"]
ORDER = ["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg", "6.jpg"]

_SCAN_OFFSETS = [-220, -140, -70, 0, 70, 140, 220]


def is_wood(r: int, g: int, b: int) -> bool:
    """Tan ahşap: R>G>B, belirgin sıcaklık, duvardan (gri) ayrı."""
    return r > g > b and 24 < (r - b) < 130 and 140 < r < 245


def _boundary(px, sx: int, sy: int, dx: int, dy: int, W: int, H: int,
              run_need: int = 6) -> int | None:
    """(sx,sy)'den (dx,dy) yönünde ilk ahşap-run'ının merkeze yakın koordinatı."""
    x, y, run = sx, sy, 0
    while 0 <= x < W and 0 <= y < H:
        if is_wood(*px[x, y]):
            run += 1
            if run >= run_need:
                return (x - dx * (run - 1)) if dx else (y - dy * (run - 1))
        else:
            run = 0
        x += dx
        y += dy
    return None


def detect_region(path: Path) -> list[int]:
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = im.load()
    cx, cy = W // 2, H // 2

    def med(dx: int, dy: int, axis: str) -> int:
        vals = []
        for o in _SCAN_OFFSETS:
            sx, sy = (cx, cy + o) if axis == "row" else (cx + o, cy)
            b = _boundary(px, sx, sy, dx, dy, W, H)
            if b is not None:
                vals.append(b)
        return int(statistics.median(vals)) if vals else None

    left = med(-1, 0, "row") or 0
    right = med(1, 0, "row") or W
    top = med(0, -1, "col") or 0
    bottom = med(0, 1, "col") or H
    return [left, top, right, bottom]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    config: dict[str, dict] = {}

    for name in FRAMED:
        region = MANUAL_REGIONS.get(name) or detect_region(MOCKUP_DIR / name)
        config[name] = {"type": "framed", "region": region}
        w, h = region[2] - region[0], region[3] - region[1]
        ar = w / h if h else 0
        print(f"{name}: framed {region}  ({w}×{h}, en-boy {ar:.2f})")
        im = Image.open(MOCKUP_DIR / name).convert("RGB")
        ImageDraw.Draw(im).rectangle(region, outline=(255, 0, 0), width=8)
        im.save(DEBUG_DIR / f"{Path(name).stem}_debug.jpg", quality=70)

    for name, cfg in FULLBLEED.items():
        config[name] = {"type": "fullbleed", **cfg}
        print(f"{name}: fullbleed {cfg}")
    for name in STATIC:
        config[name] = {"type": "static"}
        print(f"{name}: static (olduğu gibi)")

    config["_order"] = ORDER
    TEMPLATES.write_text(json.dumps(config, indent=2))
    print(f"\nYazıldı: {TEMPLATES.relative_to(ROOT)}")
    print(f"Overlay: {DEBUG_DIR.relative_to(ROOT)}/  — framed tespitini gözle doğrula "
          "(en-boy ~1.78 = 16:9).")


if __name__ == "__main__":
    main()
