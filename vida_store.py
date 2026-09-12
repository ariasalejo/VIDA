"""Persistencia dura de VIDA en Postgres (Vercel/Neon).

Estrategia de escritura dual:
- En local cada petición escribe en SQLite (autoritativo para la petición).
- En producción, además, se escribe una copia en Postgres.
- Al arrancar un cold start, VIDA restaura desde Postgres hacia el SQLite
  temporal para que la app nunca quede vacía.

Cualquier fallo de Postgres se registra y degrada a solo-SQLite sin romper.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

import vida_secret

_LOCK = threading.Lock()
_PG = None


def enabled() -> bool:
    return bool(
        os.environ.get("POSTGRES_URL")
        or os.environ.get("DATABASE_URL")
    )


def _connect():
    global _PG
    with _LOCK:
        if _PG is not None:
            try:
                _PG.execute("SELECT 1")
                return _PG
            except Exception:
                _PG = None
        url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
        if not url:
            return None
        try:
            import psycopg
            from psycopg.rows import dict_row

            _PG = psycopg.connect(url, row_factory=dict_row, connect_timeout=8)
            _PG.execute(
                """
                CREATE TABLE IF NOT EXISTS vida_video_progress (
                    video_id   TEXT NOT NULL,
                    course_id  TEXT NOT NULL,
                    position   DOUBLE PRECISION NOT NULL DEFAULT 0,
                    duration   DOUBLE PRECISION NOT NULL DEFAULT 0,
                    completed  INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT,
                    PRIMARY KEY (video_id, course_id)
                )
                """
            )
            _PG.execute(
                """
                CREATE TABLE IF NOT EXISTS vida_item_progress (
                    item_id    TEXT NOT NULL,
                    course_id  TEXT NOT NULL,
                    completed  INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT,
                    PRIMARY KEY (item_id, course_id)
                )
                """
            )
            _PG.execute(
                """
                CREATE TABLE IF NOT EXISTS vida_study_log (
                    id         BIGINT PRIMARY KEY,
                    course_id  TEXT NOT NULL,
                    kind       TEXT NOT NULL,
                    ref_id     TEXT,
                    minutes    DOUBLE PRECISION NOT NULL DEFAULT 0,
                    note       TEXT,
                    created_at TEXT
                )
                """
            )
            _PG.execute(
                """
                CREATE TABLE IF NOT EXISTS vida_files (
                    activity_id TEXT NOT NULL,
                    filename    TEXT NOT NULL,
                    data        BYTEA NOT NULL,
                    size        BIGINT NOT NULL DEFAULT 0,
                    PRIMARY KEY (activity_id, filename)
                )
                """
            )
            _PG.execute(
                """
                CREATE TABLE IF NOT EXISTS vida_kv (
                    key        TEXT PRIMARY KEY,
                    value      TEXT,
                    updated_at TEXT
                )
                """
            )
            _PG.commit()
            return _PG
        except Exception as exc:
            logging.warning("vida_store: Postgres no disponible (%s)", exc)
            _PG = None
            return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_video(video_id, course_id, position, duration, completed) -> None:
    pg = _connect()
    if not pg:
        return
    try:
        pg.execute(
            """
            INSERT INTO vida_video_progress
                (video_id, course_id, position, duration, completed, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, course_id) DO UPDATE SET
                position = EXCLUDED.position,
                duration = EXCLUDED.duration,
                completed = EXCLUDED.completed,
                updated_at = EXCLUDED.updated_at
            """,
            (video_id, course_id, float(position), float(duration), int(completed), _now()),
        )
        pg.commit()
    except Exception:
        logging.exception("vida_store: upsert_video")


def upsert_item(item_id, course_id, completed) -> None:
    pg = _connect()
    if not pg:
        return
    try:
        pg.execute(
            """
            INSERT INTO vida_item_progress (item_id, course_id, completed, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (item_id, course_id) DO UPDATE SET
                completed = EXCLUDED.completed,
                updated_at = EXCLUDED.updated_at
            """,
            (item_id, course_id, int(completed), _now()),
        )
        pg.commit()
    except Exception:
        logging.exception("vida_store: upsert_item")


def study_stable_id(course_id, kind, ref_id, minutes, note) -> int:
    raw = f"{course_id}|{kind}|{ref_id}|{round(float(minutes), 2)}|{note}"
    return int(hashlib.sha1(raw.encode("utf-8")).hexdigest()[:15], 16)


def add_study(sid: int, course_id, kind, ref_id, minutes, note, created_at) -> None:
    pg = _connect()
    if not pg:
        return
    try:
        pg.execute(
            """
            INSERT INTO vida_study_log
                (id, course_id, kind, ref_id, minutes, note, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET minutes = EXCLUDED.minutes
            """,
            (sid, course_id, kind, ref_id, float(minutes), note, created_at),
        )
        pg.commit()
    except Exception:
        logging.exception("vida_store: add_study")


def put_file(activity_id: str, filename: str, data: bytes) -> None:
    pg = _connect()
    if not pg:
        return
    try:
        stored = vida_secret.encrypt(data)
        if stored is not None:
            data = stored
        pg.execute(
            """
            INSERT INTO vida_files (activity_id, filename, data, size)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (activity_id, filename) DO UPDATE SET
                data = EXCLUDED.data, size = EXCLUDED.size
            """,
            (activity_id, filename, data, len(data)),
        )
        pg.commit()
    except Exception:
        logging.exception("vida_store: put_file")


def put_kv(key: str, value: Any) -> None:
    pg = _connect()
    if not pg:
        return
    try:
        pg.execute(
            """
            INSERT INTO vida_kv (key, value, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            (key, json.dumps(value, ensure_ascii=False), _now()),
        )
        pg.commit()
    except Exception:
        logging.exception("vida_store: put_kv")


def get_kv(key: str) -> Any | None:
    pg = _connect()
    if not pg:
        return None
    try:
        row = pg.execute("SELECT value FROM vida_kv WHERE key = %s", (key,)).fetchone()
        return json.loads(row["value"]) if row else None
    except Exception:
        logging.exception("vida_store: get_kv")
        return None


def restore(sqlite_conn: sqlite3.Connection) -> None:
    """Rehidrata el SQLite temporal desde Postgres (idempotente)."""
    pg = _connect()
    if not pg:
        return
    try:
        with _LOCK:
            for row in pg.execute(
                "SELECT video_id, course_id, position, duration, completed "
                "FROM vida_video_progress"
            ).fetchall():
                sqlite_conn.execute(
                    "INSERT OR REPLACE INTO video_progress "
                    "(video_id, course_id, position, duration, completed) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (row["video_id"], row["course_id"], row["position"],
                     row["duration"], row["completed"]),
                )

            for row in pg.execute(
                "SELECT item_id, course_id, completed FROM vida_item_progress"
            ).fetchall():
                sqlite_conn.execute(
                    "INSERT OR REPLACE INTO item_progress "
                    "(item_id, course_id, completed) VALUES (?, ?, ?)",
                    (row["item_id"], row["course_id"], row["completed"]),
                )

            for row in pg.execute(
                "SELECT id, course_id, kind, ref_id, minutes, note, created_at "
                "FROM vida_study_log"
            ).fetchall():
                sqlite_conn.execute(
                    "INSERT OR IGNORE INTO study_log "
                    "(id, course_id, kind, ref_id, minutes, note, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["id"], row["course_id"], row["kind"], row["ref_id"],
                     row["minutes"], row["note"], row["created_at"]),
                )

            sqlite_conn.commit()

        _restore_files()
        _restore_kv()
    except Exception:
        logging.exception("vida_store: restore")


