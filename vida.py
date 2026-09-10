#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import tempfile
import subprocess
import sys
import threading

try:
    from piper import PiperVoice
except ImportError:
    PiperVoice = None
    print("⚠️ Piper TTS no disponible (pip install piper-tts)")
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from secrets import compare_digest

from flask import Flask, jsonify, render_template, request, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vida_engines import (
    CourseEngine,
    ProgressEngine,
    IntelligenceEngine,
    ProfileEngine,
    CertificateEngine,
    CertificateNotEligible,
    CertificateAlreadyIssued,
)

import vida_db

ROOT = Path(__file__).resolve().parent

# VIDA Local · Piper persistente en memoria
_piper_voice = None
_piper_lock = threading.Lock()

DATA = ROOT / "data"
MEDIA = ROOT / "media"
DB = DATA / "vida.db"
COURSE = DATA / "course.json"
PROFILE = DATA / "profiles" / "sena_ciberseguridad.json"
CERT_DIR = ROOT / "certificates"
CERT_HTML = ROOT / "certificate.html"

DEFAULT_COURSE_ID = "sena_ciberseguridad"
REGISTRY = DATA / "registry.json"
COURSES_DIR = DATA / "courses"
PROFILES_DIR = DATA / "profiles"

# ---------------------------------------------------------------------------
# Protección del perfil: nombre y cédula se cifran (Fernet) en reposo.
# La llave NO vive en el código: viene de la variable VIDA_DATA_KEY.
# La API NUNCA devuelve estos valores en claro; solo expone estado y máscara.
# ---------------------------------------------------------------------------
DATA_KEY_ENV = "VIDA_DATA_KEY"


def _profile_key() -> bytes:
    secret = os.environ.get(DATA_KEY_ENV, "").strip()
    if not secret:
        raise RuntimeError(
            "Falta la variable de entorno "
            f"{DATA_KEY_ENV} para proteger el perfil."
        )
    return base64.urlsafe_b64encode(
        hashlib.sha256(secret.encode("utf-8")).digest()
    )


def _profile_cipher():
    from cryptography.fernet import Fernet

    return Fernet(_profile_key())


def encrypt_profile_value(value: str) -> str:
    if not value:
        return ""
    return _profile_cipher().encrypt(
        str(value).encode("utf-8")
    ).decode("ascii")


def decrypt_profile_value(value: str) -> str:
    if not value:
        return ""
    try:
        return _profile_cipher().decrypt(
            value.encode("ascii")
        ).decode("utf-8")
    except Exception:
        return value


def _masked_cedula(value: str) -> str:
    digits = re.sub(r"\D", "", decrypt_profile_value(value) or "")
    if len(digits) >= 4:
        return "••••••" + digits[-4:]
    return "••••"


def profile_payload(row) -> dict:
    if row is not None and isinstance(row, sqlite3.Row):
        row = dict(row)
    """Estado del perfil SIN exponer el contenido real.

    Devuelve únicamente si está completo, qué campos hay y una máscara
    de la cédula (últimos 4 dígitos) para confirmación visual segura.
    """
    full_name = str(row.get("full_name", "") or "").strip() if row else ""
    cedula = str(row.get("cedula", "") or "").strip() if row else ""
    has_full = bool(full_name)
    has_ced = bool(cedula)
    return {
        "complete": has_full and has_ced,
        "has_full_name": has_full,
        "has_cedula": has_ced,
        "masked_cedula": _masked_cedula(cedula) if has_ced else "",
    }

console = Console()

DEFAULT_COURSE = {
    "title": "Apropiación de los Conceptos en Ciberseguridad",
    "provider": "SENA",
    "hours": 48,
    "platform": "Zajuna",
    "source": "https://zajuna.sena.edu.co/",
    "learner": "Eduar Alejandro Arias Londoño",
    "tutor": "Libardo Antonio Contreras",
    "dedication": "A Libardo Antonio Contreras, mi instructor y guía, por acompañarme en este primer logro educativo de muchos que vienen.",
    "items": [
        {
            "id": "aa1",
            "kind": "activity",
            "title": "AA1 · Informe análisis y valoración de activos",
            "due": "2026-08-13",
        },
        {
            "id": "aa2",
            "kind": "activity",
            "title": "AA2 · Infografía",
            "due": "2026-08-21",
        },
        {
            "id": "aa3",
            "kind": "activity",
            "title": "AA3 · Matriz de riesgo",
            "due": "2026-08-28",
        },
        {
            "id": "aa4",
            "kind": "activity",
            "title": "AA4 · Mapa mental",
            "due": "2026-09-06",
        },
    ],
    "concepts": [
        {
            "id": "concepto_activo",
            "title": "Activo de información",
            "definition": (
                "Recurso que tiene valor para una organización y, "
                "por ello, requiere protección."
            ),
        },
        {
            "id": "concepto_confidencialidad",
            "title": "Confidencialidad",
            "definition": (
                "La información solo debe estar disponible "
                "para quienes están autorizados."
            ),
        },
        {
            "id": "concepto_integridad",
            "title": "Integridad",
            "definition": (
                "La información debe conservar su exactitud "
                "y completitud."
            ),
        },
        {
            "id": "concepto_disponibilidad",
            "title": "Disponibilidad",
            "definition": (
                "La información y los servicios deben estar "
                "disponibles cuando se necesitan."
            ),
        },
        {
            "id": "concepto_riesgo",
            "title": "Riesgo",
            "definition": (
                "Posibilidad de que una amenaza aproveche una "
                "vulnerabilidad y produzca un impacto."
            ),
        },
    ],
    "videos": [],
}


