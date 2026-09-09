# -*- coding: utf-8 -*-
"""Capa de base de datos de VIDA.

En desarrollo local se usa SQLite (data/vida.db), igual que siempre.
En Vercel/serverless el filesystem es efímero, por lo que la base de
datos debe vivir en un servicio externo persistente (Neon/Postgres).

Este módulo expone una conexión compatible con la API de sqlite3 que
usa la aplicación (execute/fetchone/fetchall, commit, rollback, close
y executescript), reescrita automáticamente al dialecto de Postgres.

Detecta automáticamente el modo:
- Postgres activo si existen DATABASE_URL o POSTGRES_URL
  (las variables que inyecta Neon / Vercel Postgres).
- Si no, todo sigue funcionando con SQLite local.
"""

from __future__ import annotations

import os
import re
import ssl
import threading
from urllib.parse import urlparse, unquote

try:
    import pg8000.dbapi as _pg8000
    _PGBACKEND = True
except Exception:  # pragma: no cover - fallback sin pg8000
    _pg8000 = None
    _PGBACKEND = False


# ---------------------------------------------------------------------------
# Errores compatibles con la excepción sqlite3.IntegrityError usada en vida.py
# ---------------------------------------------------------------------------
class DatabaseError(Exception):
    pass


class IntegrityError(DatabaseError):
    pass


# ---------------------------------------------------------------------------
# Fila tipo diccionario compatible con sqlite3.Row
#    row["col"], dict(row), row[0]
# ---------------------------------------------------------------------------
class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            if key < 0 or key >= len(self):
                raise IndexError(key)
            return list(self.values())[key]
        return dict.__getitem__(self, key)


def _translate(sql: str) -> str:
    """Reescribe el dialecto SQLite usado por la app al de Postgres."""
    sql = sql.strip()

    # INSERT OR IGNORE -> INSERT ... ON CONFLICT DO NOTHING
    m = re.match(r"(?is)^INSERT\s+OR\s+IGNORE\s+INTO\s+(.*)$", sql)
    if m:
        sql = (
            "INSERT INTO " + m.group(1).strip()
            + " ON CONFLICT DO NOTHING"
        )

    # Placeholders '?' -> '%s' (fuera de cadenas)
    sql = _replace_placeholders(sql)

    return sql


def _replace_placeholders(sql: str) -> str:
    out: list[str] = []
    in_single = False
    in_double = False
    in_comment = False
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if in_comment:
            out.append(ch)
            if ch == "\n":
                in_comment = False
            i += 1
            continue

        if in_single:
            out.append(ch)
            if ch == "\\":
                if i + 1 < n:
                    out.append(sql[i + 1])
                    i += 1
            elif ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            out.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if ch == "-" and nxt == "-":
            out.append(ch)
            in_comment = True
            i += 1
            continue

        if ch == "'":
            in_single = True
            out.append(ch)
            i += 1
            continue

        if ch == '"':
            in_double = True
            out.append(ch)
            i += 1
            continue

        if ch == "?":
            out.append("%s")
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


class _Result:
    """Resultado de execute(): imita el cursor de sqlite."""

    __slots__ = ("_rows", "_index")

    def __init__(self, rows):
        self._rows = rows
        self._index = 0

    def fetchone(self):
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self):
        rows = self._rows[self._index:]
        self._index = len(self._rows)
        return rows

    def fetchmany(self, size=None):
        size = size or 1
        rows = self._rows[self._index:self._index + size]
        self._index += len(rows)
        return rows


REMOTE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL DEFAULT 'user',
    username TEXT UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT,
    full_name TEXT,
    cedula TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS cedula TEXT;

CREATE TABLE IF NOT EXISTS video_progress (
    user_id TEXT NOT NULL DEFAULT 'local-owner',
    video_id TEXT NOT NULL,
    course_id TEXT NOT NULL DEFAULT 'sena_ciberseguridad',
    position DOUBLE PRECISION NOT NULL DEFAULT 0,
    duration DOUBLE PRECISION NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, video_id, course_id)
);

CREATE TABLE IF NOT EXISTS item_progress (
    user_id TEXT NOT NULL DEFAULT 'local-owner',
    item_id TEXT NOT NULL,
    course_id TEXT NOT NULL DEFAULT 'sena_ciberseguridad',
    completed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, item_id, course_id)
);

