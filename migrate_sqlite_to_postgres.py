#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migra los datos locales (SQLite data/vida.db) a la base Postgres remota.

Uso:
    DATABASE_URL="postgres://..." python migrate_sqlite_to_postgres.py

Requisitos:
    - Tener pg8000 instalado (python del sistema lo tiene).
    - La variable DATABASE_URL apunta al Postgres de destino (Neon/Vercel).
    - La base SQLite local debe existir (data/vida.db).

La migración es idempotente: las tablas se actualizan con ON CONFLICT,
nunca se borra información del destino.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import vida_db  # noqa: E402

DB = ROOT / "data" / "vida.db"

TABLES = [
    ("users", [
        "user_id", "kind", "username", "display_name",
        "password_hash", "created_at",
    ]),
    ("video_progress", [
        "user_id", "video_id", "course_id", "position",
        "duration", "completed", "updated_at",
    ]),
    ("item_progress", [
        "user_id", "item_id", "course_id", "completed", "updated_at",
    ]),
    ("study_log", [
        "id", "user_id", "course_id", "kind", "ref_id",
        "minutes", "note", "created_at",
    ]),
]


def conflict_sql(table: str, cols: list[str]) -> str:
    if table == "users":
        keys = ["user_id"]
    elif table == "study_log":
        keys = ["id"]
    else:
        keys = ["user_id", *(c for c in cols if c in ("video_id", "item_id")), "course_id"]

    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in keys)
    conflict = ", ".join(keys)
    return (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({conflict}) DO UPDATE SET {updates}"
    )


def main() -> int:
    if not vida_db.postgres_enabled():
        print("❌ No hay DATABASE_URL/POSTGRES_URL en el entorno.")
        return 1
    if not DB.exists():
        print(f"❌ No existe la base local: {DB}")
        return 1

    import sqlite3

    pg = vida_db.pg_conn()

    local = sqlite3.connect(str(DB))
    local.row_factory = sqlite3.Row

    summary: list[str] = []

    for table, cols in TABLES:
        rows = local.execute(
            f"SELECT {', '.join(cols)} FROM {table}"
        ).fetchall()
        if not rows:
            summary.append(f"{table}: 0 filas")
            continue

        sql = conflict_sql(table, cols)
        for row in rows:
            pg.execute(sql, tuple(row[k] for k in cols))
        pg.commit()

        summary.append(f"{table}: {len(rows)} filas")

    local.close()

    print("✅ Migración completada:")
    for line in summary:
        print(f"   · {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())