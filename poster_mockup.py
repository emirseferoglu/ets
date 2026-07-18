"""
poster_mockup.py — poster sanatını poster-mockup/ şablonlarına bindirir.

Düz şablonlar basit paste, açılı şablonlar perspektif warp ile işlenir.
Koordinatlar 2026-07 kalibrasyonu (poster-mockup/*.jpg, 1588px genişlik).

Kullanım:
    python poster_mockup.py output/poster-olive-test/poster_2x3.jpg output/poster-olive-test
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "poster-mockup"

# Şablon adı → sanat alanının 4 köşesi (TL, TR, BR, BL) şablon pikselinde.
# Damalı placeholder'lı şablonlardan OTOMATİK tespit (kenar-doğrusu uydurma,
# 2026-07). Şablonlar 4764×4764.
TEMPLATES: dict[str, list[tuple[int, int]]] = {
    "1.jpg": [(1251, 677), (3588, 674), (3623, 4122), (1214, 4125)],
    "2.jpg": [(1204, 960), (3156, 917), (3366, 4017), (1392, 4302)],
    "3.jpg": [(1952, 1794), (3335, 1800), (3316, 3912), (1920, 3872)],
    "4.jpg": [(1893, 1698), (2873, 1698), (2873, 3071), (1893, 3071)],
    "5.jpg": [(1159, 615), (2526, 619), (2523, 2516), (1157, 2512)],
    "6.jpg": [(1156, 797), (3636, 789), (3626, 4124), (1170, 4115)],
}
# Listeleme sırası: hero önce.
ORDER = ["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg", "6.jpg"]


def _find_coeffs(dest_quad, src_quad):
    """PIL PERSPECTIVE katsayıları: çıktı koordinatı → kaynak koordinatı."""
    matrix = []
    for (dx, dy), (sx, sy) in zip(dest_quad, src_quad):
        matrix.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        matrix.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
    a = np.array(matrix, dtype=np.float64)
    b = np.array([c for p in src_quad for c in p], dtype=np.float64)
    return np.linalg.lstsq(a, b, rcond=None)[0]


def _quad_aspect(quad) -> float:
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = quad
    w = (abs(x1 - x0) + abs(x2 - x3)) / 2
    h = (abs(y3 - y0) + abs(y2 - y1)) / 2
    return w / h


EXPAND_PX = 6    # tespit kenari birkac px iceride kalabilir; disari tasir, cerceve orter


def _expand_quad(quad, e=EXPAND_PX):
    cx = sum(p[0] for p in quad) / 4
    cy = sum(p[1] for p in quad) / 4
    out = []
    for x, y in quad:
        dx, dy = x - cx, y - cy
        n = (dx * dx + dy * dy) ** 0.5 or 1.0
        out.append((x + dx / n * e, y + dy / n * e))
    return out


def render_one(art: Image.Image, template_name: str, out_path: Path) -> Path:
    quad = _expand_quad(TEMPLATES[template_name])
    tpl = Image.open(TEMPLATE_DIR / template_name).convert("RGB")
    tw, th = tpl.size

    # Sanatı quad'ın en-boy oranına ve gerçek boyutuna oturt
    ar = _quad_aspect(quad)
    fit_h = min(3600, max(1600, int(max(abs(quad[3][1] - quad[0][1]),
                                        abs(quad[2][1] - quad[1][1])))))
    fit_w = int(fit_h * ar)
    fitted = ImageOps.fit(art, (fit_w, fit_h), Image.LANCZOS)

    src = [(0, 0), (fit_w, 0), (fit_w, fit_h), (0, fit_h)]
    coeffs = _find_coeffs(quad, src)
    warped = fitted.transform((tw, th), Image.PERSPECTIVE, tuple(coeffs),
                              Image.BICUBIC)

    mask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(mask).polygon([tuple(p) for p in quad], fill=255)
    tpl.paste(warped, (0, 0), mask)
    if max(tpl.size) > 2400:      # Etsy listeleme görseli için makul boyut
        s = 2400 / max(tpl.size)
        tpl = tpl.resize((int(tpl.width * s), int(tpl.height * s)), Image.LANCZOS)
    tpl.save(out_path, quality=90)
    return out_path


def render_all(art_path: str | Path, out_dir: str | Path) -> list[Path]:
    art = Image.open(art_path).convert("RGB")
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    outs = []
    for i, name in enumerate(ORDER, 1):
        out = d / f"listing_{i}.jpg"
        render_one(art, name, out)
        outs.append(out)
        print(f"  ✓ {name} → {out.name}")
    return outs


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("Kullanım: python poster_mockup.py art.jpg out_dir")
    render_all(sys.argv[1], sys.argv[2])
