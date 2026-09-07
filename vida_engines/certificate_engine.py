from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Certificate:
    certificate_id: str
    course_id: str
    learner: str
    course: str
    issued_at: str
    operational_progress: int
    mastery: int
    evidence_count: int
    required_videos: int
    completed_videos: int
    required_activities: int
    completed_activities: int
    required_concepts: int
    verified_concepts: int
    status: str
    verification_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CertificateNotEligible(RuntimeError):
    """VIDA cannot issue a certificate because a required condition is unmet."""


class CertificateAlreadyIssued(RuntimeError):
    """Exactly one certificate is allowed per course."""


class CertificateEngine:
    """
    Emits exactly ONE personal VIDA certificate per course.

    The engine never infers eligibility. Every required condition must be
    explicitly satisfied by observed/verified data supplied by the caller.

    This is NOT an official SENA certificate.
    """

    STATUS = "PERSONAL_VERIFIED"

    def __init__(self, out_dir: str | Path):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def _course_record(self, course_id: str) -> Path:
        safe = "".join(ch for ch in course_id if ch.isalnum() or ch in "-_ .")
        safe = safe.strip().replace(" ", "_") or "course"
        return self.out_dir / f"{safe}.issued.json"

    def is_issued(self, course_id: str) -> bool:
        return self._course_record(course_id).exists()

    def eligibility_report(
        self,
        *,
        operational: int,
        mastery: int,
        evidence_count: int,
        required_videos: int,
        completed_videos: int,
        required_activities: int,
        completed_activities: int,
        required_concepts: int,
        verified_concepts: int,
        unknown_count: int,
        user_confirmation: bool,
    ) -> dict[str, Any]:
        checks = {
            "operational_100": operational >= 100,
            "mastery_100": mastery >= 100,
            "evidence_present": evidence_count > 0,
            "videos_complete": completed_videos >= required_videos,
            "activities_complete": completed_activities >= required_activities,
            "concepts_verified": verified_concepts >= required_concepts,
            "no_unknown_required": unknown_count == 0,
            "user_confirmation": user_confirmation is True,
        }
        return {
            "eligible": all(checks.values()),
            "checks": checks,
        }

    def issue_once(
        self,
        *,
        course_id: str,
        learner: str,
        course: str,
        operational: int,
        mastery: int,
        evidence_count: int,
        required_videos: int,
        completed_videos: int,
        required_activities: int,
        completed_activities: int,
        required_concepts: int,
        verified_concepts: int,
        unknown_count: int,
        user_confirmation: bool,
    ) -> Certificate:
        record = self._course_record(course_id)

        if record.exists():
            raise CertificateAlreadyIssued(
                f"Ya existe un certificado único para el curso '{course_id}'."
            )

        report = self.eligibility_report(
            operational=operational,
            mastery=mastery,
            evidence_count=evidence_count,
            required_videos=required_videos,
            completed_videos=completed_videos,
            required_activities=required_activities,
            completed_activities=completed_activities,
            required_concepts=required_concepts,
            verified_concepts=verified_concepts,
            unknown_count=unknown_count,
            user_confirmation=user_confirmation,
        )

        if not report["eligible"]:
            failed = [key for key, ok in report["checks"].items() if not ok]
            raise CertificateNotEligible(
                "Certificado no elegible. Condiciones pendientes: "
                + ", ".join(failed)
            )

        issued_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "course_id": course_id,
            "learner": learner,
            "course": course,
            "issued_at": issued_at,
            "operational_progress": 100,
            "mastery": 100,
            "evidence_count": evidence_count,
            "required_videos": required_videos,
            "completed_videos": completed_videos,
            "required_activities": required_activities,
            "completed_activities": completed_activities,
            "required_concepts": required_concepts,
            "verified_concepts": verified_concepts,
            "status": self.STATUS,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        certificate_id = f"VIDA-{course_id.upper()}-{digest[:12].upper()}"

        cert = Certificate(
            certificate_id=certificate_id,
            course_id=course_id,
            learner=learner,
            course=course,
            issued_at=issued_at,
            operational_progress=100,
            mastery=100,
            evidence_count=evidence_count,
            required_videos=required_videos,
            completed_videos=completed_videos,
            required_activities=required_activities,
            completed_activities=completed_activities,
            required_concepts=required_concepts,
            verified_concepts=verified_concepts,
            status=self.STATUS,
            verification_hash=digest,
        )

        # Atomic create: if another process wins the race, issuance fails.
        record.parent.mkdir(parents=True, exist_ok=True)
        temp = record.with_suffix(record.suffix + ".tmp")
        temp.write_text(
            json.dumps(cert.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        try:
            temp.replace(record)
        except FileExistsError as exc:
            temp.unlink(missing_ok=True)
            raise CertificateAlreadyIssued(
                f"Ya existe un certificado único para el curso '{course_id}'."
            ) from exc

        return cert
