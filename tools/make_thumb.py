#!/usr/bin/env python3
"""Genera thumbnails 1280x720 (16:9) para YouTube del pódcast de VIDA.

Misma identidad del canal seguro, en formato de banner para clics.
Reproducible: se reconstruye cada vez que se quiera.

    python3 tools/make_thumb.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_covers import CAPS, FONT_BOLD, FONT_MONO, lerp, wrap

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "vida_ui_pro" / "thumbs"

W, H = 1280, 720


def paint_thumb(cfg: dict) -> Image.Image:
    pal = cfg["palette"]
    img = Image.new("RGB", (W, H), pal["bot"])
    d = ImageDraw.Draw(img)

    # Degradado vertical.
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(lerp(pal["top"][0], pal["bot"][0], t),
                                       lerp(pal["top"][1], pal["bot"][1], t),
                                       lerp(pal["top"][2], pal["bot"][2], t)))

    # Rejilla sutil.
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, W, 64):
        gd.line([(x, 0), (x, H)], fill=(pal["a"][0], pal["a"][1], pal["a"][2], 22), width=1)
    for y in range(0, H, 64):
        gd.line([(0, y), (W, y)], fill=(pal["a"][0], pal["a"][1], pal["a"][2], 22), width=1)
    img.paste(grid, (0, 0), grid)

    # Resplandores: uno detrás del título, otro gigante a la derecha.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([620, -140, 1360, 640], fill=pal["glow"])
    gd.ellipse([-120, 460, 620, 1000], fill=(pal["b"][0], pal["b"][1], pal["b"][2], 70))
    gd.ellipse([940, 420, 1360, 840], fill=(*pal["a"], 40))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)

    f_kick = ImageFont.truetype(FONT_MONO, 30)
    f_num = ImageFont.truetype(FONT_BOLD, 230)
    f_t = ImageFont.truetype(FONT_BOLD, 88)
    f_sub = ImageFont.truetype(FONT_MONO, 42)
    f_copy = ImageFont.truetype(FONT_MONO, 28)
    f_small = ImageFont.truetype(FONT_MONO, 26)

    # Cabecera.
    d.text((70, 54), "// BLUMIX · LAS VOCES DEL CÓDIGO · TEMPORADA 1", font=f_kick, fill=pal["a"])
    d.line([(70, 102), (830, 102)], fill=(*pal["a"], 90), width=2)

    # Número gigante con glitch + sello EP.
    num = cfg["num"]
    for dx, dy, col in ((-7, 5, pal["b"]), (6, -3, pal["a"]), (0, 0, (255, 255, 255))):
        d.text((94 + dx, 128 + dy), num, font=f_num, fill=col)
    if cfg.get("num_label") is not None:
        d.text((700, 150), "EP  " + num, font=f_sub, fill=(*pal["a"], 160), anchor="lm")

    # Título y subtítulo (zona izquierda, segura para YouTube).
    ty = 430
    for ln in wrap(d, cfg["title"], f_t, 1180):
        d.text((76, ty), ln, font=f_t, fill=(255, 255, 255))
        ty += 100
    ty += 2
    d.text((80, ty), "— " + cfg["sub"], font=f_sub, fill=pal["gold"])
    d.text((80, ty + 60), cfg["copy"], font=f_copy, fill=(214, 222, 240))

    # Orbe derecho tipo "documental futurista".
    orb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orb)
    cx, cy, r = 1090, 430, 190
    od.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*pal["a"], 140), width=3)
    od.ellipse([cx - 128, cy - 128, cx + 128, cy + 128], outline=(*pal["a"], 70), width=2)
    od.ellipse([cx - 66, cy - 66, cx + 66, cy + 66], fill=(*pal["a"], 60))
    od.arc([cx - r, cy - r, cx + r, cy + r], 0, 130, fill=pal["gold"], width=3)
    img = Image.alpha_composite(img.convert("RGBA"), orb).convert("RGB")
    d = ImageDraw.Draw(img)
    d.text((cx, cy - 22), "SUPER IAs", font=f_small, fill=(255, 255, 255), anchor="mm")
    d.text((cx, cy + 14), "ACTIVAS", font=f_small, fill=pal["gold"], anchor="mm")

    # Franja inferior.
    d.rectangle([0, H - 34, W, H], fill=(0, 0, 0, 40))
    d.text((70, H - 76), "OBSERVAR · VERIFICAR · COMPRENDER · DEMOSTRAR · AVANZAR",
           font=f_small, fill=(150, 165, 190))
    d.text((1150, H - 76), "VIDA", font=f_small, fill=pal["gold"], anchor="ra")

    return img


def write_thumbs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(ROOT.joinpath("podcast_audio").glob("*.mp3")):
        if path.name.startswith("chunk_") or path.name == "concat.txt":
            continue
        cfg = CAPS.get(path.stem)
        out = OUT_DIR / f"{path.stem}_thumb.png"
        if cfg is None:
            print(f"  · {path.name}: sin receta, se deja como está")
            continue
        img = paint_thumb(cfg)
        img.save(out, "PNG", optimize=True)
        print(f"  ✓ {out.name} ({os.path.getsize(out)} bytes) · EP {cfg['num']}")


if __name__ == "__main__":
    print("Thumbnails 1280x720 de VIDA:")
    write_thumbs()
    print("Listo.")