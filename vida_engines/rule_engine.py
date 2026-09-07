from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: str
    reason: str

class RuleEngine:
    """Reglas explícitas. Falta de evidencia => UNKNOWN."""

    def evaluate_video(self, position: float, duration: float) -> RuleResult:
        if duration <= 0:
            return RuleResult("VIDEO_COMPLETED", "UNKNOWN", "Duración no disponible.")
        ratio = position / duration
        if ratio >= 0.95:
            return RuleResult("VIDEO_COMPLETED", "VERIFIED", f"Playback observado: {ratio:.2%}.")
        return RuleResult("VIDEO_COMPLETED", "PENDING", f"Playback observado: {ratio:.2%}.")

    def evaluate_mastery(self, verification_present: bool) -> RuleResult:
        if verification_present:
            return RuleResult("MASTERY_VERIFIED", "VERIFIED", "Existe evidencia explícita de verificación.")
        return RuleResult("MASTERY_VERIFIED", "UNKNOWN", "No existe evidencia suficiente para afirmar dominio.")
