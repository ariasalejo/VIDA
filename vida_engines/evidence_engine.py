from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

@dataclass
class Evidence:
    evidence_id: str
    source: str
    method: str
    event_type: str
    result: str
    context: dict[str, Any]
    observed_at: str
    status: str = "OBSERVED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class EvidenceEngine:
    """Observation -> Method -> Evidence -> Context -> Result."""

    def __init__(self, store: str | Path):
        self.store = Path(store)
        self.store.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if not self.store.exists():
            return []
        return json.loads(self.store.read_text(encoding="utf-8"))

    def record(self, source: str, method: str, event_type: str, result: str, context: dict[str, Any] | None = None) -> Evidence:
        payload = {
            "source": source,
            "method": method,
            "event_type": event_type,
            "result": result,
            "context": context or {},
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        evidence = Evidence(evidence_id=f"EV-{digest.upper()}", **payload)
        data = self._load()
        data.append(evidence.to_dict())
        self.store.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return evidence

    def all(self) -> list[dict[str, Any]]:
        return self._load()
