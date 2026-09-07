from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .profiles import CourseProfile


@dataclass(frozen=True)
class ProgressSnapshot:
    """
    Estado de progreso calculado por VIDA.

    Principios:
    - operational != mastery
    - mastery != evidence
    - 0/0 no significa necesariamente 0%
    - los valores derivados deben ser reproducibles
    """

    operational: int
    mastery: int
    evidence_count: int
    unknown_count: int

    # Métricas detalladas.
    video_progress: float = 0.0
    activity_progress: float = 0.0
    concept_progress: float = 0.0
    evidence_strength: float = 0.0

    # Indica si existen datos suficientes para calcular cada componente.
    video_available: bool = False
    activity_available: bool = False
    concept_available: bool = False


class ProgressEngine:
    """
    Motor central de progreso de VIDA v4.

    El motor NO interpreta ni certifica dominio.
    Solamente calcula métricas derivadas de datos observables.

    Capas:
        datos observados
              ↓
        ratios verificables
              ↓
        progreso operacional
              ↓
        snapshot explicable
    """

    VERSION = "4.0"

    DEFAULT_WEIGHTS = {
        "video": 0.45,
        "activity": 0.55,
    }

    MAX_EVIDENCE_FOR_STRENGTH = 5

    @staticmethod
    def _validate_count(name: str, value: int) -> int:
        if isinstance(value, bool):
            raise TypeError(f"{name} debe ser un entero, no bool.")

        if not isinstance(value, int):
            raise TypeError(f"{name} debe ser int.")

        if value < 0:
            raise ValueError(f"{name} no puede ser negativo.")

        return value

    @classmethod
    def _ratio(cls, done: int, total: int) -> tuple[float, bool]:
        """
        Devuelve (ratio, available).

        Importante:
            0/0 -> (0.0, False)
            0/5 -> (0.0, True)
            5/5 -> (1.0, True)
        """
        done = cls._validate_count("done", done)
        total = cls._validate_count("total", total)

        if total == 0:
            return 0.0, False

        # Protege contra estados imposibles.
        done = min(done, total)

        return done / total, True

    @staticmethod
    def _clamp(
        value: float,
        minimum: float = 0.0,
        maximum: float = 1.0,
    ) -> float:
        return min(maximum, max(minimum, float(value)))

    @classmethod
    def _weight(
        cls,
        name: str,
        profile: CourseProfile | None,
    ) -> float:
        if profile is not None:
            weight = profile.weight(name)
        else:
            weight = cls.DEFAULT_WEIGHTS.get(name, 0.0)

        weight = float(weight)

        if weight < 0:
            raise ValueError(
                f"El peso '{name}' no puede ser negativo."
            )

        return weight

    @classmethod
    def _operational_score(
        cls,
        video_progress: float,
        video_available: bool,
        activity_progress: float,
        activity_available: bool,
        profile: CourseProfile | None,
    ) -> int:
        """
        Calcula únicamente progreso operacional.

        No mezcla mastery ni evidence porque conceptualmente
        son dimensiones diferentes.
        """

        components: list[tuple[float, float]] = []

        if video_available:
            components.append(
                (
                    video_progress,
                    cls._weight("video", profile),
                )
            )

        if activity_available:
            components.append(
                (
                    activity_progress,
                    cls._weight("activity", profile),
                )
            )

        if not components:
            return 0

        total_weight = sum(weight for _, weight in components)

        if total_weight <= 0:
            return 0

        score = sum(
            progress * weight
            for progress, weight in components
        ) / total_weight

        return round(cls._clamp(score) * 100)

    @classmethod
    def _evidence_strength(
        cls,
        evidence_count: int,
    ) -> float:
        """
        Fuerza relativa de evidencia.

        Esto NO representa dominio.
        Solamente normaliza la cantidad de registros disponibles.
        """
        return cls._clamp(
            evidence_count / cls.MAX_EVIDENCE_FOR_STRENGTH
        )

    def calculate(
        self,
        completed_videos: int,
        total_videos: int,
        completed_activities: int,
        total_activities: int,
        verified_concepts: int = 0,
        total_concepts: int = 0,
        evidence_count: int = 0,
        unknown_count: int = 0,
        profile: CourseProfile | None = None,
    ) -> ProgressSnapshot:
        """
        Calcula un snapshot completo y determinista.

        Los parámetros originales se mantienen para compatibilidad.
        """

        evidence_count = self._validate_count(
            "evidence_count",
            evidence_count,
        )

        unknown_count = self._validate_count(
            "unknown_count",
            unknown_count,
        )

        video_progress, video_available = self._ratio(
            completed_videos,
            total_videos,
        )

        activity_progress, activity_available = self._ratio(
            completed_activities,
            total_activities,
        )

        concept_progress, concept_available = self._ratio(
            verified_concepts,
            total_concepts,
        )

        operational = self._operational_score(
            video_progress,
            video_available,
            activity_progress,
            activity_available,
            profile,
        )

        mastery = round(
            self._clamp(concept_progress) * 100
        )

        evidence_strength = self._evidence_strength(
            evidence_count
        )

        return ProgressSnapshot(
            operational=max(0, min(100, operational)),
            mastery=max(0, min(100, mastery)),
            evidence_count=evidence_count,
            unknown_count=unknown_count,
            video_progress=video_progress,
            activity_progress=activity_progress,
            concept_progress=concept_progress,
            evidence_strength=evidence_strength,
            video_available=video_available,
            activity_available=activity_available,
            concept_available=concept_available,
        )
