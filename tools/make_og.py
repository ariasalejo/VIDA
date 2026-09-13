#!/usr/bin/env python3
"""Genera los activos de marca de VIDA: og_image.png (1200x630) y favicon.svg.

Uso:
    python3 tools/make_og.py

Puede regenerarse cuando quiera: es reproducible y determinista.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_PNG = ROOT / "vida_ui_pro" / "og_image.png"
OUT_SVG = ROOT / "vida_ui_pro" / "favicon.svg"

FONT_BOLD = "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
FONT_MONO = "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf"

W, H = 1200, 630
TITLE = "Apropiación de los Conceptos en Ciberseguridad"


def lerp(a, b, t):
    return int(a + (b - a) * t)


def build() -> None:
    img = Image.new("RGB", (W, H), "#050d17")
    d = ImageDraw.Draw(img)

    # Rejilla sutil de fondo.
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    step = 46
    for x in range(0, W, step):
        gd.line([(x, 0), (x, H)], fill=(69, 230, 255, 22), width=1)
    for y in range(0, H, step):
        gd.line([(0, y), (W, y)], fill=(69, 230, 255, 22), width=1)
    img.paste(grid, (0, 0), grid)

    # Resplandores de color (púrpura y rosa ciberpunk).
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ogd = ImageDraw.Draw(glow)
    ogd.ellipse([-180, -220, 480, 300], fill=(120, 0, 255, 70))
    ogd.ellipse([760, -180, 1300, 340], fill=(255, 45, 149, 55))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img = Image.alpha_composite(img.convert("RGBA"), glow.convert("RGBA")).convert("RGB")
    d = ImageDraw.Draw(img)

    # Barra láser de marca en diagonal.
    for i in range(300):
        d.rectangle((700 + i, 470 - i // 3, 710 + i, 478 - i // 3),
                    fill=(lerp(46, 139, i / 300), lerp(139, 230, i / 300),
                          lerp(255, 255, i / 300)))

    f_kicker = ImageFont.truetype(FONT_MONO, 26)
    f_big = ImageFont.truetype(FONT_BOLD, 190)
    f_med = ImageFont.truetype(FONT_MONO, 34)
    f_small = ImageFont.truetype(FONT_MONO, 26)

    d.text((70, 66), "//////// SECTOR NEXUS · SUPER IAs", font=f_kicker, fill="#45e6ff")

    # Título "VIDA" con efecto glitch (capas desplazadas).
    for dx, dy, col in ((-6, 3, "#ff2d95"), (5, -2, "#45e6ff"), (0, 0, "#ffffff")):
        d.text((66 + dx, 136 + dy), "VIDA", font=f_big, fill=col)
    d.text((344, 320), ".", font=f_med, fill="#45e6ff")

    d.text((70, 402), "LEARNING COMMAND CENTER", font=f_med, fill="#f4d77f")
    d.text((70, 452), TITLE.upper(), font=f_small, fill="#8aa6bb")

    d.text((70, 522), "Observar · Verificar · Comprender · Demostrar · Avanzar",
           font=f_small, fill="#6b87a0")
    d.text((70, 566), "SENA · ZAJUNA · 48 HORAS", font=f_kicker, fill="#6b87a0")

    img.save(OUT_PNG, "PNG", optimize=True)
    print(f"  ✓ {OUT_PNG} ({os.path.getsize(OUT_PNG)} bytes)")


def write_favicon() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#45e6ff"/><stop offset="1" stop-color="#2e8bff"/>'
        '</linearGradient></defs>'
        '<rect width="64" height="64" rx="14" fill="#050d17"/>'
        '<rect x="4" y="4" width="56" height="56" rx="11" fill="none" '
        'stroke="url(#g)" stroke-width="2.5"/>'
        '<path d="M18 42 L32 16 L40 34 L46 22 L52 42" fill="none" '
        'stroke="#45e6ff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="32" cy="48" r="4" fill="#f4d77f"/>'
        '</svg>'
    )
    OUT_SVG.write_text(svg, encoding="utf-8")
    print(f"  ✓ {OUT_SVG}")


if __name__ == "__main__":
    print("Generando activos de marca VIDA:")
    write_favicon()
    try:
        build()
    except Exception as err:  # pragma: no cover
        print(f"  ✗ og_image png falló: {err}", file=sys.stderr)
        sys.exit(1)
    print("Listo.")