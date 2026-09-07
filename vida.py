#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
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

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEDIA = ROOT / "media"
DB = DATA / "vida.db"
COURSE = DATA / "course.json"
PROFILE = DATA / "profiles" / "sena_ciberseguridad.json"
CERT_DIR = ROOT / "certificates"
CERT_HTML = ROOT / "certificate.html"

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
    DATA.mkdir(parents=True, exist_ok=True)
    (MEDIA / "videos").mkdir(parents=True, exist_ok=True)
    (MEDIA / "materials").mkdir(parents=True, exist_ok=True)

    if not COURSE.exists():
        COURSE.write_text(
            json.dumps(DEFAULT_COURSE, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def conn() -> sqlite3.Connection:
    ensure_dirs()

    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS video_progress (
            video_id TEXT PRIMARY KEY,
            position REAL NOT NULL DEFAULT 0,
            duration REAL NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS item_progress (
            item_id TEXT PRIMARY KEY,
            completed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            ref_id TEXT,
            minutes REAL NOT NULL DEFAULT 0,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    connection.commit()
    return connection


def course() -> dict:
    ensure_dirs()
    return json.loads(COURSE.read_text(encoding="utf-8"))


def engine_state() -> dict:
    connection = conn()

    items = connection.execute(
        "SELECT item_id, completed FROM item_progress"
    ).fetchall()

    videos = connection.execute(
        """
        SELECT video_id, position, duration, completed
        FROM video_progress
        """
    ).fetchall()

    log = connection.execute(
        "SELECT COALESCE(SUM(minutes), 0) AS minutes FROM study_log"
    ).fetchone()

    connection.close()

    course_data = course()
    profile = ProfileEngine(PROFILE).load()

    videos_cfg = course_data.get("videos", [])
    activities_cfg = [
        item
        for item in course_data.get("items", [])
        if item.get("kind") == "activity"
    ]
    concepts_cfg = course_data.get("concepts", [])

    completed_video_ids = {
        row["video_id"] for row in videos if row["completed"]
    }
    completed_activity_ids = {
        row["item_id"] for row in items if row["completed"]
    }

    verified_concepts = set()
    for concept in concepts_cfg:
        concept_id = str(concept["id"])
        activity_id = f"concept:{concept_id}"
        if activity_id in completed_activity_ids:
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

    certificate = CertificateEngine(CERT_DIR)
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
    evidence_dir = DATA / "evidence"
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


def _load_issued(certificate_engine: CertificateEngine, course_id: str) -> dict | None:
    record = certificate_engine._course_record(course_id)
    if not record.exists():
        return None
    import json as _json
    return _json.loads(record.read_text(encoding="utf-8"))


def api_snapshot() -> dict:
    return engine_state()


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(ROOT / "vida_ui_pro"),
        static_folder=str(ROOT / "vida_ui_pro"),
        static_url_path="/static",
    )

    @app.get("/")
    def home():
        return render_template(
            "index_pro.html",
            course=course(),
        )

    @app.get("/api/dashboard")
    def dashboard():
        return jsonify(api_snapshot())

    @app.get("/api/course")
    def get_course():
        return jsonify(course())

    @app.get("/api/certificate")
    def certificate_status():
        return jsonify(api_snapshot()["certificate"])

    @app.post("/api/certificate")
    def issue_certificate():
        payload = request.get_json(silent=True) or {}

        user_confirmation = bool(
            payload.get("user_confirmation", False)
        )

        state = api_snapshot()

        engine = CertificateEngine(CERT_DIR)
        course_data = course()
        profile = ProfileEngine(PROFILE).load()

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
        engine = CertificateEngine(CERT_DIR)
        profile = ProfileEngine(PROFILE).load()
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
        engine = CertificateEngine(CERT_DIR)
        profile = ProfileEngine(PROFILE).load()
        record = _load_issued(engine, profile.course_id)
        valid = bool(
            record
            and record.get("certificate_id") == certificate_id
        )

        return jsonify(
            {
                "valid": valid,
                "certificate": record if valid else None,
            }
        )

    @app.get("/certificado")
    def certificate_page():
        course_data = course()
        return render_template(
            "certificate.html",
            learner=course_data.get("learner", "Aprendiz VIDA"),
            tutor=course_data.get("tutor", "Instructor SENA"),
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
        connection = conn()

        row = connection.execute(
            """
            SELECT *
            FROM video_progress
            WHERE video_id = ?
            """,
            (vid,),
        ).fetchone()

        connection.close()

        if row:
            return jsonify(dict(row))

        return jsonify(
            {
                "video_id": vid,
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

        completed = int(
            bool(payload.get("completed", False))
        )

        connection = conn()

        connection.execute(
            """
            INSERT INTO video_progress (
                video_id,
                position,
                duration,
                completed
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(video_id)
            DO UPDATE SET
                position = excluded.position,
                duration = excluded.duration,
                completed = excluded.completed,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                vid,
                position,
                duration,
                completed,
            ),
        )

        connection.commit()
        connection.close()

        return jsonify(
            {
                "ok": True,
                "video_id": vid,
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

        connection.execute(
            """
            INSERT INTO item_progress (
                item_id,
                completed
            )
            VALUES (?, ?)

            ON CONFLICT(item_id)
            DO UPDATE SET
                completed = excluded.completed,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                item_id,
                completed,
            ),
        )

        connection.commit()
        connection.close()

        return jsonify(
            {
                "ok": True,
                "item_id": item_id,
                "completed": completed,
            }
        )

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

        connection.execute(
            """
            INSERT INTO study_log (
                kind,
                ref_id,
                minutes,
                note
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                kind,
                ref_id,
                minutes,
                note,
            ),
        )

        connection.commit()
        connection.close()

        return jsonify({"ok": True})

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

    for video_id in video_ids:
        connection.execute(
            """
            INSERT INTO video_progress (
                video_id, position, duration, completed
            )
            VALUES (?, 1, 1, 1)
            ON CONFLICT(video_id) DO UPDATE SET
                position = 1,
                duration = 1,
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (video_id,),
        )

    for activity_id in activity_ids + [
        f"concept:{concept_id}"
        for concept_id in concept_ids
    ]:
        connection.execute(
            """
            INSERT INTO item_progress (item_id, completed)
            VALUES (?, 1)
            ON CONFLICT(item_id) DO UPDATE SET
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (activity_id,),
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
    profile = ProfileEngine(PROFILE).load()
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

    engine = CertificateEngine(CERT_DIR)

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
