from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

class MediaEngine:
    """Descubre y verifica metadata de medios locales."""

    EXTENSIONS = {".mp4", ".webm", ".ogv", ".mkv", ".mov"}

    def __init__(self, media_dir: str | Path):
        self.media_dir = Path(media_dir)

    def scan(self) -> list[dict]:
        self.media_dir.mkdir(parents=True, exist_ok=True)
        result = []
        for path in sorted(self.media_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in self.EXTENSIONS:
                continue
            result.append({
                "file": str(path.relative_to(self.media_dir)),
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "duration": self.duration(path),
            })
        return result

    def duration(self, path: Path) -> float | None:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            text=True, capture_output=True, check=False
        )
        try:
            return float(proc.stdout.strip())
        except (TypeError, ValueError):
            return None