def ensure_dirs() -> None:
    root = runtime_root()
    for directory in (
        root,
        root / "courses",
        root / "profiles",
        MEDIA / "videos",
        MEDIA / "materials",
    ):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue

    if not COURSE.exists() and _writable(DATA):
        try:
            COURSE.write_text(
                json.dumps(DEFAULT_COURSE, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass


def _writable(path: Path) -> bool:
    """True si el filesystem permite crear archivos (local) o es de solo lectura (Vercel)."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".vida_w"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def runtime_root() -> Path:
    """Raíz escribible: data/ en local, carpeta efímera en despliegues de solo lectura."""
    if DATA.exists() and _writable(DATA):
        return DATA
    alt = Path(tempfile.gettempdir()) / "vida_runtime"
    try:
        alt.mkdir(parents=True, exist_ok=True)
    except OSError:
        alt = DATA
    return alt


def evidence_root() -> Path:
    """Carpeta de evidencias: data/evidence en local, efímera y escribible en el deploy."""
    return runtime_root() / "evidence"


def certificates_root() -> Path:
    """Carpeta de certificados emitidos: certificates/ en local, efímera en el deploy."""
    if runtime_root() is DATA:
        return CERT_DIR
    alt = runtime_root() / "certificates"
    try:
        alt.mkdir(parents=True, exist_ok=True)
    except OSError:
        alt = CERT_DIR
    return alt


def _load_registry() -> dict:
    _ensure_courses_dir()
    if not REGISTRY.exists():
        return {"active": DEFAULT_COURSE_ID, "courses": []}
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    data.setdefault("active", DEFAULT_COURSE_ID)
    data.setdefault("courses", [])
    return data


def _save_registry(data: dict) -> None:
    try:
        REGISTRY.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _ensure_courses_dir() -> None:
    try:
        (DATA / "courses").mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _discover_course_ids() -> list[str]:
    _ensure_courses_dir()
    ids: list[str] = []
    for path in sorted((DATA / "courses").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cid = str(data.get("id") or path.stem)
        if cid not in ids:
            ids.append(cid)
    return ids


def migrate_registry() -> None:
    _ensure_courses_dir()
    known = _discover_course_ids()

    if COURSE.exists() and DEFAULT_COURSE_ID not in known:
        try:
            legacy = json.loads(COURSE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            legacy = DEFAULT_COURSE
        legacy = dict(legacy)
        legacy.setdefault("id", DEFAULT_COURSE_ID)
        try:
            (DATA / "courses").mkdir(parents=True, exist_ok=True)
            (DATA / "courses" / f"{DEFAULT_COURSE_ID}.json").write_text(
                json.dumps(legacy, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        known = _discover_course_ids()

    registry = _load_registry()
    changed = False
    for cid in known:
        if cid not in registry["courses"]:
            registry["courses"].append(cid)
            changed = True
    if registry["active"] not in registry["courses"]:
        registry["active"] = (
            registry["courses"][0] if registry["courses"] else DEFAULT_COURSE_ID
        )
        changed = True
    if changed:
        _save_registry(registry)


def active_course_id() -> str:
    migrate_registry()
    registry = _load_registry()
    if registry["active"] in _discover_course_ids():
        return registry["active"]
    return DEFAULT_COURSE_ID


def set_active_course_id(course_id: str) -> bool:
    course_id = str(course_id)
    if course_id not in _discover_course_ids():
        return False
    registry = _load_registry()
    registry["active"] = course_id
    if course_id not in registry["courses"]:
        registry["courses"].append(course_id)
    _save_registry(registry)
    return True


def course(course_id: str | None = None) -> dict:
    _ensure_courses_dir()
    cid = course_id or active_course_id()
    manifest = DATA / "courses" / f"{cid}.json"
    if not manifest.exists():
        if course_id is None and COURSE.exists():
            return json.loads(COURSE.read_text(encoding="utf-8"))
        if cid == DEFAULT_COURSE_ID:
            return dict(DEFAULT_COURSE)
        return dict(DEFAULT_COURSE)
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = dict(DEFAULT_COURSE)
    data.setdefault("id", cid)
    data.setdefault("videos", [])
    return data


def _profile_template(course_id: str, course_title: str) -> dict:
    return {
        "course_id": course_id,
        "name": str(course_title or course_id).title(),
        "version": "1.0",
        "components": {
            "video": {"enabled": True},
            "activity": {"enabled": True},
            "mastery": {"enabled": True},
            "evidence": {"enabled": True},
        },
        "weights": {
            "video": 0.20,
            "activity": 0.40,
            "mastery": 0.25,
            "evidence": 0.15,
        },
        "metadata": {
            "description": (
                f"Perfil base de {course_id}. Se puede ajustar "
                "en data/profiles/ sin tocar el código."
            ),
        },
    }


def profile_path(course_id: str | None = None) -> Path:
    cid = course_id or active_course_id()
    path = PROFILES_DIR / f"{cid}.json"
    if not path.exists():
        course_data = course(cid)
        template = _profile_template(cid, str(course_data.get("title", cid)))
        try:
            path.write_text(
                json.dumps(template, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
    return path


def register_course(manifest: dict, activate: bool = True) -> str:
    (DATA / "courses").mkdir(parents=True, exist_ok=True)
    manifest = dict(manifest)
    cid = str(manifest.get("id") or "").strip()
    if not cid:
        raise ValueError("El curso debe tener un campo 'id'.")
    (DATA / "courses").mkdir(parents=True, exist_ok=True)
    (DATA / "courses" / f"{cid}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    profile_path(cid)
    migrate_registry()
    if activate:
        set_active_course_id(cid)
    return cid




# ---------------------------------------------------------------------------
# KNOWLEDGE VERIFICATION V2
# ---------------------------------------------------------------------------
# Las respuestas correctas viven exclusivamente en backend.
# Nunca se envían al navegador mediante GET.
KNOWLEDGE_CHECKS = {
    "concepto_ciberseguridad": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "cib-q1",
                "question": "¿Qué conjunto de elementos protege principalmente la ciberseguridad?",
                "options": [
                    "Sistemas, redes, aplicaciones, dispositivos y datos frente a amenazas.",
                    "Únicamente las contraseñas de los usuarios.",
                    "Solo el hardware físico de la organización.",
                    "Exclusivamente los archivos impresos."
                ],
                "correct": 0,
            },
            {
                "id": "cib-q2",
                "question": "¿Qué dimensiones incluye la ciberseguridad según el concepto?",
                "options": [
                    "Personas, procesos y tecnología.",
                    "Ventas, marketing y publicidad.",
                    "Contratos, facturas y nómina.",
                    "Presupuesto, gastos e ingresos."
                ],
                "correct": 0,
            },
            {
                "id": "cib-q3",
                "question": "¿Cuál es un ejemplo de práctica de ciberseguridad?",
                "options": [
                    "Actualización y parcheo de software.",
                    "Eliminar los respaldos de información.",
                    "Compartir credenciales de acceso.",
                    "Deshabilitar los controles de acceso."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_activo": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "act-q1",
                "question": "¿Qué es un activo de información?",
                "options": [
                    "Un recurso que posee valor para la organización y debe ser protegido.",
                    "Una amenaza que ataca los sistemas.",
                    "Una debilidad presente en el software.",
                    "El impacto económico de un incidente."
                ],
                "correct": 0,
            },
            {
                "id": "act-q2",
                "question": "¿Cuál de los siguientes es un ejemplo de activo de información?",
                "options": [
                    "Base de datos de clientes.",
                    "Una amenaza de phishing.",
                    "Una vulnerabilidad del navegador.",
                    "El impacto reputacional."
                ],
                "correct": 0,
            },
            {
                "id": "act-q3",
                "question": "¿Para qué sirve identificar y valorar los activos?",
                "options": [
                    "Para determinar qué debe protegerse primero.",
                    "Para eliminar todos los controles de seguridad.",
                    "Para aumentar la cantidad de vulnerabilidades.",
                    "Para evitar el uso de respaldos."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_confidencialidad": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "conf-q1",
                "question": "¿Qué garantiza la confidencialidad?",
                "options": [
                    "Que la información solo sea accesible para personas, procesos o sistemas autorizados.",
                    "Que la información nunca pueda ser modificada.",
                    "Que los servicios estén siempre disponibles.",
                    "Que el riesgo siempre sea eliminado por completo."
                ],
                "correct": 0,
            },
            {
                "id": "conf-q2",
                "question": "¿Cuál es un ejemplo de pérdida de confidencialidad?",
                "options": [
                    "Filtración de información.",
                    "Caída de un servidor.",
                    "Alteración de una base de datos.",
                    "Pérdida económica por un ciberataque."
                ],
                "correct": 0,
            },
            {
                "id": "conf-q3",
                "question": "¿Qué control protege la confidencialidad?",
                "options": [
                    "Cifrado.",
                    "Cortes eléctricos.",
                    "Desastres naturales.",
                    "Redundancia de almacenamiento."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_integridad": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "int-q1",
                "question": "¿Qué garantiza la integridad de la información?",
                "options": [
                    "Que mantenga su exactitud, completitud y consistencia y no sea modificada sin autorización.",
                    "Que sea accesible solo para los autorizados.",
                    "Que los servicios estén disponibles todo el tiempo.",
                    "Que las amenazas desaparezcan."
                ],
                "correct": 0,
            },
            {
                "id": "int-q2",
                "question": "¿Cuál es un ejemplo de afectación a la integridad?",
                "options": [
                    "Manipulación de registros.",
                    "Robo de contraseñas.",
                    "Interrupción del servicio.",
                    "Daño reputacional."
                ],
                "correct": 0,
            },
            {
                "id": "int-q3",
                "question": "¿Qué control ayuda a verificar la integridad?",
                "options": [
                    "Hashes.",
                    "Redundancia.",
                    "Planes de continuidad.",
                    "Alta disponibilidad."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_disponibilidad": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "disp-q1",
                "question": "¿Qué garantiza la disponibilidad?",
                "options": [
                    "Que la información y los servicios estén disponibles y utilizables cuando sean necesarios.",
                    "Que la información solo la vean los autorizados.",
                    "Que los datos no puedan modificarse.",
                    "Que no existan amenazas."
                ],
                "correct": 0,
            },
            {
                "id": "disp-q2",
                "question": "¿Qué puede afectar la disponibilidad?",
                "options": [
                    "Ataque de denegación de servicio.",
                    "Cifrado de información.",
                    "Firmas digitales.",
                    "Control de acceso."
                ],
                "correct": 0,
            },
            {
                "id": "disp-q3",
                "question": "¿Qué control favorece la disponibilidad?",
                "options": [
                    "Redundancia.",
                    "Hashes.",
                    "Gestión de privilegios.",
                    "Permisos de escritura."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_amenaza": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "ame-q1",
                "question": "¿Qué es una amenaza?",
                "options": [
                    "Una circunstancia, evento, actor o acción con capacidad potencial de causar daño a un activo.",
                    "Un recurso que debe ser protegido.",
                    "Un control que previene incidentes.",
                    "El efecto de un riesgo materializado."
                ],
                "correct": 0,
            },
            {
                "id": "ame-q2",
                "question": "¿Cuál es un ejemplo de amenaza?",
                "options": [
                    "Ransomware.",
                    "Backup de información.",
                    "Cifrado de datos.",
                    "Firewall."
                ],
                "correct": 0,
            },
            {
                "id": "ame-q3",
                "question": "¿Qué se requiere normalmente para que una amenaza produzca un incidente?",
                "options": [
                    "Que exista una condición que permita que la amenaza afecte un activo.",
                    "Que la organización no tenga activos.",
                    "Que el riesgo sea aceptado por la dirección.",
                    "Que no existan controles de seguridad documentados."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_vulnerabilidad": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "vul-q1",
                "question": "¿Qué es una vulnerabilidad?",
                "options": [
                    "Una debilidad o condición que puede ser aprovechada por una amenaza.",
                    "Un atacante que busca dañar un activo.",
                    "Una medida para reducir el riesgo.",
                    "El valor de un activo para la organización."
                ],
                "correct": 0,
            },
            {
                "id": "vul-q2",
                "question": "¿Cuál es un ejemplo de vulnerabilidad?",
                "options": [
                    "Contraseña débil.",
                    "Ransomware.",
                    "Phishing.",
                    "Robo de credenciales."
                ],
                "correct": 0,
            },
            {
                "id": "vul-q3",
                "question": "¿Dónde pueden encontrarse las vulnerabilidades?",
                "options": [
                    "En software, hardware, configuraciones, procesos o personas.",
                    "Únicamente en los servidores de almacenamiento.",
                    "Solo en los dispositivos móviles.",
                    "Exclusivamente en los atacantes externos."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_riesgo": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "riesgo-q1",
                "question": "¿Qué describe mejor el concepto de riesgo?",
                "options": [
                    "La posibilidad de que una amenaza aproveche una vulnerabilidad y produzca consecuencias sobre un activo.",
                    "La existencia de cualquier activo dentro de una organización.",
                    "Una medida utilizada únicamente para eliminar vulnerabilidades.",
                    "Un inventario de controles de seguridad."
                ],
                "correct": 0,
            },
            {
                "id": "riesgo-q2",
                "question": "¿Cuál es una relación correcta dentro de la cadena conceptual del riesgo?",
                "options": [
                    "Activo → Amenaza → Vulnerabilidad → Probabilidad → Impacto → Riesgo",
                    "Riesgo → Activo → Control → Amenaza",
                    "Impacto → Activo → Riesgo → Vulnerabilidad",
                    "Control → Riesgo → Activo → Amenaza"
                ],
                "correct": 0,
            },
            {
                "id": "riesgo-q3",
                "question": "¿Qué factores se relacionan directamente en la estimación básica del riesgo?",
                "options": [
                    "Probabilidad e impacto.",
                    "Usuario y contraseña.",
                    "Hardware y software.",
                    "Disponibilidad y ancho de banda."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_impacto": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "imp-q1",
                "question": "¿Qué es el impacto?",
                "options": [
                    "La consecuencia o efecto producido cuando un riesgo se materializa.",
                    "La posibilidad de que surja una amenaza.",
                    "Una debilidad aprovechable por un atacante.",
                    "Un control que corrige los efectos del riesgo."
                ],
                "correct": 0,
            },
            {
                "id": "imp-q2",
                "question": "¿Cuál es un ejemplo de impacto?",
                "options": [
                    "Pérdida económica.",
                    "Firewall activo.",
                    "Contraseña cifrada.",
                    "Copia de seguridad."
                ],
                "correct": 0,
            },
            {
                "id": "imp-q3",
                "question": "¿Sobre qué aspectos puede afectar el impacto?",
                "options": [
                    "Operaciones, finanzas, reputación, cumplimiento legal o confianza de los usuarios.",
                    "Únicamente el rendimiento de los equipos.",
                    "Solo el inventario de activos.",
                    "Exclusivamente los permisos de escritura."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_control": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "ctl-q1",
                "question": "¿Qué es un control de seguridad?",
                "options": [
                    "Una medida utilizada para prevenir, detectar, corregir o reducir los efectos de un riesgo.",
                    "Un evento con capacidad de causar daño.",
                    "El valor de un activo para la organización.",
                    "Una debilidad presente en los procesos."
                ],
                "correct": 0,
            },
            {
                "id": "ctl-q2",
                "question": "¿Cuál es un ejemplo de control técnico?",
                "options": [
                    "Firewall.",
                    "Contraseña débil.",
                    "Ransomware.",
                    "Filtración de información."
                ],
                "correct": 0,
            },
            {
                "id": "ctl-q3",
                "question": "¿Qué tipos de controles existen?",
                "options": [
                    "Técnicos, administrativos, físicos o relacionados con las personas y los procesos.",
                    "Solo preventivos y punitivos.",
                    "Únicamente digitales y manuales.",
                    "Exclusivamente automáticos."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_tratamiento": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "trat-q1",
                "question": "¿Qué es el tratamiento del riesgo?",
                "options": [
                    "El proceso mediante el cual la organización decide qué hacer frente a un riesgo identificado.",
                    "La herramienta que organiza la probabilidad y el impacto.",
                    "El riesgo que permanece después de los controles.",
                    "La debilidad aprovechada por una amenaza."
                ],
                "correct": 0,
            },
            {
                "id": "trat-q2",
                "question": "¿Qué opciones de tratamiento puede decidir una organización?",
                "options": [
                    "Evitarlo, reducirlo, compartirlo o transferirlo, o aceptarlo.",
                    "Ignorarlo, ocultarlo, aumentarlo y financiarlo.",
                    "Negarlo, postergarlo, duplicarlo y archivarlo.",
                    "Eliminarlo, borrarlo, olvidarlo y sustituirlo."
                ],
                "correct": 0,
            },
            {
                "id": "trat-q3",
                "question": "¿Cuándo se acepta un riesgo?",
                "options": [
                    "Cuando se encuentra dentro de los criterios establecidos por la organización.",
                    "Cuando no existe ningún activo que proteger.",
                    "Cuando la amenaza desaparece por completo.",
                    "Cuando el impacto no se ha materializado nunca."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_riesgo_residual": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "rr-q1",
                "question": "¿Qué es el riesgo residual?",
                "options": [
                    "El riesgo que permanece después de aplicar controles o medidas de tratamiento.",
                    "El riesgo aceptado antes de identificar amenazas.",
                    "El impacto causado cuando se materializa una amenaza.",
                    "Un control que elimina todos los riesgos."
                ],
                "correct": 0,
            },
            {
                "id": "rr-q2",
                "question": "¿Por qué es importante volver a evaluar el riesgo después del tratamiento?",
                "options": [
                    "Porque los controles reducen el riesgo pero no necesariamente lo eliminan por completo.",
                    "Porque el riesgo siempre desaparece al aplicar controles.",
                    "Porque el riesgo nunca cambia con el tiempo.",
                    "Porque los activos no requieren valoración."
                ],
                "correct": 0,
            },
            {
                "id": "rr-q3",
                "question": "¿Qué afirma correctamente el concepto de riesgo residual?",
                "options": [
                    "Tras aplicar controles, queda un riesgo que debe seguir siendo monitoreado.",
                    "Los controles eliminan totalmente el riesgo y no queda nada por evaluar.",
                    "El riesgo residual es mayor antes de aplicar controles.",
                    "El riesgo residual no depende de las amenazas."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_matriz_riesgo": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "mr-q1",
                "question": "¿Qué es la matriz de riesgos?",
                "options": [
                    "Una herramienta para organizar y visualizar riesgos considerando principalmente probabilidad e impacto.",
                    "Una amenaza que afecta varios activos.",
                    "Un control que elimina todas las vulnerabilidades.",
                    "El proceso de aceptar un riesgo."
                ],
                "correct": 0,
            },
            {
                "id": "mr-q2",
                "question": "¿Qué factores considera principalmente la matriz de riesgos?",
                "options": [
                    "Probabilidad e impacto.",
                    "Contraseña y usuario.",
                    "Hardware y software.",
                    "Costo y ubicación."
                ],
                "correct": 0,
            },
            {
                "id": "mr-q3",
                "question": "¿Para qué sirve la matriz de riesgos?",
                "options": [
                    "Para priorizar riesgos y facilitar la toma de decisiones sobre controles y acciones de tratamiento.",
                    "Para aumentar la probabilidad de incidentes.",
                    "Para eliminar la necesidad de controles.",
                    "Para sustituir la valoración de activos."
                ],
                "correct": 0,
            },
        ],
    },
    "concepto_gestion_seguridad": {
        "version": 1,
        "required_score": 0.67,
        "questions": [
            {
                "id": "gs-q1",
                "question": "¿Qué es la gestión de la seguridad de la información?",
                "options": [
                    "Un conjunto organizado de procesos mediante los cuales la organización protege su información y gestiona los riesgos asociados.",
                    "Una herramienta que solo organiza probabilidad e impacto.",
                    "Un control único que elimina todos los riesgos.",
                    "El acto de instalar un firewall."
                ],
                "correct": 0,
            },
            {
                "id": "gs-q2",
                "question": "¿Qué requiere la gestión de la seguridad de la información?",
                "options": [
                    "Identificar activos, comprender amenazas y vulnerabilidades, evaluar riesgos, establecer controles, verificar resultados y mejorar continuamente.",
                    "Solo comprar más software de seguridad.",
                    "Únicamente capacitar a un empleado.",
                    "Exclusivamente respaldar la información."
                ],
                "correct": 0,
            },
            {
                "id": "gs-q3",
                "question": "¿Qué afirma correctamente el concepto de gestión de la seguridad?",
                "options": [
                    "La seguridad no consiste solamente en instalar herramientas.",
                    "La seguridad queda resuelta con un firewall.",
                    "Los controles técnicos reemplazan todo el proceso.",
                    "La gestión solo se hace una vez al año."
                ],
                "correct": 0,
            },
        ],
    },
}


def knowledge_check_definition(concept_id: str):
    """Obtiene la definición privada del Knowledge Check."""
    return KNOWLEDGE_CHECKS.get(str(concept_id))


def public_knowledge_check(concept_id: str):
    """Devuelve preguntas sin exponer las respuestas correctas."""
    definition = knowledge_check_definition(concept_id)
    if not definition:
        return None

    return {
        "version": definition["version"],
        "required_score": definition["required_score"],
        "questions": [
            {
                "id": question["id"],
                "question": question["question"],
                "options": list(question["options"]),
            }
            for question in definition["questions"]
        ],
    }

LEGACY_USER_ID = "local-owner"


def current_user_id() -> str:
    """Identidad activa: usuario autenticado o invitado temporal."""
    uid = session.get("user_id")
    if uid:
        return str(uid)

    guest_id = "guest-" + secrets.token_urlsafe(12)

    # El primer invitado local reclama los datos históricos de local-owner.
    # Esto permite que la migración de identidad no haga desaparecer
    # el progreso existente.
    try:
        connection = conn()
        legacy = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM video_progress
            WHERE user_id = ?
            """,
            (LEGACY_USER_ID,),
        ).fetchone()

        legacy_items = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM item_progress
            WHERE user_id = ?
            """,
            (LEGACY_USER_ID,),
        ).fetchone()

        has_legacy = (
            int(legacy["total"] or 0) > 0
            or int(legacy_items["total"] or 0) > 0
        )

        already_claimed = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE kind = 'guest'
            """
        ).fetchone()

        if has_legacy and int(already_claimed["total"] or 0) == 0:
            connection.execute(
                """
                UPDATE video_progress
                SET user_id = ?
                WHERE user_id = ?
                """,
                (guest_id, LEGACY_USER_ID),
            )
            connection.execute(
                """
                UPDATE item_progress
                SET user_id = ?
                WHERE user_id = ?
                """,
                (guest_id, LEGACY_USER_ID),
            )
            connection.execute(
                """
                UPDATE study_log
                SET user_id = ?
                WHERE user_id = ?
                """,
                (guest_id, LEGACY_USER_ID),
            )

        connection.execute(
            """
            INSERT OR IGNORE INTO users
            (user_id, kind, display_name)
            VALUES (?, 'guest', 'Invitado')
            """,
            (guest_id,),
        )
        connection.commit()
        connection.close()
    except Exception:
        try:
            connection.close()
        except Exception:
            pass

    session["user_id"] = guest_id
    session["user_kind"] = "guest"
    return guest_id