def _restore_files() -> None:
    pg = _connect()
    if not pg:
        return
    try:
        from vida import evidence_root

        rows = pg.execute(
            "SELECT activity_id, filename, data FROM vida_files"
        ).fetchall()
        for row in rows:
            target_dir = evidence_root() / row["activity_id"]
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                raw = row["data"]
                if isinstance(raw, str):
                    raw = raw.encode("latin-1")
                try:
                    raw = vida_secret.decrypt(raw)
                except ValueError as exc:
                    logging.warning("vida_store: %s → %s", row["filename"], exc)
                    continue
                (target_dir / row["filename"]).write_bytes(raw)
            except OSError:
                continue
    except Exception:
        logging.exception("vida_store: _restore_files")


def _restore_kv() -> None:
    pg = _connect()
    if not pg:
        return
    try:
        from vida import certificates_root

        value = get_kv("evidence.json")
        if isinstance(value, list):
            evidence_dir = __import__("vida", fromlist=["evidence_root"]).evidence_root()
            try:
                evidence_dir.mkdir(parents=True, exist_ok=True)
                (evidence_dir / "evidence.json").write_text(
                    json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError:
                pass

        for row in pg.execute(
            "SELECT key, value FROM vida_kv WHERE key LIKE 'cert:%'"
        ).fetchall():
            course_id = row["key"][len("cert:"):]
            try:
                safe = "".join(
                    ch for ch in course_id if ch.isalnum() or ch in "-_ ."
                ).strip().replace(" ", "_") or "course"
                record_path = certificates_root() / f"{safe}.issued.json"
                record_path.write_text(row["value"], encoding="utf-8")
            except OSError:
                continue
    except Exception:
        logging.exception("vida_store: _restore_kv")