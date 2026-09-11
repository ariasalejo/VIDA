"""Cuentas de VIDA: almacenamiento de usuarios y contraseñas.

En producción (Vercel) los usuarios persisten en Vercel Postgres/Neon
(variable POSTGRES_URL o DATABASE_URL). Localmente se usa SQLite en
data/users.db, que se ignora en git. Ningún secreto se publica en código:
solo se guarda el hash PBKDF2 de la contraseña con salt aleatorio.
"""
from __future__ import annotations

import os
import re
import secrets
import sqlite3
import tempfile
import unicodedata
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac
from pathlib import Path
from secrets import compare_digest

_PBKDF2_ITERATIONS = 600_000


class AccountError(Exception):
    pass


class AccountExists(AccountError):
    pass


class AccountNotFound(AccountError):
    pass


class InvalidCredentials(AccountError):
    pass


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _writable(path: Path) -> bool:
    try:
        probe = path / ".vida_w"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def backend() -> str:
    if os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL"):
        return "postgres"
    return "sqlite"


def _sqlite_path() -> Path:
    data = _root() / "data"
    if data.exists() and _writable(data):
        return data / "users.db"
    alt = Path(tempfile.gettempdir()) / "vida_runtime"
    alt.mkdir(parents=True, exist_ok=True)
    return alt / "users.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS vida_users (
    id           TEXT PRIMARY KEY,
    email        TEXT NOT NULL UNIQUE,
    passhash     TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'aprendiz',
    created_at   TEXT NOT NULL
);
"""


def _pg_connect():
    import psycopg
    import psycopg.rows

    url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
    return psycopg.connect(
        url, connect_timeout=10, row_factory=psycopg.rows.dict_row
    )


def _ensure_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_sqlite_path()))
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def _ensure_postgres() -> None:
    with _pg_connect() as conn:
        conn.execute(_SCHEMA)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt),
        _PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = str(stored).split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        candidate = pbkdf2_hmac(
            "sha256", password.encode("utf-8"),
            bytes.fromhex(salt), int(iterations),
        )
        return compare_digest(candidate.hex(), digest)
    except (ValueError, TypeError):
        return False


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "aprendiz"


def _public_user(row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def create_user(email: str, display_name: str, password: str) -> dict:
    email = _normalize_email(email)
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise AccountError("Correo inválido.")
    display_name = str(display_name or "").strip()
    if not display_name:
        display_name = email.split("@")[0]
    if not password or len(password) < 6:
        raise AccountError("La contraseña debe tener al menos 6 caracteres.")

    uid = "u_" + secrets.token_urlsafe(12)
    passhash = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    if backend() == "postgres":
        _ensure_postgres()
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM vida_users")
                first = cur.fetchone()["n"] == 0
                role = "admin" if first else "aprendiz"
                try:
                    cur.execute(
                        "INSERT INTO vida_users "
                        "(id, email, passhash, display_name, role, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (uid, email, passhash, display_name, role, now),
                    )
                except Exception:
                    raise AccountExists("Ya existe una cuenta con ese correo.")
    else:
        conn = _ensure_sqlite()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM vida_users"
            ).fetchone()
            role = "admin" if row["n"] == 0 else "aprendiz"
            try:
                conn.execute(
                    "INSERT INTO vida_users "
                    "(id, email, passhash, display_name, role, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (uid, email, passhash, display_name, role, now),
                )
            except sqlite3.IntegrityError:
                raise AccountExists("Ya existe una cuenta con ese correo.")
            conn.commit()
        finally:
            conn.close()

    return {
        "id": uid,
        "email": email,
        "display_name": display_name,
        "role": role,
    }


def get_user(email: str) -> dict | None:
    email = _normalize_email(email)
    if backend() == "postgres":
        _ensure_postgres()
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM vida_users WHERE email = %s", (email,))
                row = cur.fetchone()
        if row is None:
            return None
        return _public_user(row)
    conn = _ensure_sqlite()
    try:
        row = conn.execute(
            "SELECT * FROM vida_users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()
    return _public_user(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    if backend() == "postgres":
        _ensure_postgres()
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM vida_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return _public_user(row)
    conn = _ensure_sqlite()
    try:
        row = conn.execute(
            "SELECT * FROM vida_users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    return _public_user(row) if row else None


def login(email: str, password: str) -> dict:
    user = get_user(email)
    if user is None:
        raise InvalidCredentials("Credenciales incorrectas.")
    if backend() == "postgres":
        _ensure_postgres()
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT passhash FROM vida_users WHERE id = %s", (user["id"],)
                )
                row = cur.fetchone()
        stored = row["passhash"] if row else ""
    else:
        conn = _ensure_sqlite()
        try:
            row = conn.execute(
                "SELECT passhash FROM vida_users WHERE id = ?", (user["id"],)
            ).fetchone()
        finally:
            conn.close()
        stored = row["passhash"] if row else ""
    if not verify_password(password, stored):
        raise InvalidCredentials("Credenciales incorrectas.")
    return user


def change_password(user_id: str, new_password: str) -> None:
    if not new_password or len(new_password) < 6:
        raise AccountError("La contraseña debe tener al menos 6 caracteres.")
    passhash = hash_password(new_password)
    if backend() == "postgres":
        _ensure_postgres()
        with _pg_connect() as conn:
            conn.execute(
                "UPDATE vida_users SET passhash = %s WHERE id = %s",
                (passhash, user_id),
            )
    else:
        conn = _ensure_sqlite()
        try:
            conn.execute(
                "UPDATE vida_users SET passhash = ? WHERE id = ?",
                (passhash, user_id),
            )
            conn.commit()
        finally:
            conn.close()