def conn() -> sqlite3.Connection:
    # En Vercel/serverless el filesystem es efímero: si hay credenciales
    # de Neon/Postgres se usa la base remota persistente. En local, SQLite.
    if vida_db.postgres_enabled():
        return vida_db.pg_conn()

    ensure_dirs()

    db_file = runtime_root() / "vida.db"

    connection = sqlite3.connect(db_file)
    connection.row_factory = sqlite3.Row

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS video_progress (
            video_id TEXT NOT NULL,
            course_id TEXT NOT NULL DEFAULT 'sena_ciberseguridad',
            position REAL NOT NULL DEFAULT 0,
            duration REAL NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (video_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS item_progress (
            item_id TEXT NOT NULL,
            course_id TEXT NOT NULL DEFAULT 'sena_ciberseguridad',
            completed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (item_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id TEXT NOT NULL DEFAULT 'sena_ciberseguridad',
            kind TEXT NOT NULL,
            ref_id TEXT,
            minutes REAL NOT NULL DEFAULT 0,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL DEFAULT 'user',
            username TEXT UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT,
            full_name TEXT,
            cedula TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    _migrate_existing_db(connection)
    _migrate_identity_db(connection)
    _ensure_learner_columns(connection)

    connection.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, kind, username, display_name)
        VALUES (?, 'user', 'local-owner', 'Usuario local')
        """,
        (LEGACY_USER_ID,),
    )

    connection.commit()
    return connection


def _migrate_existing_db(connection: sqlite3.Connection) -> None:
    """Convierte bases anteriores (sin course_id) al esquema multi-curso."""
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    if "study_log" in tables:
        cols = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(study_log)")
        }
        if "course_id" not in cols:
            connection.execute(
                "ALTER TABLE study_log ADD COLUMN "
                "course_id TEXT NOT NULL DEFAULT 'sena_ciberseguridad'"
            )

    for table, old_cols, new_ddl in [
        (
            "video_progress",
            "video_id, position, duration, completed, updated_at",
            """
            CREATE TABLE video_progress__mig (
                video_id TEXT NOT NULL,
                course_id TEXT NOT NULL DEFAULT 'sena_ciberseguridad',
                position REAL NOT NULL DEFAULT 0,
                duration REAL NOT NULL DEFAULT 0,
                completed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (video_id, course_id)
            )
            """,
        ),
        (
            "item_progress",
            "item_id, completed, updated_at",
            """
            CREATE TABLE item_progress__mig (
                item_id TEXT NOT NULL,
                course_id TEXT NOT NULL DEFAULT 'sena_ciberseguridad',
                completed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (item_id, course_id)
            )
            """,
        ),
    ]:
        if table not in tables:
            continue
        cols = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})")
        }
        if "course_id" in cols:
            continue
        connection.execute(new_ddl)
        connection.execute(
            f"INSERT INTO {table}__mig ({old_cols.replace(',', ',')}, course_id) "
            f"SELECT {old_cols}, 'sena_ciberseguridad' FROM {table}"
        )
        connection.execute(f"DROP TABLE {table}")
        connection.execute(f"ALTER TABLE {table}__mig RENAME TO {table}")



def _ensure_learner_columns(connection: sqlite3.Connection) -> None:
    """Añade nombre completo y cédula al perfil del aprendiz (idempotente)."""
    cols = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(users)")
    }
    if "full_name" not in cols:
        connection.execute(
            "ALTER TABLE users ADD COLUMN full_name TEXT"
        )
    if "cedula" not in cols:
        connection.execute(
            "ALTER TABLE users ADD COLUMN cedula TEXT"
        )
    connection.commit()


def _migrate_identity_db(connection: sqlite3.Connection) -> None:
    """Migra las tablas de progreso al modelo con identidad.

    Los datos existentes se asignan al usuario local heredado.
    La migración es idempotente y nunca elimina registros sin
    copiarlos previamente a la nueva estructura.
    """
    legacy_user = LEGACY_USER_ID

    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    # ---------------------------------------------------------
    # video_progress
    # ---------------------------------------------------------
    if "video_progress" in tables:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(video_progress)"
            )
        }

        if "user_id" not in columns:
            connection.execute("""
                CREATE TABLE video_progress__identity (
                    user_id TEXT NOT NULL DEFAULT 'local-owner',
                    video_id TEXT NOT NULL,
                    course_id TEXT NOT NULL
                        DEFAULT 'sena_ciberseguridad',
                    position REAL NOT NULL DEFAULT 0,
                    duration REAL NOT NULL DEFAULT 0,
                    completed INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, video_id, course_id)
                )
            """)

            connection.execute("""
                INSERT INTO video_progress__identity (
                    user_id,
                    video_id,
                    course_id,
                    position,
                    duration,
                    completed,
                    updated_at
                )
                SELECT
                    ?,
                    video_id,
                    course_id,
                    position,
                    duration,
                    completed,
                    updated_at
                FROM video_progress
            """, (legacy_user,))

            connection.execute("DROP TABLE video_progress")

            connection.execute("""
                ALTER TABLE video_progress__identity
                RENAME TO video_progress
            """)

    # ---------------------------------------------------------
    # item_progress
    # ---------------------------------------------------------
    if "item_progress" in tables:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(item_progress)"
            )
        }

        if "user_id" not in columns:
            connection.execute("""
                CREATE TABLE item_progress__identity (
                    user_id TEXT NOT NULL DEFAULT 'local-owner',
                    item_id TEXT NOT NULL,
                    course_id TEXT NOT NULL
                        DEFAULT 'sena_ciberseguridad',
                    completed INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, item_id, course_id)
                )
            """)

            connection.execute("""
                INSERT INTO item_progress__identity (
                    user_id,
                    item_id,
                    course_id,
                    completed,
                    updated_at
                )
                SELECT
                    ?,
                    item_id,
                    course_id,
                    completed,
                    updated_at
                FROM item_progress
            """, (legacy_user,))

            connection.execute("DROP TABLE item_progress")

            connection.execute("""
                ALTER TABLE item_progress__identity
                RENAME TO item_progress
            """)

    # ---------------------------------------------------------
    # study_log
    # ---------------------------------------------------------
    if "study_log" in tables:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(study_log)"
            )
        }

        if "user_id" not in columns:
            connection.execute("""
                ALTER TABLE study_log
                ADD COLUMN user_id TEXT NOT NULL
                    DEFAULT 'local-owner'
            """)

def engine_state(course_id: str | None = None) -> dict:
    cid = course_id or active_course_id()
    uid = current_user_id()
    connection = conn()

    items = connection.execute(
        "SELECT item_id, completed, course_id FROM item_progress "
        "WHERE user_id = ? AND course_id = ?",
        (uid, cid),
    ).fetchall()

    videos = connection.execute(
        """
        SELECT video_id, position, duration, completed
        FROM video_progress
        WHERE user_id = ? AND course_id = ?
        """,
        (uid, cid),
    ).fetchall()

    log = connection.execute(
        "SELECT COALESCE(SUM(minutes), 0) AS minutes FROM study_log "
        "WHERE user_id = ? AND course_id = ?",
        (uid, cid),
    ).fetchone()

    connection.close()

    course_data = course(cid)
    profile = ProfileEngine(profile_path(cid)).load()

    videos_cfg = course_data.get("videos", [])
    activities_cfg = [
        item
        for item in course_data.get("items", [])
        if item.get("kind") == "activity"
    ]
    concepts_cfg = course_data.get("concepts", [])
    activity_ids_cfg = {str(item["id"]) for item in activities_cfg}

    completed_any = {
        row["item_id"] for row in items if row["completed"]
    }
    completed_activity_ids = {
        item_id
        for item_id in completed_any
        if item_id in activity_ids_cfg
    }
    completed_video_ids = {
        row["video_id"] for row in videos if row["completed"]
    }

    verified_concepts = set()
    for concept in concepts_cfg:
        concept_id = str(concept["id"])
        if f"concept:{concept_id}" in completed_any:
            verified_concepts.add(concept_id)

    progress_engine = ProgressEngine()
    snapshot = progress_engine.calculate(
        completed_videos=len(completed_video_ids),
        total_videos=len(videos_cfg),
        completed_activities=len(completed_activity_ids),
        total_activities=len(activities_cfg),
        verified_concepts=len(verified_concepts),
        total_concepts=len(concepts_cfg),
        evidence_count=_evidence_count(),
        unknown_count=0,
        profile=profile,
    )

    unknown_count = 0
    if videos_cfg and len(completed_video_ids) < len(videos_cfg):
        unknown_count += 1
    if activities_cfg and len(completed_activity_ids) < len(activities_cfg):
        unknown_count += 1
    if concepts_cfg and len(verified_concepts) < len(concepts_cfg):
        unknown_count += 1

    intelligence = IntelligenceEngine(profile=profile)
    score = intelligence.learning_score(
        course_data,
        completed_video_ids,
        completed_activity_ids,
        verified_concepts,
        snapshot.evidence_count,
    )
    signals = intelligence.signals(
        course_data,
        completed_video_ids,
        completed_activity_ids,
        verified_concepts,
        snapshot.evidence_count,
    )
    actions = intelligence.next_actions(
        course_data,
        completed_video_ids,
        completed_activity_ids,
        verified_concepts,
        snapshot.evidence_count,
    )

    certificate = CertificateEngine(certificates_root())
    course_id = profile.course_id
    issued_record = _load_issued(certificate, course_id)

    eligibility = certificate.eligibility_report(
        operational=snapshot.operational,
        mastery=snapshot.mastery,
        evidence_count=snapshot.evidence_count,
        required_videos=len(videos_cfg),
        completed_videos=len(completed_video_ids),
        required_activities=len(activities_cfg),
        completed_activities=len(completed_activity_ids),
        required_concepts=len(concepts_cfg),
        verified_concepts=len(verified_concepts),
        unknown_count=unknown_count,
        user_confirmation=True,
    )

    return {
        "overall": snapshot.operational,
        "mastery": snapshot.mastery,
        "evidence_count": snapshot.evidence_count,
        "evidence_strength": round(snapshot.evidence_strength, 4),
        "unknown_count": unknown_count,
        "operational": snapshot.operational,
        "video_progress": round(snapshot.video_progress, 4),
        "activity_progress": round(snapshot.activity_progress, 4),
        "concept_progress": round(snapshot.concept_progress, 4),
        "study_minutes": round(float(log["minutes"])),
        "video_count": len(videos_cfg),
        "completed_videos": len(completed_video_ids),
        "activity_count": len(activities_cfg),
        "completed_activities": len(completed_activity_ids),
        "concept_count": len(concepts_cfg),
        "verified_concepts": len(verified_concepts),
        "verified_concept_ids": sorted(verified_concepts),
        "learning_score": score,
        "signals": [
            {
                "name": signal.name,
                "value": signal.value,
                "source": signal.source,
                "kind": signal.kind,
            }
            for signal in signals
        ],
        "next_actions": actions,
        "certificate": {
            "course_id": course_id,
            "issued": bool(issued_record),
            "certificate_id": (
                issued_record.get("certificate_id")
                if issued_record
                else None
            ),
            "status": (
                issued_record.get("status")
                if issued_record
                else "PENDING"
            ),
        },
        "certificate_eligible": bool(eligibility["eligible"]),
    }


def _blob_evidence_count(uid: str, cid: str) -> int:
    """Cuenta las evidencias persistentes del usuario en Blob.

    En el deploy los registros viven en Blob (sobreviven al reinicio de
    la instancia), mientras que evidence.json es efímero.
    """
    if not _cert_blob_enabled():
        return 0

    from vercel.blob import BlobClient

    client = BlobClient()
    total = 0
    cursor = None
    try:
        while True:
            page = client.list_objects(
                prefix="vida/evidence/",
                limit=1000,
                cursor=cursor,
            )
            for blob in page.blobs:
                pathname = blob.pathname
                if not pathname.endswith(".json"):
                    continue
                try:
                    result = client.get(pathname, access="private")
                    if result is None or result.status_code != 200:
                        continue
                    body = _blob_body(result)
                    if body is None:
                        continue
                    payload = json.loads(body.decode("utf-8"))
                except (OSError, ValueError, UnicodeDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                context = payload.get("context") or {}
                if (
                    str(context.get("user_id", "")) == uid
                    and str(context.get("course_id", "")) == cid
                ):
                    total += 1
            if not page.has_more:
                break
            cursor = page.cursor
    except Exception:
        return 0
    return total


def _evidence_count() -> int:
    uid = current_user_id()
    cid = active_course_id()

    blob_total = _blob_evidence_count(uid, cid)
    if blob_total > 0:
        return blob_total

    evidence_dir = evidence_root()
    if not evidence_dir.exists():
        return 0
    total = 0
    for path in evidence_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, list):
            total += sum(
                1
                for record in data
                if record.get("context", {}).get("user_id") == uid
                and record.get("context", {}).get("course_id") == cid
            )
    return total


def _evidence_for(activity_id: str) -> list[dict]:
    uid = current_user_id()
    cid = active_course_id()

    path = evidence_root() / "evidence.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [
        record
        for record in data
        if (
            record.get("context", {}).get("activity_id") == activity_id
            and record.get("context", {}).get("user_id") == uid
            and record.get("context", {}).get("course_id") == cid
        )
    ]


def _uploaded_files(activity_id: str) -> list[dict]:
    activity_dir = evidence_root() / activity_id
    if not activity_dir.exists():
        return []
    files = []
    for path in sorted(activity_dir.iterdir()):
        if path.is_file():
            files.append(
                {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "url": (
                        f"/media/evidence/{activity_id}/{path.name}"
                    ),
                }
            )
    return files


def _cert_blob_enabled() -> bool:
    """Persistencia de certificados en Vercel Blob cuando hay token."""
    return bool(os.getenv("BLOB_READ_WRITE_TOKEN"))


def _cert_blob_client():
    from vercel.blob import BlobClient
    return BlobClient()


def _cert_blob_path(course_id: str, user_id: str | None = None) -> str:
    safe = str(course_id).strip().replace(" ", "_")
    if user_id:
        return f"vida/certificates/{user_id}/{safe}.issued.json"
    return f"vida/certificates/{safe}.issued.json"


def _blob_body(result) -> bytes | None:
    """Extrae el cuerpo de un BlobGetResult sin depender de la versión del SDK.

    Las versiones nuevas del SDK de Vercel devuelven el cuerpo en ``content``
    (bytes); las anteriores lo exponían como ``stream``.
    """
    if result is None:
        return None

    stream = getattr(result, "stream", None)
    if stream is not None:
        try:
            return b"".join(stream)
        except (TypeError, ValueError):
            pass

    content = getattr(result, "content", None)
    if isinstance(content, (bytes, bytearray)):
        return bytes(content)
    if content is not None:
        try:
            return b"".join(content)
        except (TypeError, ValueError):
            return None

    return None


def _load_issued(
    certificate_engine: CertificateEngine,
    course_id: str,
    user_id: str | None = None,
) -> dict | None:
    # En el deploy, el certificado queda en Blob para sobrevivir
    # entre instancias y redespliegues.
    if _cert_blob_enabled():
        try:
            client = _cert_blob_client()
            result = client.get(
                _cert_blob_path(course_id, user_id),
                access="private",
            )
            if result is not None and result.status_code == 200:
                payload_bytes = _blob_body(result)
                if payload_bytes is not None:
                    payload = json.loads(
                        payload_bytes.decode("utf-8")
                    )
                    if isinstance(payload, dict):
                        return payload
        except Exception:
            pass

        if user_id:
            # Retrocompatibilidad: el certificado histórico emitido por
            # curso (sin identidad) sigue siendo válido para verificación.
            try:
                client = _cert_blob_client()
                result = client.get(
                    _cert_blob_path(course_id, None),
                    access="private",
                )
                if result is not None and result.status_code == 200:
                    payload_bytes = _blob_body(result)
                    if payload_bytes is not None:
                        payload = json.loads(
                            payload_bytes.decode("utf-8")
                        )
                        if isinstance(payload, dict):
                            return payload
            except Exception:
                pass

    record = certificate_engine._course_record(course_id, user_id)
    if not record.exists():
        if user_id:
            record = certificate_engine._course_record(course_id, None)
        if not record.exists():
            return None
    import json as _json
    return _json.loads(record.read_text(encoding="utf-8"))


def _load_issued_by_id(
    certificate_engine: CertificateEngine,
    certificate_id: str,
) -> dict | None:
    """Busca un certificado emitido por su identificador, sin importar
    a qué usuario pertenezca (persistencia en Blob o local)."""
    candidates: list[str] = []

    if _cert_blob_enabled():
        try:
            client = _cert_blob_client()
            cursor = None
            while True:
                page = client.list_objects(
                    prefix="vida/certificates/",
                    limit=1000,
                    cursor=cursor,
                )
                candidates.extend(
                    blob.pathname
                    for blob in page.blobs
                    if blob.pathname.endswith(".issued.json")
                )
                if not page.has_more:
                    break
                cursor = page.cursor
        except Exception:
            pass

    root = Path(certificate_engine.out_dir)
    if root.exists():
        for record in root.rglob("*.issued.json"):
            candidates.append(str(record.resolve()))

    for candidate in candidates:
        try:
            if candidate.startswith("vida/"):
                client = _cert_blob_client()
                result = client.get(candidate, access="private")
                if result is None or result.status_code != 200:
                    continue
                payload_bytes = _blob_body(result)
                if payload_bytes is None:
                    continue
                payload = json.loads(payload_bytes.decode("utf-8"))
            else:
                payload = json.loads(
                    Path(candidate).read_text(encoding="utf-8")
                )
        except (OSError, ValueError, UnicodeDecodeError):
            continue

        if isinstance(payload, dict) and payload.get("certificate_id") == certificate_id:
            return payload

    return None


def _resolve_video_file(file_ref: str) -> tuple[bool, int]:
    """Devuelve (disponible, tamaño_bytes) para una referencia de video.

    Coincide con la resolución del frontend (mediaUrl): las URLs
    externas o absolutas no se verifican localmente (se asumen en línea),
    mientras que los nombres de archivo se buscan en media/videos/.
    """
    ref = str(file_ref or "")
    if not ref:
        return False, 0
    if ref.startswith(("http://", "https://", "/")):
        return True, 0
    candidate = MEDIA / "videos" / Path(ref).name
    if candidate.is_file():
        return True, candidate.stat().st_size
    return False, 0


def _cert_token() -> str:
    """Clave privada del certificado.

    Prioridad: variable de entorno VIDA_CERT_KEY (único modo en el deploy).
    En local, se genera un token aleatorio la primera vez y se guarda en
    data/.cert_token (chmod 600); nunca se publica en el código.
    """
    env_token = os.environ.get("VIDA_CERT_KEY", "").strip()
    if env_token:
        return env_token
    token_file = runtime_root() / ".cert_token"
    if not token_file.exists():
        try:
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(secrets.token_urlsafe(24), encoding="utf-8")
            token_file.chmod(0o600)
        except OSError:
            return ""
    try:
        token = token_file.read_text(encoding="utf-8").strip()
    except OSError:
        token = ""
    return token


def _cert_allowed(req: request) -> bool:
    supplied = (
        req.headers.get("X-Vida-Key")
        or req.headers.get("X-Cert-Key")
        or req.args.get("clave")
        or req.args.get("token")
    )
    if not supplied:
        return False
    return compare_digest(str(supplied).strip(), _cert_token())


def api_snapshot() -> dict:
    return engine_state()


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(ROOT / "vida_ui_pro"),
        static_folder=str(ROOT / "vida_ui_pro"),
        static_url_path="/static",
    )

    app.secret_key = os.environ.get(
        "VIDA_SECRET_KEY",
        os.environ.get(
            "VIDA_SESSION_SECRET",
            "vida-local-development-secret-change-me",
        ),
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = True

    if os.environ.get("VERCEL") and not vida_db.postgres_enabled():
        console.print(
            "[bold yellow]⚠️  VERCEL sin DATABASE_URL: la base de datos "
            "será efímera y las cuentas/progreso se perderán al refrescar. "
            "Crea una base Neon/Postgres desde el tab Storage de Vercel y "
            "configura DATABASE_URL.[/bold yellow]"
        )

    if (
        os.environ.get("VERCEL")
        and app.secret_key == "vida-local-development-secret-change-me"
    ):
        console.print(
            "[bold yellow]⚠️  VERCEL usa el secret_key por defecto. "
            "Configura VIDA_SECRET_KEY como variable de entorno.[/bold yellow]"
        )

    @app.after_request
    def _hardened_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-XSS-Protection", "1; mode=block")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        return resp

    @app.post("/api/voice")
    def api_voice():
        """Sintetiza voz con Piper manteniendo el modelo cargado en memoria."""
        global _piper_voice

        payload = request.get_json(silent=True) or {}
        text_to_speak = str(payload.get("text", "")).strip()

        if not text_to_speak:
            return jsonify({
                "ok": False,
                "error": "No se recibió texto."
            }), 400

        if len(text_to_speak) > 2000:
            return jsonify({
                "ok": False,
                "error": "El texto de voz supera el límite permitido."
            }), 400

        model = ROOT / "voices" / "piper" / "es_ES-sharvard-medium.onnx"

        if not model.exists():
            return jsonify({
                "ok": False,
                "error": "No está disponible la voz oficial de VIDA."
            }), 503

        output = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )
        output_path = Path(output.name)
        output.close()

        try:
            # Cargar Piper UNA sola vez y conservarlo en memoria.
            if _piper_voice is None:
                with _piper_lock:
                    if _piper_voice is None:
                        _piper_voice = PiperVoice.load(str(model))

            with _piper_lock:
                import wave

                with wave.open(str(output_path), "wb") as wav_file:
                    _piper_voice.synthesize_wav(
                        text_to_speak,
                        wav_file
                    )

            if not output_path.exists():
                return jsonify({
                    "ok": False,
                    "error": "Piper no pudo generar el audio."
                }), 500

            audio = output_path.read_bytes()

            return app.response_class(
                audio,
                mimetype="audio/wav",
                headers={
                    "Cache-Control": "no-store",
                    "X-VIDA-Voice": "Piper/es_ES-sharvard-medium",
                },
            )

        except Exception as exc:
            return jsonify({
                "ok": False,
                "error": f"Error del motor de voz: {exc}"
            }), 500

        finally:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass

    @app.get("/api/me")
    def api_me():
        uid = current_user_id()
        connection = conn()
        row = connection.execute(
            """
            SELECT user_id, kind, username, display_name, full_name, cedula, created_at
            FROM users
            WHERE user_id = ?
            """,
            (uid,),
        ).fetchone()

        if row is None:
            kind = session.get("user_kind", "guest")
            connection.execute(
                """
                INSERT OR IGNORE INTO users
                (user_id, kind, display_name)
                VALUES (?, ?, ?)
                """,
                (uid, kind, "Invitado"),
            )
            connection.commit()
            row = connection.execute(
                """
                SELECT user_id, kind, username, display_name, full_name, cedula, created_at
                FROM users
                WHERE user_id = ?
                """,
                (uid,),
            ).fetchone()

        connection.close()

        user = dict(row)
        user.pop("full_name", None)
        user.pop("cedula", None)
        user["profile"] = profile_payload(row)

        return jsonify({
            "ok": True,
            "user": user,
        })


    @app.get("/api/user/profile")
    def api_user_profile():
        """Compatibilidad para clientes que solicitan /api/user/profile."""
        uid = current_user_id()
        connection = conn()

        try:
            row = connection.execute(
                """
                SELECT user_id, kind, username, display_name,
                       full_name, cedula, created_at
                FROM users
                WHERE user_id = ?
                """,
                (uid,),
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return jsonify(
                {
                    "ok": False,
                    "error": "Perfil no encontrado.",
                }
            ), 404

        display_name = str(
            row.get("display_name", "") or ""
        ).strip()

        full_name = str(
            row.get("full_name", "") or ""
        ).strip()

        nombre = (
            display_name
            or decrypt_profile_value(full_name)
            or "Invitado"
        )

        return jsonify(
            {
                "ok": True,
                "nombre": nombre,
                "user": {
                    "user_id": row.get("user_id"),
                    "username": row.get("username"),
                    "kind": row.get("kind"),
                    "display_name": display_name,
                    "profile": profile_payload(row),
                },
            }
        )


    @app.patch("/api/profile")
    def api_update_profile():
        """Actualiza el perfil identificable del aprendiz (nombre y cédula)."""
        payload = request.get_json(silent=True) or {}

        uid = str(current_user_id())
        if session.get("user_kind") == "guest":
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "El perfil personal requiere una cuenta "
                        "registrada."
                    ),
                }
            ), 403

        full_name = str(payload.get("full_name", "")).strip()
        cedula = str(payload.get("cedula", "")).strip()

        if not full_name:
            return jsonify({
                "ok": False,
                "error": "Nombre y apellidos obligatorios."
            }), 400

        if not cedula:
            return jsonify({
                "ok": False,
                "error": "Número de cédula obligatorio."
            }), 400

        try:
            enc_full_name = encrypt_profile_value(full_name)
            enc_cedula = encrypt_profile_value(cedula)
        except RuntimeError as exc:
            return jsonify({
                "ok": False,
                "error": str(exc),
            }), 503

        connection = conn()
        connection.execute(
            """
            UPDATE users
            SET full_name = ?, cedula = ?
            WHERE user_id = ?
            """,
            (enc_full_name, enc_cedula, uid),
        )
        connection.commit()

        row = connection.execute(
            """
            SELECT user_id, kind, username, display_name, full_name, cedula, created_at
            FROM users
            WHERE user_id = ?
            """,
            (uid,),
        ).fetchone()
        connection.close()

        if row is None:
            return jsonify({
                "ok": False,
                "error": "No se encontró tu perfil."
            }), 404

        return jsonify({
            "ok": True,
            "profile": profile_payload(row),
        })


    @app.post("/api/guest")
    def api_guest():
        """
        Activa la identidad Invitado de la sesión actual.

        IMPORTANTE:
        - No genera un nuevo invitado si ya existe uno.
        - No borra la sesión existente.
        - Conserva el progreso asociado al invitado actual.
        """
        existing_uid = session.get("user_id")
        existing_kind = session.get("user_kind")

        if existing_uid and existing_kind == "guest":
            uid = str(existing_uid)

            connection = conn()
            row = connection.execute(
                """
                SELECT user_id, kind, username, display_name, created_at
                FROM users
                WHERE user_id = ?
                """,
                (uid,),
            ).fetchone()

            if row is None:
                connection.execute(
                    """
                    INSERT INTO users
                    (user_id, kind, display_name)
                    VALUES (?, 'guest', 'Invitado')
                    """,
                    (uid,),
                )
                connection.commit()
                row = connection.execute(
                    """
                    SELECT user_id, kind, username, display_name, created_at
                    FROM users
                    WHERE user_id = ?
                    """,
                    (uid,),
                ).fetchone()

            connection.close()

            return jsonify({
                "ok": True,
                "user_id": row["user_id"],
                "kind": row["kind"],
                "display_name": row["display_name"] or "Invitado",
            })

        # Si había otra identidad activa, iniciar una nueva sesión de Invitado.
        session.clear()

        uid = "guest-" + secrets.token_urlsafe(12)

        session["user_id"] = uid
        session["user_kind"] = "guest"

        connection = conn()
        connection.execute(
            """
            INSERT INTO users
            (user_id, kind, display_name)
            VALUES (?, 'guest', 'Invitado')
            """,
            (uid,),
        )
        connection.commit()
        connection.close()

        return jsonify({
            "ok": True,
            "user_id": uid,
            "kind": "guest",
            "display_name": "Invitado",
        })


    @app.post("/api/register")
    def api_register():
        payload = request.get_json(silent=True) or {}

        username = str(payload.get("username", "")).strip().lower()
        display_name = str(
            payload.get("display_name") or username
        ).strip()
        password = str(payload.get("password", ""))
        full_name = str(payload.get("full_name", "")).strip()
        cedula = str(payload.get("cedula", "")).strip()

        if len(username) < 3:
            return jsonify({
                "ok": False,
                "error": "El usuario debe tener al menos 3 caracteres."
            }), 400

        if len(password) < 8:
            return jsonify({
                "ok": False,
                "error": "La contraseña debe tener al menos 8 caracteres."
            }), 400

        if not display_name:
            return jsonify({
                "ok": False,
                "error": "El nombre es obligatorio."
            }), 400

        if not full_name:
            return jsonify({
                "ok": False,
                "error": (
                    "Escribe tus nombres y apellidos: son los que "
                    "aparecerán en tu certificado."
                ),
            }), 400

        if not cedula:
            return jsonify({
                "ok": False,
                "error": (
                    "Escribe tu número de cédula: aparecerá en tu "
                    "certificado."
                ),
            }), 400

        old_uid = current_user_id()
        new_uid = "user-" + secrets.token_urlsafe(12)

        try:
            enc_full_name = encrypt_profile_value(full_name)
            enc_cedula = encrypt_profile_value(cedula)
        except RuntimeError as exc:
            return jsonify({
                "ok": False,
                "error": str(exc),
            }), 503

        connection = conn()

        try:
            exists = connection.execute(
                "SELECT 1 FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if exists:
                connection.close()
                return jsonify({
                    "ok": False,
                    "error": "Ese usuario ya existe."
                }), 409

            connection.execute("BEGIN")

            connection.execute(
                """
                INSERT INTO users
                (user_id, kind, username, display_name, password_hash, full_name, cedula)
                VALUES (?, 'user', ?, ?, ?, ?, ?)
                """,
                (
                    new_uid,
                    username,
                    display_name,
                    generate_password_hash(password),
                    enc_full_name,
                    enc_cedula,
                ),
            )

            connection.execute(
                """
                UPDATE video_progress
                SET user_id = ?
                WHERE user_id = ?
                """,
                (new_uid, old_uid),
            )

            connection.execute(
                """
                UPDATE item_progress
                SET user_id = ?
                WHERE user_id = ?
                """,
                (new_uid, old_uid),
            )

            connection.execute(
                """
                UPDATE study_log
                SET user_id = ?
                WHERE user_id = ?
                """,
                (new_uid, old_uid),
            )

            connection.commit()

        except (sqlite3.IntegrityError, vida_db.IntegrityError):
            connection.rollback()
            connection.close()
            return jsonify({
                "ok": False,
                "error": "No fue posible crear la cuenta."
            }), 409
        except Exception:
            connection.rollback()
            connection.close()
            raise

        connection.close()

        session.clear()
        session["user_id"] = new_uid
        session["user_kind"] = "user"

        return jsonify({
            "ok": True,
            "user_id": new_uid,
            "kind": "user",
            "username": username,
            "display_name": display_name,
            "profile": {
                "complete": True,
                "has_full_name": True,
                "has_cedula": True,
                "masked_cedula": _masked_cedula(enc_cedula),
            },
        }), 201


    @app.post("/api/login")
    def api_login():
        payload = request.get_json(silent=True) or {}

        username = str(payload.get("username", "")).strip().lower()
        password = str(payload.get("password", ""))

        connection = conn()
        row = connection.execute(
            """
            SELECT user_id, kind, username, display_name, full_name, cedula, password_hash
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
        connection.close()

        if not row or not row["password_hash"]:
            return jsonify({
                "ok": False,
                "error": "Usuario o contraseña incorrectos."
            }), 401

        if not check_password_hash(row["password_hash"], password):
            return jsonify({
                "ok": False,
                "error": "Usuario o contraseña incorrectos."
            }), 401

        session.clear()
        session["user_id"] = row["user_id"]
        session["user_kind"] = "user"

        return jsonify({
            "ok": True,
            "user_id": row["user_id"],
            "kind": row["kind"],
            "username": row["username"],
            "display_name": row["display_name"],
            "profile": profile_payload(row),
        })


    @app.post("/api/logout")
    def api_logout():
        session.clear()
        return jsonify({
            "ok": True,
            "message": "Sesión cerrada.",
        })


    @app.get("/")
    def home():
        return render_template(
            "index_pro.html",
            course=course(),
        )

    @app.get("/api/dashboard")
    def dashboard():
        return jsonify(api_snapshot())

    @app.get("/api/courses")
    def courses_index():
        ids = _discover_course_ids()
        active = active_course_id()
        items = []
        for cid in ids:
            data = course(cid)
            items.append(
                {
                    "id": cid,
                    "active": cid == active,
                    "title": data.get("title", cid),
                    "provider": data.get("provider", ""),
                    "platform": data.get("platform", ""),
                    "hours": data.get("hours", 0),
                    "learner": data.get("learner", ""),
                }
            )
        items.sort(key=lambda item: 0 if item["active"] else 1)
        return jsonify({"active": active, "courses": items})

    @app.post("/api/courses/<course_id>/activate")
    def activate_course(course_id: str):
        if not _cert_allowed(request):
            return jsonify(
                {
                    "ok": False,
                    "error": "Acceso denegado. Se requiere permiso del sistema.",
                }
            ), 403
        if not set_active_course_id(course_id):
            return jsonify(
                {"ok": False, "error": "Curso desconocido."}
            ), 404
        return jsonify(
            {
                "ok": True,
                "active": active_course_id(),
                "state": engine_state(),
                "course": course(),
            }
        )

    @app.post("/api/courses")
    def create_course():
        if not _cert_allowed(request):
            return jsonify(
                {
                    "ok": False,
                    "error": "Acceso denegado. Se requiere permiso del sistema.",
                }
            ), 403
        payload = request.get_json(silent=True) or {}
        try:
            cid = register_course(payload, activate=True)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify(
            {
                "ok": True,
                "active": active_course_id(),
                "course_id": cid,
                "courses": courses_index()[0].get_json(),
                "state": engine_state(),
            }
        ), 201

    @app.get("/api/course")
    def get_course():
        return jsonify(course())

    @app.get("/api/videos")
    def videos_api():
        course_data = course()
        items = []
        for video in course_data.get("videos", []):
            file_ref = str(video.get("file", "") or "")
            available, size = _resolve_video_file(file_ref)
            items.append(
                {
                    "id": video.get("id"),
                    "title": video.get("title", ""),
                    "file": file_ref,
                    "available": available,
                    "required": bool(video.get("required", False)),
                    "size_bytes": size,
                }
            )
        return jsonify(
            {
                "course_id": active_course_id(),
                "count": len(items),
                "available_count": sum(1 for v in items if v["available"]),
                "videos": items,
            }
        )

    @app.get("/api/rules")
    def rules_info():
        rules_file = DATA / "rules.json"
        rules_data = {}
        if rules_file.exists():
            rules_data = json.loads(
                rules_file.read_text(encoding="utf-8")
            )

        state = api_snapshot()
        course_data = course()

        required_videos = len(course_data.get("videos", []))
        required_activities = len(
            [
                item
                for item in course_data.get("items", [])
                if item.get("kind") == "activity"
            ]
        )
        required_concepts = len(course_data.get("concepts", []))

        engine = CertificateEngine(certificates_root())
        checks = engine.eligibility_report(
            operational=state["operational"],
            mastery=state["mastery"],
            evidence_count=state["evidence_count"],
            required_videos=required_videos,
            completed_videos=state["completed_videos"],
            required_activities=required_activities,
            completed_activities=state["completed_activities"],
            required_concepts=required_concepts,
            verified_concepts=state["verified_concepts"],
            unknown_count=state["unknown_count"],
            user_confirmation=bool(
                state["certificate"]["issued"]
            ),
        )

        profile = ProfileEngine(profile_path()).load()
        grading = {
            "engines": [
                "ProgressEngine",
                "IntelligenceEngine",
                "EvidenceEngine",
                "CertificateEngine",
            ],
            "formula": (
                "overall = Σ (peso_i × progreso_i)   ·   "
                "mastery = conceptos verificados / total   ·   "
                "learning_score = Inteligencia adaptativa"
            ),
            "weights": dict(profile.weights),
            "components": profile.enabled_components(),
            "course_id": profile.course_id,
        }

        return jsonify(
            {
                "course": {
                    "id": course_data.get("id"),
                    "title": course_data.get("title"),
                    "provider": course_data.get("provider"),
                    "platform": course_data.get("platform"),
                    "hours": course_data.get("hours"),
                },
                "grading": grading,
                "principles": rules_data.get("principles", []),
                "certificate_policy": rules_data.get(
                    "certificate_policy", {}
                ),
                "eligibility": checks,
                "state": {
                    "operational": state["operational"],
                    "mastery": state["mastery"],
                    "evidence_count": state["evidence_count"],
                    "unknown_count": state["unknown_count"],
                    "completed_videos": state["completed_videos"],
                    "required_videos": required_videos,
                    "completed_activities": state[
                        "completed_activities"
                    ],
                    "required_activities": required_activities,
                    "verified_concepts": state["verified_concepts"],
                    "required_concepts": required_concepts,
                },
            }
        )

    @app.get("/api/certificate")
    def certificate_status():
        return jsonify(api_snapshot()["certificate"])

    @app.post("/api/certificate")
    def issue_certificate():
        payload = request.get_json(silent=True) or {}

        user_confirmation = bool(
            payload.get("user_confirmation", False)
        )

        # El certificado es personal: cada aprendiz registrado emite el suyo.
        uid = str(current_user_id())
        kind = session.get("user_kind", "guest")

        if kind == "guest":
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "El certificado es personal: crea una cuenta "
                        "con tu nombre y cédula para emitir el tuyo."
                    ),
                }
            ), 403

        connection = conn()
        user_row = connection.execute(
            """
            SELECT user_id, kind, username, display_name, full_name, cedula
            FROM users
            WHERE user_id = ?
            """,
            (uid,),
        ).fetchone()
        connection.close()

        full_name = (
            decrypt_profile_value(
                str(user_row["full_name"] or "").strip()
            )
            if user_row
            else ""
        )
        display_name = (
            str(user_row["display_name"] or "").strip()
            if user_row
            else ""
        )
        cedula = (
            decrypt_profile_value(
                str(user_row["cedula"] or "").strip()
            )
            if user_row
            else ""
        )

        if user_row is None:
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "No se encontró tu perfil. "
                        "Vuelve a iniciar sesión."
                    ),
                }
            ), 403

        state = api_snapshot()

        engine = CertificateEngine(certificates_root())
        course_data = course()
        profile = ProfileEngine(profile_path()).load()

        required_videos = len(course_data.get("videos", []))
        required_activities = len(
            [
                item
                for item in course_data.get("items", [])
                if item.get("kind") == "activity"
            ]
        )
        required_concepts = len(course_data.get("concepts", []))

        # El certificado personal ya emitido persiste en Blob: evita
        # duplicar entre instancias del deploy incluso si /tmp se reinicia.
        already = _load_issued(engine, profile.course_id, uid)
        if already:
            return jsonify(
                {
                    "ok": False,
                    "error": "Ya tienes un certificado emitido para este curso.",
                    "certificate_id": already.get("certificate_id"),
                    "verification_url": (
                        f"/verificar/{already.get('certificate_id')}"
                        if already.get("certificate_id")
                        else None
                    ),
                }
            ), 409

        learner = full_name or display_name or str(
            course_data.get(
                "learner",
                "Aprendiz VIDA",
            )
        )

        try:
            cert = engine.issue_once(
                course_id=profile.course_id,
                learner=learner,
                course=str(
                    course_data.get(
                        "title",
                        "Curso SENA",
                    )
                ),
                operational=state["operational"],
                mastery=state["mastery"],
                evidence_count=state["evidence_count"],
                required_videos=required_videos,
                completed_videos=state["completed_videos"],
                required_activities=required_activities,
                completed_activities=state["completed_activities"],
                required_concepts=required_concepts,
                verified_concepts=state["verified_concepts"],
                unknown_count=state["unknown_count"],
                user_confirmation=user_confirmation,
                user_id=uid,
                cedula=cedula,
            )
        except CertificateAlreadyIssued as exc:
            issued = _load_issued(
                engine,
                profile.course_id,
                uid,
            )
            return jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                    "certificate_id": (
                        issued.get("certificate_id")
                        if issued
                        else None
                    ),
                    "verification_url": (
                        f"/verificar/{issued.get('certificate_id')}"
                        if issued
                        else None
                    ),
                }
            ), 409

        except CertificateNotEligible as exc:
            return jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                    "checks": engine.eligibility_report(
                        operational=state["operational"],
                        mastery=state["mastery"],
                        evidence_count=state["evidence_count"],
                        required_videos=required_videos,
                        completed_videos=state["completed_videos"],
                        required_activities=required_activities,
                        completed_activities=state["completed_activities"],
                        required_concepts=required_concepts,
                        verified_concepts=state["verified_concepts"],
                        unknown_count=state["unknown_count"],
                        user_confirmation=user_confirmation,
                    ),
                }
            ), 409

        except OSError:
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "El entorno de despliegue es de solo lectura: "
                        "el certificado solo se emite en la versión local."
                    ),
                }
            ), 503

        # Archivar en Blob para que el certificado sobreviva entre
        # instancias y redespliegues.
        if _cert_blob_enabled():
            try:
                client = _cert_blob_client()
                client.put(
                    _cert_blob_path(profile.course_id, uid),
                    json.dumps(
                        cert.to_dict(), ensure_ascii=False
                    ).encode("utf-8"),
                    access="private",
                    content_type="application/json",
                    overwrite=True,
                )
            except Exception:
                app.logger.exception(
                    "No se pudo archivar el certificado en Blob"
                )

        return jsonify(
            {
                "ok": True,
                "certificate_id": cert.certificate_id,
                "verification_url": (
                    f"/verificar/{cert.certificate_id}"
                ),
                "certificate": cert.to_dict(),
            }
        ), 201

    @app.get("/verificar/<certificate_id>")
    def verify_certificate(certificate_id: str):
        engine = CertificateEngine(certificates_root())
        record = _load_issued_by_id(engine, certificate_id)

        valid = bool(
            record
            and record.get("certificate_id") == certificate_id
        )

        return render_template(
            "verify.html",
            valid=valid,
            record=record if valid else None,
            certificate_id=certificate_id,
        )

    @app.get("/api/verify/<certificate_id>")
    def verify_certificate_api(certificate_id: str):
        engine = CertificateEngine(certificates_root())
        record = _load_issued_by_id(engine, certificate_id)
        valid = bool(
            record
            and record.get("certificate_id") == certificate_id
        )

        return jsonify(
            {
                "ok": True,
                "valid": valid,
                "certificate": record if valid else None,
            }
        )

    @app.get("/certificado")
    def certificate_page():
        if not _cert_allowed(request):
            return render_template(
                "gated.html",
                target=request.path,
            ), 403

        course_data = course()
        snapshot_cert = api_snapshot()["certificate"] or {}
        return render_template(
            "certificate.html",
            learner=(
                course_data.get(
                    "learner",
                    "Aprendiz VIDA",
                )
                or "Aprendiz VIDA"
            ),
            dedication=course_data.get(
                "dedication",
                "Dedicatoria del aprendiz.",
            ),
            course=course_data.get(
                "title",
                "Curso SENA",
            ),
            provider=course_data.get("provider", "SENA"),
            hours=course_data.get("hours", 48),
            platform=course_data.get("platform", "Zajuna"),
            source=course_data.get("source", ""),
            cert=snapshot_cert,
        )

    @app.get("/mi-certificado")
    def my_certificate_page():
        engine = CertificateEngine(certificates_root())
        profile = ProfileEngine(profile_path()).load()
        cert = _load_issued(
            engine,
            profile.course_id,
            str(current_user_id()),
        )

        if not cert or not cert.get("certificate_id"):
            return render_template(
                "gated.html",
                target="/mi-certificado",
            ), 404

        course_data = course()
        return render_template(
            "certificate.html",
            learner=(
                cert.get("learner")
                or course_data.get(
                    "learner",
                    "Aprendiz VIDA",
                )
                or "Aprendiz VIDA"
            ),
            cedula=cert.get("cedula") or "",
            dedication=course_data.get(
                "dedication",
                "Dedicatoria del aprendiz.",
            ),
            course=course_data.get(
                "title",
                "Curso SENA",
            ),
            provider=course_data.get("provider", "SENA"),
            hours=course_data.get("hours", 48),
            platform=course_data.get("platform", "Zajuna"),
            source=course_data.get("source", ""),
            cert=cert,
        )

    @app.get("/api/progress/<vid>")
    def get_video_progress(vid: str):
        cid = active_course_id()
        connection = conn()

        uid = current_user_id()

        row = connection.execute(
            """
            SELECT *
            FROM video_progress
            WHERE user_id = ? AND video_id = ? AND course_id = ?
            """,
            (uid, vid, cid),
        ).fetchone()

        connection.close()

        if row:
            return jsonify(dict(row))

        return jsonify(
            {
                "video_id": vid,
                "course_id": cid,
                "position": 0,
                "duration": 0,
                "completed": 0,
            }
        )

    @app.post("/api/progress/<vid>")
    def set_video_progress(vid: str):
        payload = request.get_json(silent=True) or {}

        try:
            position = float(payload.get("position", 0))
            duration = float(payload.get("duration", 0))
        except (TypeError, ValueError):
            return jsonify(
                {
                    "ok": False,
                    "error": "position o duration inválidos",
                }
            ), 400

        completed = int(bool(payload.get("completed", False)))

        connection = conn()
        cid = active_course_id()
        uid = current_user_id()

        try:
            connection.execute(
                """
                INSERT INTO video_progress (
                    user_id,
                    video_id,
                    course_id,
                    position,
                    duration,
                    completed
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, video_id, course_id)
                DO UPDATE SET
                    position = excluded.position,
                    duration = excluded.duration,
                    completed = excluded.completed,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    uid,
                    vid,
                    cid,
                    position,
                    duration,
                    completed,
                ),
            )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return jsonify(
            {
                "ok": True,
                "video_id": vid,
                "course_id": cid,
                "position": position,
                "duration": duration,
                "completed": completed,
            }
        )


    @app.post("/api/item/<item_id>")
    def set_item(item_id: str):
        payload = request.get_json(silent=True) or {}

        completed = int(
            bool(payload.get("completed", False))
        )

        connection = conn()
        cid = active_course_id()
        uid = current_user_id()

        connection.execute(
            """
            INSERT INTO item_progress (
                user_id,
                item_id,
                course_id,
                completed
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(user_id, item_id, course_id)
            DO UPDATE SET
                completed = excluded.completed,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                uid,
                item_id,
                cid,
                completed,
            ),
        )

        connection.commit()
        connection.close()

        return jsonify(
            {
                "ok": True,
                "item_id": item_id,
                "course_id": cid,
                "completed": completed,
            }
        )

    @app.post("/api/concept/<concept_id>/study")
    def concept_study(concept_id: str):
        """Registra estudio explícito de un concepto existente."""
        course_data = course()
        concept = next(
            (
                c for c in course_data.get("concepts", [])
                if str(c.get("id")) == str(concept_id)
            ),
            None,
        )

        if concept is None:
            return jsonify({
                "ok": False,
                "error": "Concepto no encontrado.",
            }), 404

        payload = request.get_json(silent=True) or {}

        try:
            minutes = float(payload.get("minutes", 1))
        except (TypeError, ValueError):
            return jsonify({
                "ok": False,
                "error": "minutes inválidos",
            }), 400

        if minutes <= 0 or minutes > 120:
            return jsonify({
                "ok": False,
                "error": "minutes inválidos",
            }), 400

        connection = conn()
        cid = active_course_id()
        uid = current_user_id()

        connection.execute(
            """
            INSERT INTO study_log (
                user_id,
                course_id,
                kind,
                ref_id,
                minutes,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                cid,
                "concept",
                str(concept_id),
                minutes,
                f"Estudio del concepto: {concept.get('title', concept_id)}",
            ),
        )

        connection.commit()
        connection.close()

        return jsonify({
            "ok": True,
            "concept_id": str(concept_id),
            "minutes": minutes,
        })


    
    @app.get("/api/concept/<concept_id>/check")
    def get_knowledge_check(concept_id: str):
        """
        Devuelve el Knowledge Check público de un concepto.

        Las respuestas correctas permanecen exclusivamente en backend.
        """
        course_data = course()

        concept = next(
            (
                c
                for c in course_data.get("concepts", [])
                if str(c.get("id")) == str(concept_id)
            ),
            None,
        )

        if concept is None:
            return jsonify({
                "ok": False,
                "error": "Concepto no encontrado.",
            }), 404

        check = public_knowledge_check(concept_id)

        if check is None:
            return jsonify({
                "ok": False,
                "error": "Este concepto todavía no tiene Knowledge Check.",
                "concept_id": str(concept_id),
            }), 404

        return jsonify({
            "ok": True,
            "concept_id": str(concept_id),
            "check": check,
        })


    @app.post("/api/concept/<concept_id>/check")
    def submit_knowledge_check(concept_id: str):
        """
        Corrige el Knowledge Check exclusivamente en backend.

        El navegador envía únicamente los índices seleccionados.
        El servidor determina las respuestas correctas.
        """
        course_data = course()

        concept = next(
            (
                c
                for c in course_data.get("concepts", [])
                if str(c.get("id")) == str(concept_id)
            ),
            None,
        )

        if concept is None:
            return jsonify({
                "ok": False,
                "error": "Concepto no encontrado.",
            }), 404

        definition = knowledge_check_definition(concept_id)

        if definition is None:
            return jsonify({
                "ok": False,
                "error": "Este concepto todavía no tiene Knowledge Check.",
                "concept_id": str(concept_id),
            }), 404

        payload = request.get_json(silent=True) or {}
        answers = payload.get("answers")

        if not isinstance(answers, dict):
            return jsonify({
                "ok": False,
                "error": "answers debe ser un objeto.",
            }), 400

        questions = definition["questions"]

        expected_ids = {str(q["id"]) for q in questions}
        received_ids = {str(k) for k in answers.keys()}

        missing = sorted(expected_ids - received_ids)
        unknown = sorted(received_ids - expected_ids)

        if missing:
            return jsonify({
                "ok": False,
                "error": "Faltan respuestas.",
                "missing": missing,
            }), 400

        if unknown:
            return jsonify({
                "ok": False,
                "error": "Se recibieron preguntas no válidas.",
                "unknown": unknown,
            }), 400

        correct_count = 0
        results = []

        for question in questions:
            question_id = str(question["id"])
            selected = answers.get(question_id)

            try:
                selected_index = int(selected)
            except (TypeError, ValueError):
                return jsonify({
                    "ok": False,
                    "error": f"Respuesta inválida para {question_id}.",
                }), 400

            valid_range = range(len(question["options"]))

            if selected_index not in valid_range:
                return jsonify({
                    "ok": False,
                    "error": f"Opción inválida para {question_id}.",
                }), 400

            is_correct = selected_index == int(question["correct"])

            if is_correct:
                correct_count += 1

            results.append({
                "id": question_id,
                "correct": is_correct,
            })

        total = len(questions)
        score = correct_count / total if total else 0.0
        required_score = float(definition["required_score"])
        passed = score >= required_score

        connection = conn()
        cid = active_course_id()
        uid = current_user_id()

        knowledge_item_id = f"knowledge:{concept_id}"

        if passed:
            connection.execute(
                """
                INSERT INTO item_progress (
                    user_id,
                    item_id,
                    course_id,
                    completed
                )
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, item_id, course_id)
                DO UPDATE SET
                    completed = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    uid,
                    knowledge_item_id,
                    cid,
                ),
            )

            connection.commit()

        connection.close()

        return jsonify({
            "ok": True,
            "concept_id": str(concept_id),
            "version": definition["version"],
            "score": round(score, 4),
            "correct": correct_count,
            "total": total,
            "required_score": required_score,
            "passed": passed,
            "results": results,
        })


    @app.post("/api/concept/<concept_id>/verify")
    def verify_concept(concept_id: str):
        """
        Verificación final de un concepto.

        Flujo obligatorio:

        estudio → Knowledge Check aprobado → concepto verificado
        """
        course_data = course()

        concept = next(
            (
                c for c in course_data.get("concepts", [])
                if str(c.get("id")) == str(concept_id)
            ),
            None,
        )

        if concept is None:
            return jsonify({
                "ok": False,
                "error": "Concepto no encontrado.",
            }), 404

        connection = conn()
        cid = active_course_id()
        uid = current_user_id()

        # ---------------------------------------------------------------
        # 1. Debe existir estudio registrado.
        # ---------------------------------------------------------------
        study_row = connection.execute(
            """
            SELECT COALESCE(SUM(minutes), 0) AS minutes
            FROM study_log
            WHERE user_id = ?
              AND course_id = ?
              AND kind = 'concept'
              AND ref_id = ?
            """,
            (uid, cid, str(concept_id)),
        ).fetchone()

        studied_minutes = float(study_row["minutes"] or 0)

        if studied_minutes <= 0:
            connection.close()
            return jsonify({
                "ok": False,
                "error": "Primero registra estudio del concepto.",
                "concept_id": str(concept_id),
                "studied_minutes": studied_minutes,
            }), 409

        # ---------------------------------------------------------------
        # 2. Debe existir Knowledge Check aprobado.
        # ---------------------------------------------------------------
        knowledge_item_id = f"knowledge:{concept_id}"

        knowledge_row = connection.execute(
            """
            SELECT completed
            FROM item_progress
            WHERE user_id = ?
              AND item_id = ?
              AND course_id = ?
            """,
            (uid, knowledge_item_id, cid),
        ).fetchone()

        knowledge_passed = bool(
            knowledge_row
            and int(knowledge_row["completed"] or 0) == 1
        )

        if not knowledge_passed:
            connection.close()
            return jsonify({
                "ok": False,
                "error": "Primero aprueba el Knowledge Check del concepto.",
                "concept_id": str(concept_id),
                "knowledge_check_passed": False,
                "studied_minutes": studied_minutes,
            }), 409

        # ---------------------------------------------------------------
        # 3. Crear la verificación final del concepto.
        # ---------------------------------------------------------------
        item_id = f"concept:{concept_id}"

        connection.execute(
            """
            INSERT INTO item_progress (
                user_id,
                item_id,
                course_id,
                completed
            )
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, item_id, course_id)
            DO UPDATE SET
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (uid, item_id, cid),
        )

        connection.commit()
        connection.close()

        return jsonify({
            "ok": True,
            "concept_id": str(concept_id),
            "item_id": item_id,
            "verified": True,
            "knowledge_check_passed": True,
            "studied_minutes": studied_minutes,
        })


    @app.post("/api/study")
    def study():
        payload = request.get_json(silent=True) or {}

        try:
            minutes = float(payload.get("minutes", 0))
        except (TypeError, ValueError):
            return jsonify(
                {
                    "ok": False,
                    "error": "minutes inválidos",
                }
            ), 400

        kind = str(
            payload.get("kind", "study")
        )

        ref_id = str(
            payload.get("ref_id", "")
        )

        note = str(
            payload.get("note", "")
        )

        if minutes <= 0 or minutes > 1440:
            return jsonify(
                {
                    "ok": False,
                    "error": "minutes inválidos",
                }
            ), 400

        connection = conn()
        cid = active_course_id()
        uid = current_user_id()

        connection.execute(
            """
            INSERT INTO study_log (
                user_id,
                course_id,
                kind,
                ref_id,
                minutes,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                cid,
                kind,
                ref_id,
                minutes,
                note,
            ),
        )

        connection.commit()
        connection.close()

        return jsonify({"ok": True})

    @app.get("/api/activity/<activity_id>")
    def activity_detail(activity_id: str):
        course_data = course()

        item = next(
            (
                item
                for item in course_data.get("items", [])
                if item.get("id") == activity_id
            ),
            None,
        )

        if item is None:
            return jsonify(
                {"ok": False, "error": "Actividad no encontrada."}
            ), 404

        conn_activity = conn()
        uid = current_user_id()
        cid = active_course_id()

        row = conn_activity.execute(
            """
            SELECT completed FROM item_progress
            WHERE user_id = ? AND item_id = ? AND course_id = ?
            """,
            (uid, activity_id, cid),
        ).fetchone()

        video_row = conn_activity.execute(
            """
            SELECT position, duration, completed
            FROM video_progress
            WHERE user_id = ? AND video_id = ? AND course_id = ?
            """,
            (uid, f"video:{activity_id}", cid),
        ).fetchone()

        conn_activity.close()

        evidence_records = _evidence_for(activity_id)
        uploaded_files = _uploaded_files(activity_id)

        video_ref = str(item.get("video", "") or "")
        video_available, video_size = _resolve_video_file(video_ref)

        return jsonify(
            {
                **item,
                "completed": bool(
                    row["completed"] if row else False
                ),
                "video_available": video_available,
                "video_bytes": video_size,
                "video_progress": {
                    "position": (
                        video_row["position"]
                        if video_row
                        else 0
                    ),
                    "duration": (
                        video_row["duration"]
                        if video_row
                        else 0
                    ),
                    "completed": bool(
                        video_row["completed"]
                        if video_row
                        else False
                    ),
                },
                "evidence_count": len(evidence_records),
                "evidence_files": uploaded_files,
            }
        )

    @app.get("/api/activities")
    def activities_list():
        course_data = course()
        connection = conn()
        uid = current_user_id()
        cid = active_course_id()

        rows = {
            row["item_id"]: row["completed"]
            for row in connection.execute(
                """
                SELECT item_id, completed
                FROM item_progress
                WHERE user_id = ? AND course_id = ?
                """,
                (uid, cid),
            ).fetchall()
        }

        connection.close()

        result = []
        for item in course_data.get("items", []):
            if item.get("kind") != "activity":
                continue
            activity_id = item["id"]
            result.append(
                {
                    "id": activity_id,
                    "title": item.get("title", activity_id),
                    "due": item.get("due", ""),
                    "completed": bool(rows.get(activity_id)),
                    "evidence_count": len(
                        _evidence_for(activity_id)
                    ),
                }
            )

        return jsonify(result)


    # === VIDA VERCEL BLOB EVIDENCE PATCH ===
    def _vercel_blob_enabled() -> bool:
        """Activa Blob cuando Vercel proporciona su token."""
        return bool(os.getenv("BLOB_READ_WRITE_TOKEN"))


    def _vercel_blob_client():
        """Carga el SDK solo cuando Blob está habilitado."""
        from vercel.blob import BlobClient
        return BlobClient()


    def _vercel_blob_prefix(activity_id: str) -> str:
        """Aísla evidencias por usuario, curso y actividad."""
        uid = str(current_user_id())
        cid = str(active_course_id())
        return f"vida/evidence/{uid}/{cid}/{activity_id}/"


    def _vercel_blob_read(pathname: str) -> bytes:
        client = _vercel_blob_client()
        result = client.get(pathname, access="private")

        if (
            result is None
            or result.status_code != 200
        ):
            raise FileNotFoundError(pathname)

        body = _blob_body(result)
        if body is None:
            raise FileNotFoundError(pathname)

        return body


    def _vercel_blob_list(activity_id: str) -> list:
        client = _vercel_blob_client()
        prefix = _vercel_blob_prefix(activity_id)

        blobs = []
        cursor = None

        while True:
            page = client.list_objects(
                prefix=prefix,
                limit=1000,
                cursor=cursor,
            )

            blobs.extend(page.blobs)

            if not page.has_more:
                break

            cursor = page.cursor

        return blobs


    def _vercel_blob_records(activity_id: str) -> list[dict]:
        records = []

        for blob in _vercel_blob_list(activity_id):
            pathname = blob.pathname

            if not pathname.endswith(".json"):
                continue

            try:
                payload = json.loads(
                    _vercel_blob_read(pathname).decode("utf-8")
                )
            except (
                OSError,
                ValueError,
                UnicodeDecodeError,
            ):
                continue

            if isinstance(payload, dict):
                records.append(payload)

        records.sort(
            key=lambda item: item.get("observed_at", "")
        )

        return records


    def _vercel_blob_records_recover(activity_id: str) -> list[dict]:
        """
        Recupera evidencias históricas aunque hayan quedado bajo
        un prefijo de usuario distinto. La identidad se valida
        contra el contexto almacenado dentro del registro JSON.
        """
        records = []
        uid = str(current_user_id())
        cid = str(active_course_id())

        client = _vercel_blob_client()
        prefix = "vida/evidence/"
        cursor = None

        while True:
            page = client.list_objects(
                prefix=prefix,
                limit=1000,
                cursor=cursor,
            )

            for blob in page.blobs:
                pathname = blob.pathname

                if not pathname.endswith(".json"):
                    continue

                try:
                    payload = json.loads(
                        _vercel_blob_read(pathname).decode("utf-8")
                    )
                except (
                    OSError,
                    ValueError,
                    UnicodeDecodeError,
                ):
                    continue

                if not isinstance(payload, dict):
                    continue

                context = payload.get("context") or {}

                if (
                    str(context.get("user_id", "")) == uid
                    and str(context.get("course_id", "")) == cid
                    and str(context.get("activity_id", "")) == str(activity_id)
                ):
                    records.append(payload)

            if not page.has_more:
                break

            cursor = page.cursor

        records.sort(
            key=lambda item: item.get("observed_at", "")
        )

        return records


    def _vercel_blob_files(activity_id: str) -> list[dict]:
        files = []

        for blob in _vercel_blob_list(activity_id):
            pathname = blob.pathname

            if pathname.endswith(".json"):
                continue

            name = pathname.rsplit("/", 1)[-1]

            files.append(
                {
                    "name": name,
                    "size": int(blob.size or 0),
                    "url": (
                        f"/media/evidence/"
                        f"{activity_id}/{name}"
                    ),
                }
            )

        files.sort(
            key=lambda item: item["name"]
        )

        return files


    def _vercel_blob_store_evidence(
        activity_id: str,
        stored_name: str,
        body: bytes,
        content_type: str | None,
        record: dict,
    ) -> None:
        client = _vercel_blob_client()
        prefix = _vercel_blob_prefix(activity_id)

        client.put(
            prefix + stored_name,
            body,
            access="private",
            content_type=(
                content_type
                or "application/octet-stream"
            ),
            add_random_suffix=False,
        )

        client.put(
            prefix + str(record["evidence_id"]) + ".json",
            json.dumps(
                record,
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8"),
            access="private",
            content_type="application/json",
            add_random_suffix=False,
        )

    # === FIN VIDA VERCEL BLOB EVIDENCE PATCH ===

    @app.get("/api/evidence")
    def evidence_overview():
        course_data = course()
        result = []

        for item in course_data.get("items", []):
            if item.get("kind") != "activity":
                continue

            activity_id = item["id"]

            try:
                if _vercel_blob_enabled():
                    records = _vercel_blob_records(activity_id)

                    # Recuperación de evidencias históricas:
                    # si no aparecen bajo el prefijo actual,
                    # buscar los JSON existentes y validar su
                    # identidad desde context.user_id/course_id.
                    if not records:
                        records = _vercel_blob_records_recover(
                            activity_id
                        )

                    files = _vercel_blob_files(activity_id)

                    # Si los archivos están bajo un prefijo histórico,
                    # reconstruirlos desde los registros recuperados.
                    if records:
                        files = []
                        for record in records:
                            context = record.get("context") or {}
                            name = context.get("file")
                            if not name:
                                continue

                            files.append(
                                {
                                    "name": str(name),
                                    "size": int(context.get("size") or 0),
                                    "url": (
                                        f"/media/evidence/"
                                        f"{activity_id}/{name}"
                                    ),
                                }
                            )
                else:
                    records = _evidence_for(activity_id)
                    files = _uploaded_files(activity_id)
            except Exception as exc:
                app.logger.exception(
                    "Error leyendo evidencia activity=%s: %s",
                    activity_id,
                    exc,
                )
                records = []
                files = []

            result.append(
                {
                    "activity_id": activity_id,
                    "title": item.get(
                        "title",
                        activity_id,
                    ),
                    "records": records,
                    "files": files,
                }
            )

        return jsonify(result)

    @app.post("/api/evidence/<activity_id>")
    def upload_evidence(activity_id: str):
        from werkzeug.utils import secure_filename

        if "file" not in request.files:
            return jsonify(
                {
                    "ok": False,
                    "error": "No se recibió archivo.",
                }
            ), 400

        upload = request.files["file"]

        if not upload or not upload.filename:
            return jsonify(
                {
                    "ok": False,
                    "error": "Archivo vacío.",
                }
            ), 400

        safe = secure_filename(
            upload.filename
        ).lower()

        allowed = {
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "gif",
            "webp",
            "xlsx",
            "xls",
            "doc",
            "docx",
            "ppt",
            "pptx",
            "txt",
            "zip",
        }

        if (
            "." not in safe
            or safe.rsplit(".", 1)[1] not in allowed
        ):
            return jsonify(
                {
                    "ok": False,
                    "error": "Formato no permitido.",
                }
            ), 400

        stamp = datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        stored_name = (
            f"{stamp}_{safe}"
        )

        if _vercel_blob_enabled():
            try:
                body = upload.read()

                if not body:
                    return jsonify(
                        {
                            "ok": False,
                            "error": "Archivo vacío.",
                        }
                    ), 400

                from vida_engines import EvidenceEngine

                evidence = EvidenceEngine(
                    evidence_root()
                    / "evidence.json"
                )

                record = evidence.record(
                    source=(
                        f"work/{activity_id}"
                    ),
                    method="evidence_upload",
                    event_type=(
                        "ACTIVITY_COMPLETE"
                    ),
                    result="DELIVERED",
                    context={
                        "activity_id": activity_id,
                        "user_id": (
                            current_user_id()
                        ),
                        "course_id": (
                            active_course_id()
                        ),
                        "file": stored_name,
                        "size": len(body),
                        "note": str(
                            request.form.get(
                                "note",
                                "",
                            )
                        ),
                    },
                )

                _vercel_blob_store_evidence(
                    activity_id=activity_id,
                    stored_name=stored_name,
                    body=body,
                    content_type=upload.mimetype,
                    record=record.to_dict(),
                )

            except Exception as exc:
                app.logger.exception(
                    "Error guardando evidencia "
                    "en Vercel Blob"
                )

                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "No se pudo guardar "
                            "la evidencia en Blob: "
                            f"{exc}"
                        ),
                    }
                ), 503

            try:
                connection = conn()
                cid = active_course_id()
                uid = current_user_id()

                connection.execute(
                    """
                    INSERT INTO item_progress
                        (
                            user_id,
                            item_id,
                            course_id,
                            completed
                        )
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(
                        user_id,
                        item_id,
                        course_id
                    )
                    DO UPDATE SET
                        completed = 1,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        uid,
                        activity_id,
                        cid,
                    ),
                )

                connection.commit()
                connection.close()

            except Exception:
                app.logger.exception(
                    "No se pudo actualizar "
                    "item_progress"
                )

            return jsonify(
                {
                    "ok": True,
                    "evidence_id": (
                        record.evidence_id
                    ),
                    "file": stored_name,
                    "url": (
                        f"/media/evidence/"
                        f"{activity_id}/"
                        f"{stored_name}"
                    ),
                    "storage": "vercel_blob",
                }
            ), 201

        # ============================
        # MODO LOCAL
        # ============================

        evidence_dir = (
            evidence_root()
            / activity_id
        )

        try:
            evidence_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

        except OSError:
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "No se pudo escribir "
                        "en el almacén de "
                        "evidencias de este "
                        "despliegue."
                    ),
                }
            ), 503

        path = (
            evidence_dir
            / stored_name
        )

        try:
            upload.save(path)

        except OSError:
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "No se pudo guardar "
                        "la evidencia en este "
                        "despliegue."
                    ),
                }
            ), 503

        from vida_engines import EvidenceEngine

        evidence = EvidenceEngine(
            evidence_root()
            / "evidence.json"
        )

        record = evidence.record(
            source=(
                f"work/{activity_id}"
            ),
            method="evidence_upload",
            event_type=(
                "ACTIVITY_COMPLETE"
            ),
            result="DELIVERED",
            context={
                "activity_id": activity_id,
                "user_id": (
                    current_user_id()
                ),
                "course_id": (
                    active_course_id()
                ),
                "file": stored_name,
                "size": path.stat().st_size,
                "note": str(
                    request.form.get(
                        "note",
                        "",
                    )
                ),
            },
        )

        connection = conn()
        cid = active_course_id()
        uid = current_user_id()

        connection.execute(
            """
            INSERT INTO item_progress
                (
                    user_id,
                    item_id,
                    course_id,
                    completed
                )
            VALUES (?, ?, ?, 1)
            ON CONFLICT(
                user_id,
                item_id,
                course_id
            )
            DO UPDATE SET
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                uid,
                activity_id,
                cid,
            ),
        )

        connection.commit()
        connection.close()

        return jsonify(
            {
                "ok": True,
                "evidence_id": (
                    record.evidence_id
                ),
                "file": stored_name,
                "url": (
                    f"/media/evidence/"
                    f"{activity_id}/"
                    f"{stored_name}"
                ),
                "storage": "filesystem",
            }
        ), 201

    def _vercel_blob_find_file(
        activity_id: str,
        name: str,
    ):
        """Busca el archivo actual o uno histórico del usuario."""
        client = _vercel_blob_client()

        current_path = (
            _vercel_blob_prefix(activity_id)
            + name
        )

        try:
            result = client.get(
                current_path,
                access="private",
            )
            if (
                result is not None
                and result.status_code == 200
                and _blob_body(result) is not None
            ):
                return result
        except Exception:
            pass

        uid = str(current_user_id())
        cid = str(active_course_id())
        cursor = None

        while True:
            page = client.list_objects(
                prefix="vida/evidence/",
                limit=1000,
                cursor=cursor,
            )

            for blob in page.blobs:
                pathname = blob.pathname

                if not pathname.endswith(".json"):
                    continue

                try:
                    payload = json.loads(
                        _vercel_blob_read(pathname).decode("utf-8")
                    )
                except (
                    OSError,
                    ValueError,
                    UnicodeDecodeError,
                ):
                    continue

                if not isinstance(payload, dict):
                    continue

                context = payload.get("context") or {}

                if (
                    str(context.get("user_id", "")) != uid
                    or str(context.get("course_id", "")) != cid
                    or str(context.get("activity_id", "")) != str(activity_id)
                    or str(context.get("file", "")) != str(name)
                ):
                    continue

                historical_path = (
                    pathname.rsplit("/", 1)[0]
                    + "/"
                    + name
                )

                try:
                    result = client.get(
                        historical_path,
                        access="private",
                    )
                    if (
                        result is not None
                        and result.status_code == 200
                        and _blob_body(result) is not None
                    ):
                        return result
                except Exception:
                    continue

            if not page.has_more:
                break

            cursor = page.cursor

        return None


    @app.get("/media/evidence/<activity_id>/<path:name>")
    def media_evidence(
        activity_id: str,
        name: str,
    ):
        if _vercel_blob_enabled():
            try:
                result = _vercel_blob_find_file(
                    activity_id,
                    name,
                )

            except Exception:
                app.logger.exception(
                    "Error leyendo evidencia "
                    "desde Vercel Blob"
                )

                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "No se pudo leer "
                            "la evidencia."
                        ),
                    }
                ), 503

            if (
                result is None
                or result.status_code != 200
            ):
                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "Evidencia no encontrada."
                        ),
                    }
                ), 404

            body = _blob_body(result)

            if body is None:
                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "Evidencia no encontrada."
                        ),
                    }
                ), 404

            headers = {
                "Cache-Control": (
                    "private, no-store"
                )
            }

            if result.blob.content_type:
                headers["Content-Type"] = (
                    result.blob.content_type
                )

            return Response(
                body,
                headers=headers,
            )

        return send_from_directory(
            evidence_root()
            / activity_id,
            name,
            as_attachment=False,
        )

    @app.get("/media/materials/<path:name>")
    def media_material(name: str):
        return send_from_directory(
            MEDIA / "materials",
            name,
        )

    @app.get("/media/videos/<path:name>")
    def media_video(name: str):
        return send_from_directory(
            MEDIA / "videos",
            name,
            conditional=True,
        )

    return app


