#!/usr/bin/env python3
"""Genera podcasts a partir de guiones markdown usando edge-tts.

Uso:
    python3 graba_podcast.py                          # podcast principal (Salome, es-CO)
    python3 graba_podcast.py --guide podcast_guion_superias.md --music
    python3 graba_podcast.py --guide podcast_guion_superias.md --force --music
"""
import argparse
import asyncio
import re
import subprocess
import time
from pathlib import Path

import edge_tts

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "podcast_audio"
FINAL = OUT_DIR / "podcast_ciberseguridad_1h.mp3"
GUIDE = BASE / "podcast_guion_ciberseguridad.md"

DEFAULT_VOICE = "es-CO-SalomeNeural"
DEFAULT_RATE = "-6%"
DEFAULT_PITCH = "+10Hz"

# Voces por hablante para el guion de Las Voces del Código (cap. 03).
SPEAKERS: dict[str, dict[str, dict[str, str]]] = {
    "superias": {
        "BLUMIX": {"voice": "es-CO-GonzaloNeural", "rate": "-10%", "pitch": "+8Hz"},
        "OPENCODE": {"voice": "es-MX-JorgeNeural", "rate": "-10%", "pitch": "+6Hz"},
    },
}


def resolve_paths(guide: Path) -> "tuple[Path, Path]":
    """Deriva carpeta y archivo final según el guion elegido.

    El guion principal mantiene sus rutas. Los demás guiones generan su propia
    carpeta (ej. superias) y su archivo final.
    """
    guide = Path(guide)
    if guide.resolve() == (BASE / "podcast_guion_ciberseguridad.md").resolve():
        return OUT_DIR, FINAL
    stem = guide.stem  # ej. podcast_guion_superias
    sub = stem.replace("podcast_guion_", "").replace("podcast_", "") or "audio"
    out = BASE / "podcast_audio" / sub
    if sub == "superias":
        # El catálogo (/api/podcast) solo lista *.mp3 en podcast_audio raíz.
        return out, BASE / "podcast_audio" / "podcast_superias_1h.mp3"
    return out, out / ("podcast_" + sub + ".mp3")


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


def parse_speakers(text: str, speakers: dict[str, dict[str, str]]) -> list[tuple[str, dict]]:
    """Convierte el guion con marcadores **HABLANTE:** en pares (texto, voz)."""
    turns: list[tuple[str, str]] = []
    for line in text.splitlines():
        m = re.match(r"^\*\*(BLUMIX|OPENCODE):\*\*(.*)$", line.strip())
        if m:
            body = m.group(2).strip()
            if body:
                turns.append((m.group(1), body))
    jobs: list[tuple[str, dict]] = []
    for speaker, body in turns:
        cfg = speakers.get(speaker)
        if cfg is None:
            raise SystemExit(f"Hablante desconocido: {speaker}")
        for para in split_paragraphs(body):
            jobs.append((para, cfg))
    return jobs


async def gen_chunk(i: int, text: str, cfg: dict, out: Path) -> str:
    f = out / f"chunk_{i:03d}.mp3"
    if f.exists() and f.stat().st_size > 1000:
        return str(f)
    tmp = out / f"chunk_{i:03d}.tmp.mp3"
    if tmp.exists():
        tmp.unlink()
    communicate = edge_tts.Communicate(
        text, cfg["voice"], rate=cfg["rate"], pitch=cfg["pitch"]
    )
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


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    ).stdout.strip()
    return float(out or 0)


def make_music_pad(pad: Path, dur: float) -> None:
    """Sintetiza un manto ambiental suave (pad en acordes) con ffmpeg."""
    a = "0.055*sin(2*PI*220*t)"
    b = "0.040*sin(2*PI*277.18*t)"
    c = "0.036*sin(2*PI*329.63*t)"
    e = "0.022*sin(2*PI*440*t)"
    expr = "+".join([a, b, c, e])
    cmd = (
        f"ffmpeg -y -f lavfi -i "
        f"\"aevalsrc={expr}:s=44100:d={dur:.2f}\" "
        f"-af \"lowpass=f=2000,tremolo=f=0.12:d=0.6,volume=0.7\" -ar 44100 -ac 2 {pad}"
    )
    subprocess.run(cmd, shell=True, check=True, capture_output=True)


async def main_async(args: argparse.Namespace) -> None:
    guide = Path(args.guide)
    out, final = resolve_paths(guide)
    OUT_DIR.mkdir(exist_ok=True)
    out.mkdir(exist_ok=True)
    text = guide.read_text(encoding="utf-8")

    sub = guide.stem.replace("podcast_guion_", "")
    speakers = SPEAKERS.get(sub)
    if speakers:
        jobs = parse_speakers(text, speakers)
        chips: list[tuple[Path, str]] = []
    else:
        chips = []
        jobs = [("", {"voice": args.voice, "rate": args.rate, "pitch": args.pitch})]
        full = split_paragraphs(text)
        # pares locales solo para nombres: (chunk_text, cfg) en orden
        jobs = [(c, {"voice": args.voice, "rate": args.rate, "pitch": args.pitch}) for c in full]

    print(
        f"Generando {len(jobs)} clips con edge-tts "
        f"({'/'.join(v['voice'] for v in speakers.values()) if speakers else args.voice})..."
    )
    t0 = time.time()
    sem = asyncio.Semaphore(args.workers)

    async def worker(i: int, text: str, cfg: dict) -> str:
        async with sem:
            return await gen_chunk(i, text, cfg, out)

    tasks = [asyncio.create_task(worker(i, t, cfg)) for i, (t, cfg) in enumerate(jobs)]
    results = await asyncio.gather(*tasks)
    print(f"TTS listo en {time.time() - t0:.1f}s")

    print("Concatenando con ffmpeg...")
    ordered = "\n".join(f"file 'chunk_{i:03d}.mp3'" for i, _ in enumerate(jobs)) + "\n"
    (out / "concat.txt").write_text(ordered, encoding="utf-8")
    speech = out / "speech.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
         "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", str(speech)],
        check=True, cwd=out,
    )

    if args.music:
        print("Mezclando música de fondo suave...")
        pad = out / "pad.wav"
        dur = duration(speech)
        make_music_pad(pad, dur)
        tmp = out / (final.name + ".tmp.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(speech), "-i", str(pad),
             "-filter_complex",
             "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=3:normalize=0",
             "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", str(tmp)],
            check=True,
        )
        tmp.replace(final)
        pad.unlink(missing_ok=True)
    else:
        speech.replace(final)

    speech.unlink(missing_ok=True)
    print(f"\nPodcast final: {final}")
    print(f"Duración: {duration(final)/60:.1f} minutos")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera podcasts con edge-tts")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Voz edge-tts")
    parser.add_argument("--rate", default=DEFAULT_RATE, help="Velocidad (ej: -6%%)")
    parser.add_argument("--pitch", default=DEFAULT_PITCH, help="Tono (ej: +10Hz)")
    parser.add_argument("--guide", default=str(GUIDE), help="Guion markdown a usar")
    parser.add_argument("--music", action="store_true", help="Mezclar música de fondo")
    parser.add_argument("--workers", type=int, default=8, help="Clips en paralelo")
    parser.add_argument("--force", action="store_true", help="Regenerar todos los chunks")
    args = parser.parse_args()

    if args.force:
        guide = Path(args.guide)
        out, _ = resolve_paths(guide)
        for f in out.glob("chunk_*.mp3"):
            f.unlink()
        print("Chunks anteriores eliminados")

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()