#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import sqlite3
import tempfile
import webbrowser
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from secrets import compare_digest

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
)
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import vida_store

from vida_engines import (
    accounts,
    CourseEngine,
    ProgressEngine,
    IntelligenceEngine,
    ProfileEngine,
    CertificateEngine,
    CertificateNotEligible,
    CertificateAlreadyIssued,
)

ROOT = Path(__file__).resolve().parent
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


_RESTORED_PG = False


def conn() -> sqlite3.Connection:
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
        """
    )

    _migrate_existing_db(connection)

    connection.commit()

    global _RESTORED_PG
    if vida_store.enabled() and not _RESTORED_PG:
        vida_store.restore(connection)
        _RESTORED_PG = True

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


def engine_state(course_id: str | None = None) -> dict:
    cid = course_id or active_course_id()
    connection = conn()

    items = connection.execute(
        "SELECT item_id, completed, course_id FROM item_progress "
        "WHERE course_id = ?",
        (cid,),
    ).fetchall()

    videos = connection.execute(
        """
        SELECT video_id, position, duration, completed
        FROM video_progress
        WHERE course_id = ?
        """,
        (cid,),
    ).fetchall()

    log = connection.execute(
        "SELECT COALESCE(SUM(minutes), 0) AS minutes FROM study_log "
        "WHERE course_id = ?",
        (cid,),
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
    }


def _evidence_count() -> int:
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
            total += len(data)
    return total


def _evidence_for(activity_id: str) -> list[dict]:
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
        if record.get("context", {}).get("activity_id")
        == activity_id
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


def _load_issued(certificate_engine: CertificateEngine, course_id: str) -> dict | None:
    record = certificate_engine._course_record(course_id)
    if not record.exists():
        return None
    import json as _json
    return _json.loads(record.read_text(encoding="utf-8"))


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
    if supplied and compare_digest(str(supplied).strip(), _cert_token()):
        session["vida_cert_ok"] = True
        session.permanent = True
        return True
    return bool(session.get("vida_cert_ok"))


def _logged_in() -> dict | None:
    uid = session.get("uid")
    if not uid:
        return None
    try:
        return accounts.get_user_by_id(str(uid))
    except Exception:
        return None


def _is_guest() -> bool:
    return bool(session.get("guest"))


def _learner_slug() -> str:
    return accounts.slugify(course().get("learner", "Aprendiz VIDA"))


def _needs_account(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _logged_in():
            return jsonify(
                {"ok": False, "error": "Requiere iniciar sesión."}
            ), 401
        return func(*args, **kwargs)

    return wrapper


def _session_context() -> dict:
    user = _logged_in()
    guest = _is_guest()
    return {
        "authed": bool(user),
        "guest": guest,
        "user": user,
        "slug": _learner_slug() if (user or guest) else None,
    }


def _public_profile_data() -> dict:
    course_data = course()
    state = engine_state()
    cert = state["certificate"]
    return {
        "slug": _learner_slug(),
        "learner": course_data.get("learner", "Aprendiz VIDA"),
        "course": course_data.get("title", "Curso SENA"),
        "provider": course_data.get("provider", "SENA"),
        "platform": course_data.get("platform", "Zajuna"),
        "hours": course_data.get("hours", 48),
        "dedication": course_data.get("dedication", ""),
        "overall": state["overall"],
        "mastery": state["mastery"],
        "evidence_count": state["evidence_count"],
        "learning_score": state["learning_score"],
        "video_completed": state["completed_videos"],
        "video_total": state["video_count"],
        "activity_completed": state["completed_activities"],
        "activity_total": state["activity_count"],
        "concept_verified": state["verified_concepts"],
        "concept_total": state["concept_count"],
        "certificate": {
            "issued": cert.get("issued", False),
            "certificate_id": cert.get("certificate_id"),
            "status": cert.get("status"),
            "verification_url": (
                f"/verificar/{cert.get('certificate_id')}"
                if cert.get("certificate_id")
                else None
            ),
        },
    }


def api_snapshot() -> dict:
    return engine_state()


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(ROOT / "vida_ui_pro"),
        static_folder=str(ROOT / "vida_ui_pro"),
        static_url_path="/static",
    )

    app.secret_key = (
        os.environ.get("VIDA_SECRET_KEY")
        or _cert_token()
        or secrets.token_urlsafe(32)
    )
    app.permanent_session_lifetime = timedelta(days=7)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE="VERCEL" in os.environ
        or "NOW_REGION" in os.environ
        or runtime_root() is not DATA,
    )

    @app.get("/")
    def home():
        if not _logged_in() and not _is_guest():
            return redirect("/acceso")
        return render_template(
            "index_pro.html",
            course=course(),
            ctx=_session_context(),
        )

    @app.get("/acceso")
    def acceso():
        if _logged_in():
            return redirect("/")
        return render_template(
            "auth.html",
            slug=_learner_slug(),
        )

    @app.get("/acceso/guest")
    def acceso_guest():
        session["guest"] = True
        session.permanent = True
        return redirect("/")

    @app.post("/api/auth/signup")
    def auth_signup():
        payload = request.get_json(silent=True) or {}
        try:
            user = accounts.create_user(
                payload.get("email", ""),
                payload.get("name", ""),
                payload.get("password", ""),
            )
        except accounts.AccountError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        session.clear()
        session["uid"] = user["id"]
        session.permanent = True
        return jsonify({"ok": True, "user": user}), 201

    @app.post("/api/auth/login")
    def auth_login():
        payload = request.get_json(silent=True) or {}
        if not payload.get("email") or not payload.get("password"):
            return jsonify(
                {"ok": False, "error": "Correo y contraseña son obligatorios."}
            ), 400
        try:
            user = accounts.login(
                payload.get("email", ""),
                payload.get("password", ""),
            )
        except accounts.AccountError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 401
        session.clear()
        session["uid"] = user["id"]
        session.permanent = True
        return jsonify({"ok": True, "user": user})

    @app.post("/api/auth/logout")
    def auth_logout():
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/auth/me")
    def auth_me():
        return jsonify(_session_context())

    @app.get("/api/public/profile")
    def public_profile():
        return jsonify(_public_profile_data())

    @app.get("/perfil")
    def perfil_redirect():
        return redirect(f"/perfil/{_learner_slug()}")

    @app.get("/perfil/<slug>")
    def perfil_page(slug: str):
        data = _public_profile_data()
        if data["slug"] != slug:
            return render_template(
                "perfil.html",
                data={},
                not_found=True,
            ), 404
        return render_template(
            "perfil.html",
            data=data,
            not_found=False,
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
    @_needs_account
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
        if not _cert_allowed(request):
            return jsonify(
                {
                    "ok": False,
                    "error": "Acceso denegado. Se requiere permiso del sistema.",
                }
            ), 403

        payload = request.get_json(silent=True) or {}

        user_confirmation = bool(
            payload.get("user_confirmation", False)
        )

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

        try:
            cert = engine.issue_once(
                course_id=profile.course_id,
                learner=str(
                    course_data.get(
                        "learner",
                        "Aprendiz VIDA",
                    )
                ),
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
            )
        except CertificateAlreadyIssued as exc:
            issued = _load_issued(
                engine,
                profile.course_id,
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

        try:
            vida_store.put_kv(
                f"cert:{profile.course_id}",
                cert.to_dict(),
            )
        except Exception:
            pass

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
        if not _cert_allowed(request):
            return render_template(
                "gated.html",
                target=request.path,
            ), 403

        engine = CertificateEngine(certificates_root())
        profile = ProfileEngine(profile_path()).load()
        record = _load_issued(engine, profile.course_id)

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
        if not _cert_allowed(request):
            return jsonify(
                {
                    "ok": False,
                    "error": "Acceso denegado. Se requiere permiso del sistema.",
                }
            ), 403

        engine = CertificateEngine(certificates_root())
        profile = ProfileEngine(profile_path()).load()
        record = _load_issued(engine, profile.course_id)
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
        return render_template(
            "certificate.html",
            learner=course_data.get("learner", "Aprendiz VIDA"),
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
            cert=api_snapshot()["certificate"],
        )

    @app.get("/api/progress/<vid>")
    def get_video_progress(vid: str):
        cid = active_course_id()
        connection = conn()

        row = connection.execute(
            """
            SELECT *
            FROM video_progress
            WHERE video_id = ? AND course_id = ?
            """,
            (vid, cid),
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
    @_needs_account
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

        completed = int(
            bool(payload.get("completed", False))
        )

        connection = conn()
        cid = active_course_id()

        connection.execute(
            """
            INSERT INTO video_progress (
                video_id,
                course_id,
                position,
                duration,
                completed
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(video_id, course_id)
            DO UPDATE SET
                position = excluded.position,
                duration = excluded.duration,
                completed = excluded.completed,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                vid,
                cid,
                position,
                duration,
                completed,
            ),
        )

        connection.commit()
        connection.close()

        vida_store.upsert_video(vid, cid, position, duration, completed)

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
    @_needs_account
    def set_item(item_id: str):
        payload = request.get_json(silent=True) or {}

        completed = int(
            bool(payload.get("completed", False))
        )

        connection = conn()
        cid = active_course_id()

        connection.execute(
            """
            INSERT INTO item_progress (
                item_id,
                course_id,
                completed
            )
            VALUES (?, ?, ?)

            ON CONFLICT(item_id, course_id)
            DO UPDATE SET
                completed = excluded.completed,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                item_id,
                cid,
                completed,
            ),
        )

        connection.commit()
        connection.close()

        vida_store.upsert_item(item_id, cid, completed)

        return jsonify(
            {
                "ok": True,
                "item_id": item_id,
                "course_id": cid,
                "completed": completed,
            }
        )

    @app.post("/api/study")
    @_needs_account
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
        created_at = datetime.now(timezone.utc).isoformat()
        study_id = vida_store.study_stable_id(
            cid, kind, ref_id, minutes, note
        )

        connection.execute(
            """
            INSERT INTO study_log (
                id,
                course_id,
                kind,
                ref_id,
                minutes,
                note,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                study_id,
                cid,
                kind,
                ref_id,
                minutes,
                note,
                created_at,
            ),
        )

        connection.commit()
        connection.close()

        vida_store.add_study(
            study_id, cid, kind, ref_id, minutes, note, created_at
        )

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

        row = conn_activity.execute(
            """
            SELECT completed FROM item_progress
            WHERE item_id = ?
            """,
            (activity_id,),
        ).fetchone()

        video_row = conn_activity.execute(
            """
            SELECT position, duration, completed
            FROM video_progress
            WHERE video_id = ?
            """,
            (f"video:{activity_id}",),
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

        rows = {
            row["item_id"]: row["completed"]
            for row in connection.execute(
                "SELECT item_id, completed FROM item_progress"
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

    @app.get("/api/evidence")
    def evidence_overview():
        course_data = course()
        result = []
        for item in course_data.get("items", []):
            if item.get("kind") != "activity":
                continue
            activity_id = item["id"]
            result.append(
                {
                    "activity_id": activity_id,
                    "title": item.get("title", activity_id),
                    "records": _evidence_for(activity_id),
                    "files": _uploaded_files(activity_id),
                }
            )
        return jsonify(result)

    @app.post("/api/evidence/<activity_id>")
    @_needs_account
    def upload_evidence(activity_id: str):
        from werkzeug.utils import secure_filename

        if "file" not in request.files:
            return jsonify(
                {"ok": False, "error": "No se recibió archivo."}
            ), 400

        upload = request.files["file"]
        if not upload or not upload.filename:
            return jsonify(
                {"ok": False, "error": "Archivo vacío."}
            ), 400

        safe = secure_filename(upload.filename).lower()
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
        if "." not in safe or safe.rsplit(".", 1)[1] not in allowed:
            return jsonify(
                {
                    "ok": False,
                    "error": "Formato no permitido.",
                }
            ), 400

        evidence_dir = evidence_root() / activity_id
        try:
            evidence_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "No se pudo escribir en el almacén de evidencias "
                        "de este despliegue."
                    ),
                }
            ), 503

        stamp = datetime.now(timezone.utc).strftime(
            "%Y%m%d_%H%M%S"
        )
        stored_name = f"{stamp}_{safe}"
        path = evidence_dir / stored_name
        try:
            upload.save(path)
        except OSError:
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "No se pudo guardar la evidencia en este despliegue."
                    ),
                }
            ), 503

        vida_store.put_file(activity_id, stored_name, path.read_bytes())

        from vida_engines import EvidenceEngine

        evidence = EvidenceEngine(
            evidence_root() / "evidence.json"
        )
        record = evidence.record(
            source=f"work/{activity_id}",
            method="evidence_upload",
            event_type="ACTIVITY_COMPLETE",
            result="DELIVERED",
            context={
                "activity_id": activity_id,
                "file": stored_name,
                "size": path.stat().st_size,
                "note": str(
                    request.form.get("note", "")
                ),
            },
        )

        try:
            ev_path = evidence_root() / "evidence.json"
            if ev_path.exists():
                vida_store.put_kv(
                    "evidence.json",
                    json.loads(ev_path.read_text(encoding="utf-8")),
                )
        except Exception:
            pass

        connection = conn()
        cid = active_course_id()
        connection.execute(
            """
            INSERT INTO item_progress (item_id, course_id, completed)
            VALUES (?, ?, 1)
            ON CONFLICT(item_id, course_id) DO UPDATE SET
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (activity_id, cid),
        )
        connection.commit()
        connection.close()

        vida_store.upsert_item(activity_id, cid, 1)

        return jsonify(
            {
                "ok": True,
                "evidence_id": record.evidence_id,
                "file": stored_name,
                "url": (
                    f"/media/evidence/{activity_id}/"
                    f"{stored_name}"
                ),
            }
        ), 201

    @app.get("/media/evidence/<activity_id>/<path:name>")
    def media_evidence(activity_id: str, name: str):
        return send_from_directory(
            evidence_root() / activity_id,
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

    for video_id in video_ids:
        connection.execute(
            """
            INSERT INTO video_progress (
                video_id, course_id, position, duration, completed
            )
            VALUES (?, ?, 1, 1, 1)
            ON CONFLICT(video_id, course_id) DO UPDATE SET
                position = 1,
                duration = 1,
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (video_id, cid),
        )

    for activity_id in activity_ids + [
        f"concept:{concept_id}"
        for concept_id in concept_ids
    ]:
        connection.execute(
            """
            INSERT INTO item_progress (item_id, course_id, completed)
            VALUES (?, ?, 1)
            ON CONFLICT(item_id, course_id) DO UPDATE SET
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (activity_id, cid),
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