def tui() -> None:
    snapshot = api_snapshot()
    current_course = course()

    console.print(
        Panel.fit(
            (
                "[bold cyan]🧠 VIDA · LEARNING STUDIO[/bold cyan]\n"
                f"[white]{current_course['provider']} · "
                f"{current_course['title']}[/white]\n\n"
                f"[green]Progreso operativo[/green] "
                f"{snapshot['overall']}%    "
                f"[blue]Dominio[/blue] "
                f"{snapshot['mastery']}%    "
                f"[cyan]🎬 Videos[/cyan] "
                f"{snapshot['completed_videos']}/"
                f"{snapshot['video_count']}    "
                f"[yellow]📝 Actividades[/yellow] "
                f"{snapshot['completed_activities']}/"
                f"{snapshot['activity_count']}\n"
                f"[magenta]⏱ Estudio registrado[/magenta] "
                f"{snapshot['study_minutes']} min    "
                f"[bold green]💡 Learning Score[/bold green] "
                f"{snapshot['learning_score']}%"
            ),
            title="BLUMIX · VIDA",
        )
    )

    table = Table()
    table.add_column("Estado")
    table.add_column("Actividad")
    table.add_column("Fecha")

    connection = conn()

    progress_map = {
        row["item_id"]: row["completed"]
        for row in connection.execute(
            """
            SELECT item_id, completed
            FROM item_progress
            """
        ).fetchall()
    }

    connection.close()

    for item in current_course.get("items", []):
        table.add_row(
            "✅" if progress_map.get(item["id"]) else "○",
            item["title"],
            item.get("due", "—"),
        )

    console.print(table)

    console.print(
        "\n[dim]Comandos: "
        "vida web · vida tui · vida init[/dim]"
    )


