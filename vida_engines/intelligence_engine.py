from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .profiles import CourseProfile


@dataclass(frozen=True)
class IntelligenceSignal:
    """
    Señal utilizada por la inteligencia de VIDA.

    observed  = dato directamente disponible.
    inferred  = cálculo derivado de datos observados.
    predicted = predicción/recomendación.
    """

    name: str
    value: float
    source: str
    kind: str = "observed"


class IntelligenceEngine:
    """
    VIDA Intelligence Engine v3.

    Motor adaptativo, determinista y explicable.

    PRINCIPIOS:
    - No inventa evidencia.
    - No certifica dominio.
    - No convierte predicciones en hechos.
    - Separa observación, inferencia y predicción.
    - Mantiene trazabilidad.
    - Puede alimentar modelos ML posteriormente.
    """

    VERSION = "3.0"

    WEIGHTS = {
        "video": 1.0,
        "activity": 1.3,
        "concept": 1.5,
        "evidence": 1.2,
        "consistency": 0.8,
        "stagnation": 1.0,
    }

    def __init__(
        self,
        profile: "CourseProfile | None" = None,
    ) -> None:
        self._history: list[dict[str, Any]] = []
        self.profile = profile

    def _weight(self, name: str) -> float:
        """
        Obtiene el peso del perfil cuando el componente está declarado.

        Los pesos específicos de inteligencia que no forman parte del
        perfil curricular mantienen su ponderación interna heredada.

        Esto permite que CourseProfile gobierne:
            video
            activity
            mastery
            evidence

        mientras IntelligenceEngine conserva:
            consistency
            stagnation
        """
        if self.profile is not None and name in self.profile.weights:
            return self.profile.weight(name)

        return float(self.WEIGHTS.get(name, 0.0))

    # =========================================================
    # UTILIDADES
    # =========================================================

    @staticmethod
    def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return min(maximum, max(minimum, float(value)))

    @classmethod
    def _ratio(cls, done: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return cls._clamp(done / total)

    # =========================================================
    # SIGNALS
    # =========================================================

    def signals(
        self,
        course: dict[str, Any],
        completed_video_ids: set[str],
        completed_activity_ids: set[str],
        verified_concepts: set[str],
        evidence_count: int,
    ) -> list[IntelligenceSignal]:

        videos = course.get("videos", [])

        activities = [
            item
            for item in course.get("items", [])
            if item.get("kind") == "activity"
        ]

        concepts = course.get("concepts", [])

        video_progress = self._ratio(
            len(completed_video_ids),
            len(videos),
        )

        activity_progress = self._ratio(
            len(completed_activity_ids),
            len(activities),
        )

        concept_mastery = self._ratio(
            len(verified_concepts),
            len(concepts),
        )

        evidence_strength = self._clamp(
            evidence_count / 5
        )

        # -----------------------------------------------------
        # CONSISTENCY
        # -----------------------------------------------------

        consistency = self.consistency()

        # -----------------------------------------------------
        # STAGNATION
        # -----------------------------------------------------

        stagnation = self.stagnation()

        # -----------------------------------------------------
        # UNKNOWN PRESSURE
        # -----------------------------------------------------

        unknown = 0

        if videos and video_progress < 1:
            unknown += 1

        if activities and activity_progress < 1:
            unknown += 1

        if concepts and concept_mastery < 1:
            unknown += 1

        unknown_pressure = self._clamp(
            unknown / 3
        )

        return [
            IntelligenceSignal(
                "video_progress",
                video_progress,
                "course/video_progress",
            ),

            IntelligenceSignal(
                "activity_progress",
                activity_progress,
                "course/activity_progress",
            ),

            IntelligenceSignal(
                "concept_mastery",
                concept_mastery,
                "knowledge/verification",
            ),

            IntelligenceSignal(
                "evidence_strength",
                evidence_strength,
                "evidence/count",
            ),

            IntelligenceSignal(
                "consistency",
                consistency,
                "intelligence/history",
                "inferred",
            ),

            IntelligenceSignal(
                "stagnation",
                stagnation,
                "intelligence/history",
                "inferred",
            ),

            IntelligenceSignal(
                "unknown_pressure",
                unknown_pressure,
                "rule_engine",
                "inferred",
            ),
        ]

    # =========================================================
    # LEARNING SCORE
    # =========================================================

    def learning_score(
        self,
        course: dict[str, Any],
        completed_video_ids: set[str],
        completed_activity_ids: set[str],
        verified_concepts: set[str],
        evidence_count: int,
    ) -> float:

        signals = self.signals(
            course,
            completed_video_ids,
            completed_activity_ids,
            verified_concepts,
            evidence_count,
        )

        values = {
            signal.name: signal.value
            for signal in signals
        }

        positive = (
            values["video_progress"] * self._weight("video")
            + values["activity_progress"] * self._weight("activity")
            + values["concept_mastery"] * self._weight("mastery")
            + values["evidence_strength"] * self._weight("evidence")
            + values["consistency"] * self._weight("consistency")
        )

        penalty = (
            values["stagnation"] * self._weight("stagnation")
        )

        max_score = (
            self._weight("video")
            + self._weight("activity")
            + self._weight("mastery")
            + self._weight("evidence")
            + self._weight("consistency")
        )

        score = ((positive - penalty) / max_score) * 100

        return round(
            self._clamp(score / 100) * 100,
            2,
        )

    # =========================================================
    # CONSISTENCY
    # =========================================================

    def consistency(self) -> float:
        """
        Estima consistencia usando observaciones históricas.

        Si todavía no existe historial:
        devuelve 0 porque no existe evidencia suficiente.
        """

        if not self._history:
            return 0.0

        values = []

        for event in self._history:
            value = event.get("learning_signal")

            if isinstance(value, (int, float)):
                values.append(
                    self._clamp(float(value))
                )

        if not values:
            return 0.0

        return round(
            self._clamp(mean(values)),
            4,
        )

    # =========================================================
    # STAGNATION
    # =========================================================

    def stagnation(self) -> float:
        """
        Detecta ausencia de progreso reciente.

        No afirma fracaso.
        Solo produce una señal inferida.
        """

        if len(self._history) < 2:
            return 0.0

        recent = self._history[-5:]

        values = [
            event.get("learning_signal")
            for event in recent
            if isinstance(
                event.get("learning_signal"),
                (int, float),
            )
        ]

        if len(values) < 2:
            return 0.0

        delta = values[-1] - values[0]

        if delta > 0.05:
            return 0.0

        if delta < 0:
            return 1.0

        return 0.5

    # =========================================================
    # NEXT ACTIONS
    # =========================================================

    def next_actions(
        self,
        course: dict[str, Any],
        completed_video_ids: set[str],
        completed_activity_ids: set[str],
        verified_concepts: set[str],
        evidence_count: int,
    ) -> list[dict[str, str]]:

        actions: list[dict[str, str]] = []

        videos = course.get("videos", [])

        activities = [
            item
            for item in course.get("items", [])
            if item.get("kind") == "activity"
        ]

        concepts = course.get("concepts", [])

        # -----------------------------------------------------
        # ACTIVIDAD
        # -----------------------------------------------------

        for item in activities:

            item_id = item.get("id")

            if item_id not in completed_activity_ids:

                actions.append({
                    "priority": "high",
                    "type": "activity",
                    "title": str(
                        item.get(
                            "title",
                            "Actividad",
                        )
                    ),
                    "reason": "Actividad curricular pendiente.",
                    "score": "95",
                })

                break

        # -----------------------------------------------------
        # VIDEO
        # -----------------------------------------------------

        for video in videos:

            video_id = video.get("id")

            if video_id not in completed_video_ids:

                actions.append({
                    "priority": "high",
                    "type": "video",
                    "title": str(
                        video.get(
                            "title",
                            "Video",
                        )
                    ),
                    "reason": "Video curricular pendiente.",
                    "score": "90",
                })

                break

        # -----------------------------------------------------
        # CONCEPTO
        # -----------------------------------------------------

        for concept in concepts:

            concept_id = concept.get("id")

            if concept_id not in verified_concepts:

                actions.append({
                    "priority": "medium",
                    "type": "verification",
                    "title": str(
                        concept.get(
                            "title",
                            concept.get(
                                "name",
                                "Concepto",
                            ),
                        )
                    ),
                    "reason": "Concepto aún no verificado.",
                    "score": "80",
                })

                break

        # -----------------------------------------------------
        # EVIDENCIA
        # -----------------------------------------------------

        if evidence_count == 0:

            actions.append({
                "priority": "medium",
                "type": "evidence",
                "title": "Generar primera evidencia",
                "reason": "No existe evidencia registrada.",
                "score": "85",
            })

        # -----------------------------------------------------
        # ESTRATEGIA ADAPTATIVA
        # -----------------------------------------------------

        score = self.learning_score(
            course,
            completed_video_ids,
            completed_activity_ids,
            verified_concepts,
            evidence_count,
        )

        stagnation = self.stagnation()

        if stagnation >= 0.75:

            actions.append({
                "priority": "high",
                "type": "strategy",
                "title": "Romper estancamiento",
                "reason": "El historial muestra poco o ningún progreso reciente.",
                "score": "97",
            })

        elif score < 30:

            actions.append({
                "priority": "high",
                "type": "strategy",
                "title": "Construir base de aprendizaje",
                "reason": "La cobertura curricular actual es baja.",
                "score": str(int(100 - score)),
            })

        elif score < 70:

            actions.append({
                "priority": "medium",
                "type": "strategy",
                "title": "Consolidar aprendizaje",
                "reason": "Existe progreso, pero faltan señales suficientes de dominio.",
                "score": str(int(100 - score)),
            })

        else:

            actions.append({
                "priority": "low",
                "type": "strategy",
                "title": "Profundizar y demostrar",
                "reason": "La cobertura es alta; priorizar verificación y evidencia.",
                "score": str(int(score)),
            })

        return actions

    # =========================================================
    # EXPLAINABILITY
    # =========================================================

    def explain(
        self,
        course: dict[str, Any],
        completed_video_ids: set[str],
        completed_activity_ids: set[str],
        verified_concepts: set[str],
        evidence_count: int,
    ) -> dict[str, Any]:

        signals = self.signals(
            course,
            completed_video_ids,
            completed_activity_ids,
            verified_concepts,
            evidence_count,
        )

        return {
            "engine": "IntelligenceEngine",
            "version": self.VERSION,

            "learning_score": self.learning_score(
                course,
                completed_video_ids,
                completed_activity_ids,
                verified_concepts,
                evidence_count,
            ),

            "signals": [
                {
                    "name": signal.name,
                    "value": signal.value,
                    "source": signal.source,
                    "kind": signal.kind,
                }
                for signal in signals
            ],

            "history_size": len(self._history),

            "policy": {
                "evidence_required_for_certification": True,
                "prediction_is_not_evidence": True,
                "unknown_is_not_success": True,
                "observed_separated_from_inferred": True,
                "ml_prediction_cannot_certify": True,
            },
        }

    # =========================================================
    # MEMORY
    # =========================================================

    def remember(
        self,
        event: dict[str, Any],
    ) -> None:
        """
        Guarda una observación para aprendizaje adaptativo.

        Esta memoria NO modifica evidencia,
        progreso oficial ni certificación.
        """

        self._history.append(
            dict(event)
        )

    def history(self) -> list[dict[str, Any]]:
        return list(self._history)
