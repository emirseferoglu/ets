"""
ai_brief.py — OpenAI (vision) ile ürün brief'i üretir.

Verilen: tema + trend keyword'leri + KAZANAN rakip ilanın referans görsel(ler)i.
OpenAI görseli inceler (stil/kompozisyon/palet benchmark), sonra ÖZGÜN bir:
  * art_prompt  (fal.ai için — kazanan estetiğinde ama özgün, kopya değil)
  * title       (≤140, güçlü keyword önde)
  * tags        (13 adet, ≤20 kr)
  * description (keyword ilk cümlede + dijital indirme)

üretir. Kopyalama YASAK — sadece ilham/benchmark. OpenAI hata verirse çağıran
taraf şablona düşer (güvenli).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

SYSTEM = """You are an elite Etsy SEO strategist and art director for a shop selling \
DIGITAL Samsung Frame TV art (16:9, 4K, instant download).

You receive: a THEME, trend KEYWORDS, the TITLE of a current BEST-SELLING reference listing, \
and a detailed ANALYSIS of its artwork. Create a product that is VERY CLOSE to that winner — \
the SAME subject, composition, palette and mood — so it competes directly for the same buyers.

COPYRIGHT SAFETY (highest priority, overrides everything):
- If the reference involves ANY brand, franchise, trademarked or copyrighted character, movie, \
game, celebrity or real person (e.g. Star Wars, Darth Vader, Disney, Marvel, Harry Potter), \
you MUST NOT depict, name, parody or reference it. Instead strip it to the generic underlying \
subject (e.g. a classic Last Supper with ordinary robed figures softly painted with natural \
faces — never any franchise character or recognizable real person) and build the title/tags \
around that generic subject only.

CORE RULE — STAY VERY CLOSE TO THE WINNER (within the copyright rule above):
- Depict the SAME SUBJECT/SCENE as the reference. If the reference is a Last Supper / Christian \
scene, paint a Last Supper with robed figures at a long table; if a coastal seascape, paint \
that seascape; if birds in flight, birds in flight. Use the reference TITLE to understand the \
exact subject and the keywords buyers search for.
- Match its COMPOSITION, PALETTE and TECHNIQUE closely. This is an ORIGINAL rendition of the \
same subject in the same aesthetic — not a pixel-for-pixel copy of that one file, and never \
reproduce any watermark, brand or shop name — but it SHOULD clearly read as the same subject \
and vibe as the winner.
- NEVER euphemise or generalise the subject (never turn "Last Supper" into "Communal \
Gathering", or "cherry blossom" into "pink flowers"). Name it for what it is.
- If no reference is given, default to a vintage oil painting in the theme.

