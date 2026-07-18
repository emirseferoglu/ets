"""
poster_pack.py — Dikey POSTER üretir ve 5-size baskı paketi çıkarır.

Akış:
  1. Ideogram V4 ile 2:3 dikey master üret (1365×2048)
  2. ESRGAN 4x AI upscale (~5460×8192)
  3. Merkez-kırpma ile 5 oran, 300 DPI baskı boyutları:
       2:3  → 6000×9000  (4x6, 8x12, 12x18, 16x24, 20x30, 24x36")
       3:4  → 5400×7200  (6x8, 9x12, 12x16, 18x24")
       4:5  → 4800×6000  (8x10, 12x15, 16x20, 24x30")
       ISO  → 4961×7016  (A5, A4, A3, A2; A1 ~%85 DPI)
       11:14→ 3300×4200  (11x14")
  (Etsy dijital dosya limiti = 5 → paket tam oturur.)

Kullanım:
    python poster_pack.py "PROMPT" output/poster-tema
"""

from __future__ import annotations

import sys
from pathlib import Path

from generate_art import esrgan_4x, generate

# (klasör_adı, hedef_px, kapsanan baskı boyutları — description için)
RATIOS = [
    ("2x3",   (6000, 9000), '4x6", 8x12", 12x18", 16x24", 20x30", 24x36"'),
    ("3x4",   (5400, 7200), '6x8", 9x12", 12x16", 18x24"'),
    ("4x5",   (4800, 6000), '8x10", 12x15", 16x20", 24x30"'),
    ("ISO",   (4961, 7016), "A5, A4, A3, A2, A1"),
    ("11x14", (3300, 4200), '11x14"'),
]
MAX_MB = 19.5   # Etsy dijital dosya limiti 20MB


def _center_crop_resize(img, target: tuple[int, int]):
    from PIL import Image
    tw, th = target
    tr = tw / th
    w, h = img.size
    r = w / h
    if r > tr:      # master daha geniş → yanlardan kırp
        nw = int(h * tr)
        box = ((w - nw) // 2, 0, (w + nw) // 2, h)
    else:           # master daha uzun → üst/alttan kırp
        nh = int(w / tr)
        box = (0, (h - nh) // 2, w, (h + nh) // 2)
    return img.crop(box).resize(target, Image.LANCZOS)


def _save_under_limit(img, path: Path) -> None:
    """20MB Etsy limitinin altında kalacak şekilde JPEG kaydet."""
    for q in (92, 88, 84, 80):
        img.save(path, quality=q)
        if path.stat().st_size <= MAX_MB * 1024 * 1024:
            return
    # 80'de hâlâ büyükse olduğu gibi bırak (pratikte olmaz)


def make_pack(prompt: str, out_dir: str | Path,
              apply_texture: bool = True) -> dict:
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)

    master = d / "master_2x3.jpg"
    print("  dikey master üretiliyor (Ideogram V4, 2:3)…")
    generate(prompt, master, aspect_ratio="2:3", apply_texture=apply_texture)

    print("  ESRGAN 4x upscale…")
    big = esrgan_4x(master)
    print(f"  master: {big.size[0]}x{big.size[1]}")

    files = []
    for name, target, sizes in RATIOS:
        out = d / f"poster_{name}.jpg"
        _save_under_limit(_center_crop_resize(big, target), out)
        mb = out.stat().st_size / 1024 / 1024
        print(f"  ✓ {name:<6} {target[0]}x{target[1]}  ({mb:.1f}MB)  → {sizes}")
        files.append(out)

    # Listeleme önizlemesi (2000px, 4:5 — Etsy görseli için)
    preview = d / "preview.jpg"
    _center_crop_resize(big, (1600, 2000)).save(preview, quality=88)
    return {"dir": str(d), "files": [str(f) for f in files], "preview": str(preview)}


def included_files_text() -> str:
    """Listing description'a eklenecek 'Included Files' bloğu."""
    lines = ["📁 Included Files:",
             "You will receive 5 high-resolution JPG files (300 DPI), each in a "
             "different aspect ratio, allowing printing in 20+ standard frame sizes."]
    for name, _t, sizes in RATIOS:
        label = {"2x3": "2:3 Ratio", "3x4": "3:4 Ratio", "4x5": "4:5 Ratio",
                 "ISO": "ISO Sizes", "11x14": "11:14 Ratio"}[name]
        lines.append(f"❖ {label}: {sizes}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit('Kullanım: python poster_pack.py "PROMPT" output/klasor')
    result = make_pack(sys.argv[1], sys.argv[2])
    print(f"\nPaket hazır: {result['dir']}")
