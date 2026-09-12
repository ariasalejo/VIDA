"""Cifrado simétrico (Fernet) para los datos de VIDA en reposo.

Política de privacidad del proyecto: las evidencias subidas por el aprendiz se
guardan cifradas en reposo (Postgres/Neon y copias locales). La clave maestra
llega por la variable de entorno VIDA_DATA_KEY (deploy) o por el archivo
data/.data_key (local, chmod 600 y gitignored).

El cifrado solo se activa cuando existe una clave persistente; si no la hay
en un despliegue de solo lectura, se degrada sin cifrar y se registra un aviso
para no romper el cold start.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

_LOG = logging.getLogger("vida_secret")

# Marca para distinguir payloads cifrados de filas plane-texto (legacy).
MAGIC = b"VIDAENC1:"

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _local_key_path() -> Path:
    return _DATA_DIR / ".data_key"


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def data_key() -> bytes | None:
    """Devuelve la clave Fernet derivada o None si no existe una persistente."""
    env_key = os.environ.get("VIDA_DATA_KEY", "").strip()
    if env_key:
        return _derive_key(env_key)

    key_file = _local_key_path()
    if key_file.exists():
        try:
            secret = key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return _derive_key(secret) if secret else None

    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_urlsafe(32)
        key_file.write_text(secret, encoding="utf-8")
        key_file.chmod(0o600)
        return _derive_key(secret)
    except OSError as exc:
        _LOG.warning("vida_secret: sin clave persistente, cifrado desactivado (%s)", exc)
        return None


def enabled() -> bool:
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return False
    return bool(data_key())


def encrypt(payload: bytes) -> bytes | None:
    """Cifra bytes; devuelve None si el cifrado está deshabilitado."""
    if not enabled():
        return None
    key = data_key()
    from cryptography.fernet import Fernet

    token = Fernet(key).encrypt(payload)
    return MAGIC + token


def decrypt(payload: bytes) -> bytes:
    """Descifra un payload; si no lleva la marca, lo devuelve como estaba."""
    if not payload.startswith(MAGIC):
        return payload
    if not enabled():
        raise ValueError("No hay clave de cifrado disponible para descifrar.")
    from cryptography.fernet import Fernet, InvalidToken

    token = payload[len(MAGIC):]
    try:
        return Fernet(data_key()).decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Evidencia cifrada ilegible (clave distinta).") from exc