CREATE TABLE IF NOT EXISTS study_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'local-owner',
    course_id TEXT NOT NULL DEFAULT 'sena_ciberseguridad',
    kind TEXT NOT NULL,
    ref_id TEXT,
    minutes DOUBLE PRECISION NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def postgres_enabled() -> bool:
    """True cuando hay credenciales de Neon/Postgres y pg8000 disponible."""
    if not _PGBACKEND:
        return False
    return bool(
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("POSTGRES_URL_NON_POOLING")
    )


def _database_url() -> str:
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("POSTGRES_URL_NON_POOLING")
        or ""
    )


def _connect() -> "PGConnection":
    url = _database_url()
    part = urlparse(url)

    if not part.hostname:
        raise DatabaseError(
            "No se pudo interpretar DATABASE_URL/POSTGRES_URL."
        )

    password = unquote(part.password or "")
    ssl_context = ssl.create_default_context()

    raw = _pg8000.connect(
        host=part.hostname,
        port=part.port or 5432,
        database=(part.path or "/").lstrip("/") or "postgres",
        user=unquote(part.username or ""),
        password=password,
        ssl_context=ssl_context,
    )

    return PGConnection(raw)


_pg_local = threading.local()


def pg_conn() -> "PGConnection":
    """Conexión Postgres aislada por hilo para evitar compartir sockets."""
    connection = getattr(_pg_local, "connection", None)

    if connection is None:
        connection = _connect()
        connection.executescript(REMOTE_SCHEMA)
        connection.commit()
        _pg_local.connection = connection

    return connection


class PGConnection:
    """Adaptador que imita sqlite3.Connection sobre Postgres (pg8000)."""

    def __init__(self, raw):
        self._raw = raw
        # El código de la app inicia transacciones con "BEGIN".
        self._tx = False

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------
    def _reconnect(self) -> None:
        fresh = _connect()
        fresh.executescript(REMOTE_SCHEMA)
        fresh.commit()
        self._raw = fresh._raw
        self._tx = False
        _pg_local.connection = self

    def _run(self, sql: str, params: tuple | list | None):
        pg = _pg8000

        cur = self._raw.cursor()
        if params:
            cur.execute(sql, tuple(params))
        else:
            cur.execute(sql)

        if cur.description is None:
            return _Result([])

        cols = []
        for d in cur.description:
            if isinstance(d, (tuple, list)):
                cols.append(d[0])
            else:
                cols.append(getattr(d, "name", d[0]))
        rows = cur.fetchall() or []
        return _Result(
            [Row(dict(zip(cols, r))) for r in rows]
        )

    # ------------------------------------------------------------------
    # API pública (compatible con la que usa vida.py)
    # ------------------------------------------------------------------
    def execute(self, sql: str, params=()):
        sql = str(sql).strip()

        upper = sql.upper()
        if upper in ("BEGIN", "BEGIN TRANSACTION"):
            self._tx = True
            return _Result([])
        if upper in ("COMMIT", "COMMIT TRANSACTION"):
            self.commit()
            self._tx = False
            return _Result([])
        if upper in ("ROLLBACK", "ROLLBACK TRANSACTION"):
            self.rollback()
            return _Result([])

        translated = _translate(sql)

        try:
            return self._run(translated, params)
        except (pg_errors("OperationalError"), pg_errors("InterfaceError")):
            # La conexión ociosa del Lambda pudo morir: reconectar y reintentar.
            self.close()
            self._reconnect()
            return self._run(translated, params)
        except pg_errors("IntegrityError") as exc:
            raise IntegrityError(str(exc)) from exc
        except Exception as exc:
            raise DatabaseError(str(exc)) from exc

    def executescript(self, script: str) -> None:
        for statement in re.split(r";\s*(?:\n|$)", script):
            statement = statement.strip()
            if not statement:
                continue
            self._run(_translate(statement), ())

    def commit(self) -> None:
        try:
            self._raw.commit()
        except Exception:
            raise

    def rollback(self) -> None:
        try:
            self._raw.rollback()
        except Exception:
            pass

    def close(self) -> None:
        # La conexión remota se reutiliza entre peticiones del mismo Lambda.
        pass


def pg_errors(name: str):
    """Devuelve la clase de error pg8000 por nombre de forma segura."""
    if _pg8000 is None:
        return DatabaseError
    return getattr(_pg8000, name, DatabaseError)