#!/usr/bin/env python3
"""Genera portadas cuadradas (1000x1000) para cada pódcast de VIDA.

Cada episodio del canal seguro recibe su propio cuadro con identidad propia.
Reproducible: reconstruye las portadas cada vez que se quiera.

    python3 tools/make_covers.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "podcast_audio"
OUT_DIR = ROOT / "vida_ui_pro" / "covers"

FONT_BOLD = "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
FONT_MONO = "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf"

SIZE = 1000

CAPS = {
    "podcast_ciberseguridad_1h": {
        "num": "01",
        "title": "Ciberseguridad y Código",
        "sub": "Tu primera zancada",
        "copy": "BLUMIX · LAS VOCES DEL CÓDIGO · QUÉ ES LA CIBERSEGURIDAD · TRÍADA CIA · DÓNDE EMPIEZAS",
        "palette": {
            "top": (8, 20, 46), "bot": (4, 7, 18),
            "a": (69, 230, 255), "b": (46, 139, 255), "gold": (244, 215, 127),
            "glow": (46, 139, 255, 78),
        },
        "theme": "shield",
    },
    "podcast_capitulo2_1h": {
        "num": "02",
        "title": "Tu castillo y tu llave",
        "sub": "Los anzuelos invisibles",
        "copy": "BLUMIX · LAS VOCES DEL CÓDIGO · CONTRASEÑAS · PHISHING · RANSOMWARE · INGENIERÍA SOCIAL",
        "palette": {
            "top": (18, 6, 40), "bot": (5, 2, 16),
            "a": (255, 121, 66), "b": (181, 78, 209), "gold": (244, 215, 127),
            "glow": (255, 121, 66, 80),
        },
        "theme": "castle",
    },
    "podcast_superias_1h": {
        "num": "03",
        "title": "Secretos de la programación",
        "sub": "Conversación con las súper IAs",
        "copy": "BLUMIX × OPENCODE · SECRETOS DE LA PROGRAMACIÓN · EL MEJOR MOMENTO",
        "palette": {
            "top": (34, 8, 56), "bot": (10, 3, 22),
            "a": (255, 45, 149), "b": (139, 92, 246), "gold": (244, 215, 127),
            "glow": (255, 45, 149, 80),
        },
        "theme": "ai",
    },
    "podcast_camino_principiante_1h": {
        "num": "04",
        "title": "El camino del principiante",
        "sub": "Monólogo de la súper IA",
        "copy": "BLUMIX · LAS VOCES DEL CÓDIGO · APRENDER · PRACTICAR · NO RENDIRSE · AVANZAR",
        "palette": {
            "top": (6, 30, 26), "bot": (2, 12, 11),
            "a": (71, 224, 183), "b": (46, 139, 255), "gold": (244, 215, 127),
            "glow": (71, 224, 183, 78),
        },
        "theme": "path",
    },
}

# Portada «inicial» de la temporada: el cuadro de cabecera del canal seguro.
# Se sirve en /static/covers/seasons/temporada_1.png (no depende de un MP3).
SEASONS = {
    "temporada_1": {
        "num": "1",
        "num_label": None,
        "title": "Las Voces del Código",
        "sub": "Temporada 1 · BLUMIX y las súper IAs",
        "copy": "CANAL SEGURO DEL APRENDIZ · CIBERSEGURIDAD Y PROGRAMACIÓN SIN HUMO",
        "palette": {
            "top": (10, 16, 48), "bot": (3, 5, 16),
            "a": (69, 230, 255), "b": (255, 45, 149), "gold": (244, 215, 127),
            "glow": (255, 45, 149, 70),
        },
    },
}


def lerp(a, b, t):
    return int(a + (b - a) * t)


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if draw.textlength(cur + " " + w, font=font) <= max_w or not cur:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def paint_cover(cfg: dict) -> Image.Image:
    pal = cfg["palette"]
    img = Image.new("RGB", (SIZE, SIZE), pal["bot"])
    d = ImageDraw.Draw(img)

    # Degradado vertical.
    for y in range(SIZE):
        t = y / SIZE
        d.line([(0, y), (SIZE, y)], fill=(lerp(pal["top"][0], pal["bot"][0], t),
                                          lerp(pal["top"][1], pal["bot"][1], t),
                                          lerp(pal["top"][2], pal["bot"][2], t)))

    # Rejilla sutil.
    grid = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, SIZE, 48):
        gd.line([(x, 0), (x, SIZE)], fill=(pal["a"][0], pal["a"][1], pal["a"][2], 24), width=1)
    for y in range(0, SIZE, 48):
        gd.line([(0, y), (SIZE, y)], fill=(pal["a"][0], pal["a"][1], pal["a"][2], 24), width=1)
    img.paste(grid, (0, 0), grid)

    # Resplandores.
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-200, -180, 520, 340], fill=pal["glow"])
    gd.ellipse([520, 430, 1250, 1150], fill=(pal["b"][0], pal["b"][1], pal["b"][2], 60))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)

    f_kick = ImageFont.truetype(FONT_MONO, 34)
    f_num = ImageFont.truetype(FONT_BOLD, 300)
    f_t = ImageFont.truetype(FONT_BOLD, 64)
    f_sub = ImageFont.truetype(FONT_MONO, 40)
    f_copy = ImageFont.truetype(FONT_MONO, 26)
    f_small = ImageFont.truetype(FONT_MONO, 30)

    # Cabecera.
    d.text((70, 62), cfg.get("kick", "// BLUMIX · LAS VOCES DEL CÓDIGO · TEMPORADA 1"), font=f_kick, fill=pal["a"])
    d.line([(70, 118), (930, 118)], fill=(*pal["a"], 90), width=2)

    # Número gigante con sombra glitch.
    num = cfg["num"]
    w_num = d.textlength(num + ".", font=f_num)
    x_num, y_num = 96, 150
    for dx, dy, col in ((-7, 4, pal["b"]), (6, -3, pal["a"]), (0, 0, (255, 255, 255))):
        d.text((x_num + dx, y_num + dy), num, font=f_num, fill=col)
    d.text((x_num + w_num - 40, y_num + 208), ".", font=f_num, fill=pal["gold"])
    if cfg.get("num_label") is not None:
        d.text((546, -16), cfg["num_label"], font=f_sub, fill=(*pal["a"], 150))

    # Sombra interior inferior.
    d.rectangle([0, 700, SIZE, SIZE], fill=(0, 0, 0, 0))

    # Título y subtítulo.
    ty = 560
    for ln in wrap(d, cfg["title"], f_t, SIZE - 156):
        d.text((78, ty), ln, font=f_t, fill=(255, 255, 255))
        ty += 76
    ty += 4
    d.text((80, ty), "— " + cfg["sub"], font=f_sub, fill=pal["gold"])
    d.text((80, ty + 58), cfg["copy"], font=f_copy, fill=(210, 220, 240))

    # Firma inferior.
    d.text((80, 940), "OBSERVAR · VERIFICAR · COMPRENDER · DEMOSTRAR · AVANZAR",
           font=f_small, fill=(150, 165, 190))
    d.text((80, 62 + 0), "", font=f_small, fill=pal["a"])

    return img


def write_season_art() -> None:
    """Portada «inicial» de la temporada (cuadrada 1400x1400 + thumb 1280x720)."""
    from make_thumb import paint_thumb  # misma identidad, en formato banner

    seasons_dir = ROOT / "vida_ui_pro" / "covers" / "seasons"
    thumbs_dir = ROOT / "vida_ui_pro" / "thumbs" / "seasons"
    for key, cfg in SEASONS.items():
        art = paint_cover(cfg)
        art_hi = art.resize((1400, 1400), Image.LANCZOS)
        seasons_dir.mkdir(parents=True, exist_ok=True)
        art_hi.save(seasons_dir / f"{key}.png", "PNG", optimize=True)
        banner = paint_thumb(cfg)
        thumbs_dir.mkdir(parents=True, exist_ok=True)
        banner.save(thumbs_dir / f"{key}_thumb.png", "PNG", optimize=True)
        print(
            f"  ✓ temporada {key}.png ({os.path.getsize(seasons_dir / (key + '.png'))} bytes) · "
            f"1350x1350 + thumb 1280x720"
        )


def write_covers() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(AUDIO_DIR.glob("*.mp3")):
        if path.name.startswith("chunk_") or path.name == "concat.txt":
            continue
        cfg = CAPS.get(path.stem)
        out = OUT_DIR / f"{path.stem}.png"
        if cfg is None:
            print(f"  · {path.name}: sin receta, se deja como está")
            continue
        art = paint_cover(cfg)
        # Apple/Spotify exigen arte de al menos 1400x1400 px para los feeds.
        art_hi = art.resize((1400, 1400), Image.LANCZOS)
        art_hi.save(out, "PNG", optimize=True)
        print(f"  ✓ {out.name} ({os.path.getsize(out)} bytes) · {cfg['num']} · 1400x1400")


if __name__ == "__main__":
    print("Portadas del canal seguro VIDA:")
    write_season_art()
    write_covers()
    print("Listo.")