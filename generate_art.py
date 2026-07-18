"""
generate_art.py — fal.ai (Ideogram V4) ile Frame TV art üretir.

FAL_KEY .env'den okunur. 16:9 görsel üretir, LANCZOS ile 3840×2160'a scale eder.

Kullanım (test):
    python generate_art.py "A cottagecore cottage garden, painterly, 16:9" out.jpg
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
os.environ.setdefault("FAL_KEY", os.getenv("FAL_KEY", ""))

import fal_client  # noqa: E402  (FAL_KEY env'den sonra import)

DEFAULT_MODEL = "ideogram/v4"

# HER prompt'a eklenen zorunlu doku ifadesi — çıktılar "flat"/dijital değil,
# gerçek yağlı boya + görünür fırça darbeleri + kanvas dokusu olsun.
TEXTURE_SUFFIX = (
    " Painted as a HEAVILY TEXTURED traditional OIL PAINTING on coarse canvas — "
    "THICK RAISED brushstrokes with visible bristle marks, HEAVY impasto where paint "
    "stands off the surface in three-dimensional ridges, bold palette-knife strokes "
    "with scraped and layered paint, rough canvas weave showing through thinner areas, "
    "each stroke carrying a different load of paint creating tactile depth variation. "
    "The surface must look like a real oil painting you could touch and feel the bumps — "
    "NEVER flat, NEVER smooth, NEVER airbrushed, NEVER digital-looking."
)


def generate(
    prompt: str,
    out_path: str | Path,
    model: str = DEFAULT_MODEL,
    aspect_ratio: str = "16:9",
    apply_texture: bool = True,
) -> tuple[Path, str]:
    """Görsel üret; (yerel_dosya, fal_url) döndürür.

    apply_texture=False → impasto ev-stili eki ATLANIR (referans düz
    pastel/guaj/suluboya/çizim ise teknik sadakati bozmasın)."""
    if not os.getenv("FAL_KEY"):
        raise SystemExit(".env içinde FAL_KEY yok.")
    full_prompt = prompt.strip().rstrip(".") + "."
    if apply_texture:
        full_prompt += TEXTURE_SUFFIX
    if "ideogram" in model:
        # 16:9 = Frame TV; 2:3 = dikey poster master (5-size pakete kırpılır)
        size = {"width": 1536, "height": 864} if aspect_ratio == "16:9" \
            else {"width": 1365, "height": 2048}
        args = {
            "prompt": full_prompt,
            "image_size": size,
            "rendering_speed": "QUALITY",
            "num_images": 1,
            "output_format": "jpeg",
            "enable_safety_checker": True,
        }
    elif "ultra" in model:
        args = {
            "prompt": full_prompt,
            "aspect_ratio": aspect_ratio,
            "num_images": 1,
            "output_format": "jpeg",
            "safety_tolerance": "5",
            "raw": False,
        }
    else:
        args = {
            "prompt": full_prompt,
            "image_size": {"width": 1536, "height": 864},
            "num_images": 1,
            "num_inference_steps": 28,
            "enable_safety_checker": True,
        }
    result = fal_client.subscribe(model, arguments=args, with_logs=False)
    url = result["images"][0]["url"]
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    return out, url


def esrgan_4x(src_path: str | Path):
    """ESRGAN 4x AI upscale — PIL.Image döndürür (kırpma/yeniden boyutlamaya hazır)."""
    import io

    from PIL import Image

    fal_url = fal_client.upload_file(str(src_path))
    result = fal_client.subscribe("fal-ai/esrgan", arguments={
        "image_url": fal_url,
        "scale": 4,
        "model": "RealESRGAN_x4plus",
        "output_format": "jpeg",
    }, with_logs=False)
    r = requests.get(result["image"]["url"], timeout=300)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def upscale_4k(
    src_path: str | Path,
    out_path: str | Path,
    target: tuple[int, int] = (3840, 2160),
) -> Path:
    """ESRGAN 4x AI upscale → LANCZOS ile hedef boyuta teslim dosyası."""
    from PIL import Image

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    esrgan_4x(src_path).resize(target, Image.LANCZOS).save(out, quality=95)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit('Kullanım: python generate_art.py "PROMPT" out.jpg')
    p, _ = generate(sys.argv[1], sys.argv[2])
    print(f"✓ üretildi: {p}")
