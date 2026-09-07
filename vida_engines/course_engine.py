from __future__ import annotations
import json
from pathlib import Path
from typing import Any

class CourseEngine:
    """Carga el manifiesto curricular. No inventa contenidos."""

    def __init__(self, manifest: str | Path):
        self.path = Path(manifest)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"Course manifest no existe: {self.path}")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("El manifiesto debe ser un objeto JSON.")
        return data

    def videos(self) -> list[dict[str, Any]]:
        return list(self.load().get("videos", []))

    def activities(self) -> list[dict[str, Any]]:
        return [x for x in self.load().get("items", []) if x.get("kind") == "activity"]

    def concepts(self) -> list[dict[str, Any]]:
        return list(self.load().get("concepts", []))
