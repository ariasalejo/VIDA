#!/usr/bin/env python3
"""Genera el podcast a partir del guion markdown usando edge-tts (voz Salome, es-CO).

Voz por defecto: es-CO-SalomeNeural (profesora colombiana, natural y cálida).
Uso:
    python3 graba_podcast.py                 # genera solo lo que falta
    python3 graba_podcast.py --force         # regenera todo desde cero
    python3 graba_podcast.py --voice es-MX-DaliaNeural
"""
import argparse
import asyncio
import re
import subprocess
import time
from pathlib import Path

import edge_tts

BASE = Path(__file__).resolve().parent
GUIDE = BASE / "podcast_guion_ciberseguridad.md"
OUT_DIR = BASE / "podcast_audio"
FINAL = OUT_DIR / "podcast_ciberseguridad_1h.mp3"

DEFAULT_VOICE = "es-CO-SalomeNeural"
DEFAULT_RATE = "-6%"
DEFAULT_PITCH = "+10Hz"


def resolve_paths(guide: Path) -> "tuple[Path, Path]":
    """Deriva carpeta y archivo final según el guion elegido.

    El guion principal (podcast_guion_ciberseguridad.md) mantiene sus rutas de
    siempre. Los demás guiones (ej. podcast_guion_capitulo2.md) generan su
    propia carpeta (capitulo2) y su archivo final (podcast_capitulo2.mp3).
    """
    guide = Path(guide)
    if guide.resolve() == (BASE / "podcast_guion_ciberseguridad.md").resolve():
        return OUT_DIR, FINAL
    stem = guide.stem  # podcast_guion_capitulo2
    sub = stem.replace("podcast_guion_", "").replace("podcast_", "") or "audio"
    out = BASE / "podcast_audio" / sub
    name = "podcast_" + sub + ".mp3"
    return out, out / name


def clean(text: str) -> str:
    text = re.sub(r"^#{1,6}.*$", "", text, flags=re.M)
    text = re.sub(r"^\*\(.*?\)\*$", "", text, flags=re.M)
    text = re.sub(r"^\s*\*", "", text, flags=re.M)
    text = re.sub(r"^[-|`].*$", "", text, flags=re.M)
    text = re.sub(r"^\[.*?\]$", "", text, flags=re.M)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\[|\]", "", text)
    text = re.sub(r"\bNARRADOR:\b", "", text)
    text = re.sub(r"\bPROFESORA:\b", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("sabe识别", "sabe identificar")
    text = text.replace("creeme", "créeme")
    text = text.replace("tranquilo", "tranquilo")
    return text.strip()


def split_paragraphs(text: str, max_chars: int = 950) -> list[str]:
    chunks = []
    for para in re.split(r"\n\s*\n", text):
        para = clean(para)
        if len(para) < 40:
            continue
        while len(para) > max_chars:
            cut = para.rfind(".", 0, max_chars)
            if cut < max_chars * 0.6:
                cut = para.rfind(" ", 0, max_chars)
                if cut < 200:
                    cut = max_chars
            chunks.append(para[: cut + 1])
            para = para[cut + 1 :].strip()
        if para:
            chunks.append(para)
    return chunks


async def gen_chunk(i: int, text: str, voice: str, rate: str, pitch: str) -> str:
    f = OUT_DIR / f"chunk_{i:03d}.mp3"
    if f.exists() and f.stat().st_size > 1000:
        return str(f)
    tmp = OUT_DIR / f"chunk_{i:03d}.tmp.mp3"
    if tmp.exists():
        tmp.unlink()
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    last_err: Exception | None = None
    for attempt in range(8):
        try:
            await communicate.save(str(tmp))
            if tmp.stat().st_size <= 1000:
                raise RuntimeError("chunk vacío")
            tmp.replace(f)
            return str(f)
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"No se pudo generar el chunk {i}: {last_err}")


async def main_async(args: argparse.Namespace) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    text = GUIDE.read_text(encoding="utf-8")
    chunks = split_paragraphs(text)
    print(
        f"Generando {len(chunks)} clips con edge-tts ({args.voice}) "
        f"rate={args.rate} pitch={args.pitch}..."
    )
    t0 = time.time()
    sem = asyncio.Semaphore(args.workers)

    async def worker(i: int, chunk: str) -> str:
        async with sem:
            return await gen_chunk(i, chunk, args.voice, args.rate, args.pitch)

    tasks = [
        asyncio.create_task(worker(i, c)) for i, c in enumerate(chunks)
    ]
    results = await asyncio.gather(*tasks)
    print(f"TTS listo en {time.time() - t0:.1f}s")
    for r in results:
        print("  ", Path(r).name)

    print("Concatenando con ffmpeg...")
    concat_file = OUT_DIR / "concat.txt"
    ordered = [f"file 'chunk_{i:03d}.mp3'" for i, _ in enumerate(chunks)]
    concat_file.write_text("\n".join(ordered) + "\n", encoding="utf-8")
    final_tmp = OUT_DIR / (FINAL.name + ".tmp.mp3")
    cmd = (
        f"ffmpeg -y -f concat -safe 0 -i {concat_file.name} "
        f"-c:a libmp3lame -b:a 128k -ar 44100 {final_tmp.name}"
    )
    subprocess.run(cmd, shell=True, cwd=OUT_DIR, check=True)
    final_tmp.replace(FINAL)
    print(f"\nPodcast final: {FINAL}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el podcast con edge-tts")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Voz edge-tts")
    parser.add_argument("--rate", default=DEFAULT_RATE, help="Velocidad (ej: -6%%)")
    parser.add_argument("--pitch", default=DEFAULT_PITCH, help="Tono (ej: +10Hz)")
    parser.add_argument("--workers", type=int, default=6, help="Clips en paralelo")
    parser.add_argument(
        "--force", action="store_true", help="Regenerar todos los chunks"
    )
    args = parser.parse_args()

    if args.force:
        for f in OUT_DIR.glob("chunk_*.mp3"):
            f.unlink()
        print("Chunks anteriores eliminados")

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()