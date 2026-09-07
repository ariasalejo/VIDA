from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .profiles import CourseProfile


class ProfileEngine:
    """
    Carga y valida perfiles de cursos.

    Principio:

        CURSO = CONFIGURACIÓN
        PROGRESO = ESTADO
        EVIDENCIA = HECHOS
        INTELIGENCIA = INTERPRETACIÓN

    El cambio de curso debe realizarse mediante un perfil,
    no modificando los motores internos.
    """

    def __init__(self, store: str | Path):
        self.store = Path(store)

    def load(self) -> CourseProfile:
        if not self.store.exists():
            raise FileNotFoundError(
                f"Perfil no encontrado: {self.store}"
            )

        data: dict[str, Any] = json.loads(
            self.store.read_text(encoding="utf-8")
        )

        profile = CourseProfile(
            course_id=str(data["course_id"]),
            name=str(data["name"]),
            version=str(data.get("version", "1.0")),
            components=dict(data.get("components", {})),
            weights=dict(data.get("weights", {})),
            metadata=dict(data.get("metadata", {})),
        )

        profile.validate()

        return profile

    def save(self, profile: CourseProfile) -> None:
        profile.validate()

        self.store.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            "course_id": profile.course_id,
            "name": profile.name,
            "version": profile.version,
            "components": profile.components,
            "weights": profile.weights,
            "metadata": profile.metadata,
        }

        self.store.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    def describe(self, profile: CourseProfile) -> dict[str, Any]:
        return {
            "course_id": profile.course_id,
            "name": profile.name,
            "version": profile.version,
            "components": profile.enabled_components(),
            "weights": dict(profile.weights),
            "metadata": dict(profile.metadata),
        }
