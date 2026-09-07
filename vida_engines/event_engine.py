#!/usr/bin/env python3

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EventEngine:
    """
    Registro de hechos observados.

    Principio:
        EVENTO != INTERPRETACIÓN

    Este motor no decide si algo es bueno, malo,
    aprendido, dominado o certificado.

    Solo registra lo que realmente ocurrió.
    """

    VALID_TYPES = {
        "VIDEO_OPEN",
        "VIDEO_PLAY",
        "VIDEO_PAUSE",
        "VIDEO_HEARTBEAT",
        "VIDEO_COMPLETE",
        "ACTIVITY_OPEN",
        "ACTIVITY_COMPLETE",
        "CONCEPT_OPEN",
        "CONCEPT_VERIFY",
        "STUDY_START",
        "STUDY_END",
    }

    def __init__(
        self,
        store: str | Path,
    ) -> None:
        self.store = Path(store)
        self.store.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.store.exists():
            self.store.write_text(
                "[]\n",
                encoding="utf-8",
            )

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(
                self.store.read_text(
                    encoding="utf-8"
                )
            )
        except (
            json.JSONDecodeError,
            FileNotFoundError,
        ):
            return []

        if not isinstance(data, list):
            raise ValueError(
                "El Event Ledger debe ser una lista JSON."
            )

        return data

    def _save(
        self,
        events: list[dict[str, Any]],
    ) -> None:
        temporary = self.store.with_suffix(
            self.store.suffix + ".tmp"
        )

        temporary.write_text(
            json.dumps(
                events,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        temporary.replace(self.store)

    def record(
        self,
        event_type: str,
        source: str,
        subject: str,
        data: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Registra un hecho observado.

        No acepta tipos desconocidos.
        """

        event_type = str(
            event_type
        ).strip().upper()

        if event_type not in self.VALID_TYPES:
            raise ValueError(
                f"Tipo de evento no permitido: {event_type}"
            )

        event = {
            "event_id": (
                f"EVT-{uuid.uuid4().hex[:16].upper()}"
            ),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "type": event_type,
            "source": str(source),
            "subject": str(subject),
            "session_id": (
                str(session_id)
                if session_id
                else None
            ),
            "data": data or {},
        }

        events = self._load()
        events.append(event)
        self._save(events)

        return event

    def all(self) -> list[dict[str, Any]]:
        return self._load()

    def count(self) -> int:
        return len(self._load())

    def session(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        return [
            event
            for event in self._load()
            if event.get("session_id")
            == session_id
        ]

    def source(
        self,
        source: str,
    ) -> list[dict[str, Any]]:
        return [
            event
            for event in self._load()
            if event.get("source")
            == source
        ]

    def type(
        self,
        event_type: str,
    ) -> list[dict[str, Any]]:
        event_type = str(
            event_type
        ).strip().upper()

        return [
            event
            for event in self._load()
            if event.get("type")
            == event_type
        ]

    def latest(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if limit < 1:
            return []

        return self._load()[-limit:]
