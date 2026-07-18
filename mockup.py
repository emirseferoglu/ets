"""
mockup.py — sanatı şablon türüne göre listeleme görseline dönüştürür.

Türler (assets/mockup/templates.json):
  * framed    : sanatı ahşap çerçevenin ekran bölgesine bindirir
  * fullbleed : sanatın kare crop'unu (2000×2000) üretir
  * static    : şablonu olduğu gibi kopyalar (ör. "HOW IT WORKS")

Kullanım (test):
    python mockup.py art.jpg 1.jpg out.jpg
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
MOCKUP_DIR = ROOT / "assets" / "mockup"
TEMPLATES = MOCKUP_DIR / "templates.json"


def load_templates() -> dict:
    if not TEMPLATES.exists():
        raise SystemExit("templates.json yok. Önce: python calibrate_mockups.py")
    return json.loads(TEMPLATES.read_text())


def render(art_path: str | Path, template_name: str, out_path: str | Path) -> Path:
    cfg = load_templates().get(template_name)
    if not cfg:
        raise SystemExit(f"{template_name} templates.json'da yok.")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    kind = cfg["type"]

    if kind == "static":
        shutil.copy(MOCKUP_DIR / template_name, out)
        return out

    art = Image.open(art_path).convert("RGB")

    if kind == "framed":
        x0, y0, x1, y1 = cfg["region"]
        tpl = Image.open(MOCKUP_DIR / template_name).convert("RGB")
        tpl.paste(ImageOps.fit(art, (x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
        tpl.save(out, quality=92)
    elif kind == "fullbleed":
        W, H = art.size
        s = int(min(W, H) * cfg.get("frac", 1.0))
        cx, cy = cfg.get("cx", 0.5), cfg.get("cy", 0.5)
        x = max(0, min(W - s, int(cx * W - s / 2)))
        y = max(0, min(H - s, int(cy * H - s / 2)))
        art.crop((x, y, x + s, y + s)).resize((2000, 2000), Image.LANCZOS).save(
            out, quality=92
        )
    else:
        raise SystemExit(f"Bilinmeyen tür: {kind}")
    return out


# Geriye dönük uyum.
def composite(art_path, template_name, out_path):
    return render(art_path, template_name, out_path)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit("Kullanım: python mockup.py art.jpg 1.jpg out.jpg")
    print(f"✓ {render(sys.argv[1], sys.argv[2], sys.argv[3])}")