art_prompt: rich, specific prompt to PAINT that exact subject (keep the reference's subject, \
composition and palette) in EXACTLY THE SAME TECHNIQUE as the reference — copy its TECHNIQUE \
line faithfully: if the reference is heavy impasto oil, describe thick raised palette-knife \
strokes; if it is flat pastel/chalk/gouache/watercolor/ink/sketch, describe THAT flat chalky \
or washed technique and explicitly say "flat, matte, NO impasto, NO 3D paint ridges". Never \
substitute your own style for the reference's. Composed for a wide 16:9 TV, museum quality. \
End with: "no text, no watermark, no frame, no border, no signature".
title: <=140 chars, FRONT-LOAD the same strongest search keywords as the reference subject \
(e.g. "Last Supper", "Christian", "Religious"), include "Samsung Frame TV Art" and "Digital \
Download". Natural, not gibberish.
tags: EXACTLY 13, each <=20 chars, real buyer phrases around the subject. ONLY letters, \
numbers and spaces — NO colons/pipes/slashes/dashes. No brands, trademarks or real people.
description: 900-1400 chars, main subject keyword in first sentence, cover: what it is, instant \
digital download (no physical item), 4K 3840x2160 16:9, how to set on Frame TV, friendly close.

Return STRICT JSON only: {"art_prompt": "...", "title": "...", "tags": ["...x13"], "description": "..."}"""


def _clean_tags(tags: list) -> list[str]:
    out, seen = [], set()
    for t in tags:
        # Etsy tag: yalnızca harf/rakam/boşluk (":" "|" vb. reddedilir)
        t = re.sub(r"[^0-9A-Za-zÀ-ÿ ]", " ", str(t))
        t = re.sub(r"\s+", " ", t).strip()[:20]
        if t and t.lower() not in seen:
            out.append(t)
            seen.add(t.lower())
    return out[:13]


def _analyze_style(client, image_urls: list[str]) -> str:
    """Kazanan görseli REPLİKASYON düzeyinde analiz et — amaç: bu tarifi okuyan
    bir ressamın neredeyse aynı tabloyu yeniden çizebilmesi."""
    content: list[dict] = [{
        "type": "text",
        "text": ("You are writing a REPLICATION SPEC for a painter who must recreate "
                 "this best-selling artwork as closely as legally possible (same "
                 "subject, layout, palette, mood — an original rendition, not a "
                 "pixel copy). Some images may be room mockups: analyze only the "
                 "ARTWORK inside the frame/screen. Write these labeled lines:\n"
                 "SUBJECT: the exact scene/motif, faithfully and specifically, "
                 "including COUNT and pose of key elements (e.g. 'seven grey "
                 "herons standing, all facing left', 'one olive branch with five "
                 "olives').\n"
                 "LAYOUT: where each major element sits (left/center/right, "
                 "top/bottom, rough proportions), the direction subjects face, "
                 "how much empty background remains and where.\n"
                 "BACKGROUND: exact background type and tone (e.g. 'plain warm "
                 "beige watercolor wash, slightly darker toward upper left').\n"
                 "PALETTE: 4-6 dominant colors with precise names (e.g. 'sage "
                 "green, muted terracotta, cream, thin charcoal outlines').\n"
                 "TECHNIQUE: style, stroke type, texture, outline treatment "
                 "(e.g. 'flat gouache with visible pencil outlines', 'heavy "
                 "impasto oil with palette-knife ridges').\n"
                 "SCALE & DENSITY: the physical size and count of marks "
                 "relative to the canvas — e.g. 'hundreds of small dense "
                 "fragmented patches, each 2-4% of canvas width, tightly "
                 "packed all-over with thin sketchy dark lines between them' "
                 "vs 'five large sweeping shapes'. This matters enormously "
                 "for abstracts.\n"
                 "MOOD: one line.\n"
                 "Be concrete and visual, no marketing language. Ignore any "
                 "overlaid text, watermark, logo or shop name."),
    }]
    for u in image_urls[:3]:
        content.append({"type": "image_url", "image_url": {"url": u}})
    r = client.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": content}], max_tokens=600,
    )
    return (r.choices[0].message.content or "").strip()


def _write_replication_prompt(client, image_urls: list[str],
                              extra_context: str = "") -> str:
    """GPT-4o görsele bakıp Ideogram prompt'unu DOĞRUDAN yazar (ara katman yok).

    Amaç: prompt'u okuyan görüntü modeli bu tabloyu olabildiğince birebir
    yeniden üretsin. Marka/karakter güvenliği korunur."""
    content: list[dict] = [{
        "type": "text",
        "text": ("Look at the ARTWORK in these images (ignore room mockups, "
                 "frames, overlay text — analyze only the artwork itself"
                 + (f"; seller context: {extra_context[:400]}" if extra_context else "")
                 + "). Write ONE image-generation prompt that would recreate "
                 "THIS EXACT painting as faithfully as possible. The prompt "
                 "must:\n"
                 "- enumerate EVERY major element with its position, size and "
                 "count (e.g. 'in the lower left, a cluster of ...')\n"
                 "- describe the background precisely (type, tone, gradients)\n"
                 "- name 4-6 exact colors\n"
                 "- state the technique faithfully (flat pastel/chalk/gouache/"
                 "watercolor/ink → say 'flat, matte, NO impasto'; thick oil → "
                 "describe raised palette-knife strokes)\n"
                 "- state mark SCALE and DENSITY (e.g. 'hundreds of small "
                 "fragmented patches each 2-4% of canvas width, tightly "
                 "packed, thin sketchy charcoal lines between them')\n"
                 "- if the artwork contains any trademarked character, brand "
                 "or real person, replace it with a generic equivalent\n"
                 "- name the MEDIUM precisely (oil pastel / chalk / crayon / "
                 "gouache / watercolor / oil) and include: 'hand-made "
                 "traditional media look with grainy pigment texture and "
                 "soft irregular edges — NEVER vector art, NEVER clip-art, "
                 "NEVER flat digital graphics, NEVER hard outlined shapes'\n"
                 "Output ONLY the prompt text, 150-220 words, ending with: "
                 "'no text, no watermark, no frame, no border, no signature.'"),
    }]
    for u in image_urls[:3]:
        content.append({"type": "image_url", "image_url": {"url": u}})
    r = client.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": content}],
        max_tokens=500,
    )
    out = (r.choices[0].message.content or "").strip().strip('"')
    if len(out) < 80:
        raise ValueError("replikasyon promptu çok kısa")
    return out


def generate_brief(theme: str, keywords: list[str], reference_images: list[str],
                   reference_title: str = "",
                   reference_description: str = "") -> dict:
    """OpenAI ile brief üret. Başarısızsa exception fırlatır (çağıran şablona düşer)."""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # 1) Kazanan görseli nötr biçimde analiz et (görsel bu adımda kalır, brief'te değil).
    style = ""
    if reference_images:
        try:
            style = _analyze_style(client, reference_images)
        except Exception:  # noqa: BLE001
            style = ""

    # 2) Brief'i metin-only yaz (telif filtresine takılmaz).
    user = f"THEME: {theme}\nTREND KEYWORDS: {', '.join(keywords[:12])}\n"
    if reference_title:
        user += (f"\nBEST-SELLING REFERENCE TITLE (match this subject and its search "
                 f"keywords closely): {reference_title}\n")
    if reference_description:
        user += ("\nSELLER'S OWN DESCRIPTION OF THE REFERENCE (scraped from the "
                 "listing page — extract any VISUAL facts about style, colors, "
                 "subject and technique and honor them in art_prompt):\n"
                 f"{reference_description}\n")
    if style:
        user += ("\nREPLICATION SPEC OF THE REFERENCE ARTWORK — your art_prompt MUST "
                 "restate ALL of these concrete details (subject counts, layout "
                 "positions, background, palette, technique) so the new painting "
                 "reads as the same artwork re-painted by hand:\n"
                 f"{style}\n")
    user += "\nWrite the brief as strict JSON."

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.85,
        max_tokens=1600,
    )
    raw = resp.choices[0].message.content
    if not raw:
        raise ValueError("OpenAI boş yanıt döndü.")
    data = json.loads(raw)

    tags = _clean_tags(data.get("tags") or [])
    if not data.get("art_prompt") or not data.get("title") or len(tags) < 10:
        raise ValueError("OpenAI brief eksik/geçersiz döndü.")

    # BİREBİR MOD: görsel varsa art_prompt'u GPT-4o görsele bakarak DOĞRUDAN
    # yazar (spec→brief ara katmanındaki bilgi kaybı olmaz). Hata olursa
    # brief'in kendi prompt'u kullanılır.
    art_prompt = data["art_prompt"].strip()
    if reference_images:
        try:
            art_prompt = _write_replication_prompt(
                client, reference_images, reference_description)
            print("  (birebir replikasyon promptu kullanıldı)")
        except Exception as e:  # noqa: BLE001
            print(f"  (replikasyon promptu düşmedi: {str(e)[:50]} → brief)")

    return {
        "art_prompt": art_prompt,
        "title": data["title"].strip()[:140],
        "tags": tags,
        "description": (data.get("description") or "").strip(),
    }


if __name__ == "__main__":
    import sys
    th = sys.argv[1] if len(sys.argv) > 1 else "coastal"
    b = generate_brief(th, ["coastal tv art", "beach frame tv", "seascape painting"], [])
    print(json.dumps(b, ensure_ascii=False, indent=2))