def init() -> None:
    ensure_dirs()
    connection = conn()
    connection.close()

    (MEDIA / "videos" / ".gitkeep").touch()

    console.print(
        "[bold green]✅ VIDA inicializada.[/bold green]"
    )


def seed() -> None:
    ensure_dirs()

    course_data = course()

    video_ids = [
        str(video["id"])
        for video in course_data.get("videos", [])
    ]
    activity_ids = [
        str(item["id"])
        for item in course_data.get("items", [])
        if item.get("kind") == "activity"
    ]
    concept_ids = [
        str(concept["id"])
        for concept in course_data.get("concepts", [])
    ]

    connection = conn()
    cid = active_course_id()
    uid = current_user_id()

    for video_id in video_ids:
        connection.execute(
            """
            INSERT INTO video_progress (
                user_id, video_id, course_id, position, duration, completed
            )
            VALUES (?, ?, ?, 1, 1, 1)
            ON CONFLICT(user_id, video_id, course_id) DO UPDATE SET
                position = 1,
                duration = 1,
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (uid, video_id, cid),
        )

    for activity_id in activity_ids + [
        f"concept:{concept_id}"
        for concept_id in concept_ids
    ]:
        connection.execute(
            """
            INSERT INTO item_progress (
                user_id, item_id, course_id, completed
            )
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, item_id, course_id) DO UPDATE SET
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (uid, activity_id, cid),
        )

    connection.commit()
    connection.close()

    from vida_engines import EventEngine, EvidenceEngine

    events = EventEngine(DATA / "events" / "events.json")
    evidence = EvidenceEngine(DATA / "evidence" / "evidence.json")

    for activity_id, title in [
        (item["id"], item.get("title", item["id"]))
        for item in course_data.get("items", [])
        if item.get("kind") == "activity"
    ]:
        events.record(
            "ACTIVITY_COMPLETE",
            source=f"work/{activity_id}",
            subject=str(
                course_data.get("learner", "aprendiz")
            ),
            data={"title": title},
        )
        evidence.record(
            source=f"work/{activity_id}",
            method="submission_confirmed",
            event_type="ACTIVITY_COMPLETE",
            result="DELIVERED",
            context={"title": title},
        )

    for video in course_data.get("videos", []):
        events.record(
            "VIDEO_COMPLETE",
            source=f"media/{video['id']}",
            subject=str(
                course_data.get("learner", "aprendiz")
            ),
            data={"title": video.get("title", video["id"])},
        )
        evidence.record(
            source=f"media/{video['id']}",
            method="playback_complete",
            event_type="VIDEO_COMPLETE",
            result="VERIFIED_VIDEO",
            context={
                "title": video.get("title", video["id"]),
            },
        )

    for concept in course_data.get("concepts", []):
        evidence.record(
            source=f"knowledge/{concept['id']}",
            method="explicit_verification",
            event_type="CONCEPT_VERIFY",
            result="VERIFIED_MASTERY",
            context={"title": concept.get("title", concept["id"])},
        )

    console.print(
        "[bold green]✅ Trabajos registrados: "
        f"{len(activity_ids)} actividades, "
        f"{len(video_ids)} videos, "
        f"{len(concept_ids)} conceptos (evidencia en data/evidence).[/bold green]"
    )


def issue_certificate() -> None:
    ensure_dirs()

    course_data = course()
    profile = ProfileEngine(profile_path()).load()
    state = api_snapshot()

    required_videos = len(course_data.get("videos", []))
    required_activities = len(
        [
            item
            for item in course_data.get("items", [])
            if item.get("kind") == "activity"
        ]
    )
    required_concepts = len(course_data.get("concepts", []))

    engine = CertificateEngine(certificates_root())

    try:
        cert = engine.issue_once(
            course_id=profile.course_id,
            learner=str(
                course_data.get("learner", "Aprendiz VIDA")
            ),
            course=str(
                course_data.get("title", "Curso SENA")
            ),
            operational=state["operational"],
            mastery=state["mastery"],
            evidence_count=state["evidence_count"],
            required_videos=required_videos,
            completed_videos=state["completed_videos"],
            required_activities=required_activities,
            completed_activities=state["completed_activities"],
            required_concepts=required_concepts,
            verified_concepts=state["verified_concepts"],
            unknown_count=state["unknown_count"],
            user_confirmation=True,
        )
    except CertificateAlreadyIssued as exc:
        console.print(f"[yellow]⚠️ Certificado ya emitido:[/yellow] {exc}")
        return
    except CertificateNotEligible as exc:
        console.print(f"[red]❌ No elegible:[/red] {exc}")
        console.print("[dim]Registra los trabajos con 'vida seed'.[/dim]")
        return

    console.print(
        Panel.fit(
            (
                f"[bold yellow]🏆 Certificado emitido:[/bold yellow]\n"
                f"[white]{cert.certificate_id}[/white]\n"
                f"[cyan]Verificación web:[/cyan] "
                f"http://127.0.0.1:8787/verificar/{cert.certificate_id}"
            ),
            title="VIDA · CERTIFICADO",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vida"
    )

    parser.add_argument(
        "cmd",
        choices=[
            "init",
            "seed",
            "cert",
            "web",
            "tui",
        ],
        nargs="?",
        default="tui",
    )

    args = parser.parse_args()

    if args.cmd == "init":
        init()
        return

    if args.cmd == "seed":
        seed()
        return

    if args.cmd == "cert":
        issue_certificate()
        return

    if args.cmd == "tui":
        tui()
        return

    app = create_app()

    console.print(
        Panel(
            (
                "[bold cyan]🧠 VIDA[/bold cyan]\n"
                "http://127.0.0.1:8787\n\n"
                "[green]Servidor local activo[/green]"
            ),
            title="VIDA · LOCAL",
        )
    )

    webbrowser.open(
        "http://127.0.0.1:8787"
    )

    app.run(
        host="127.0.0.1",
        port=8787,
        debug=False,
    )


if __name__ == "__main__":
    main()

