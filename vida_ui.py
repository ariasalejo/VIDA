from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Label, ProgressBar
from textual.reactive import reactive

from vida_engines import ProgressEngine, IntelligenceEngine, ProfileEngine


BASE_DIR = Path(__file__).resolve().parent
COURSE_FILE = BASE_DIR / "data" / "course.json"
DB_FILE = BASE_DIR / "data" / "vida.db"
PROFILE_FILE = BASE_DIR / "data" / "profiles" / "sena_ciberseguridad.json"


class MetricCard(Static):
    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
    ) -> None:
        super().__init__()
        self.title = title
        self.value = value
        self.subtitle = subtitle

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="card-title")
        yield Label(self.value, classes="card-value")
        if self.subtitle:
            yield Label(
                self.subtitle,
                classes="card-subtitle",
            )


class VIDAApp(App):
    TITLE = "VIDA · Centro Inteligente de Aprendizaje"
    SUB_TITLE = "Ciberseguridad · SENA"

    CSS = """
    Screen {
        background: #07111f;
        color: #e6edf7;
    }

    Header {
        background: #0b1728;
        color: #ffffff;
        height: 3;
    }

    Footer {
        background: #0b1728;
        color: #9fb3c8;
    }

    #body {
        height: auto;
        padding: 1 2;
    }

    #hero {
        height: 7;
        padding: 1 2;
        background: #0d1b2d;
        border: round #24415f;
    }

    #hero-title {
        color: #7dd3fc;
        text-style: bold;
        width: 100%;
    }

    #hero-subtitle {
        color: #9fb3c8;
        margin-top: 1;
    }

    #metrics {
        height: 9;
        margin-top: 1;
    }

    .metric {
        width: 1fr;
        height: 7;
        margin-right: 1;
        padding: 1;
        background: #0d1b2d;
        border: round #24415f;
    }

    .metric:last-child {
        margin-right: 0;
    }

    .card-title {
        color: #8ba4bd;
    }

    .card-value {
        color: #7dd3fc;
        text-style: bold;
        margin-top: 1;
    }

    .card-subtitle {
        color: #71869b;
        margin-top: 1;
    }

    #content {
        height: auto;
        min-height: 8;
        margin-top: 1;
    }

    .panel {
        width: 1fr;
        height: auto;
        min-height: 8;
        padding: 1 2;
        background: #0d1b2d;
        border: round #24415f;
        margin-right: 1;
    }

    .panel:last-child {
        margin-right: 0;
    }

    .panel-title {
        color: #7dd3fc;
        text-style: bold;
        margin-bottom: 1;
    }

    .signal {
        height: 2;
        color: #c5d3e0;
    }

    .observed {
        color: #86efac;
    }

    .inferred {
        color: #fbbf24;
    }

    .action-high {
        color: #fb7185;
    }

    .action-medium {
        color: #fbbf24;
    }

    .action-low {
        color: #86efac;
    }

    #progress-panel {
        height: auto;
        min-height: 6;
        margin-top: 1;
        padding: 1 2;
        background: #0d1b2d;
        border: round #24415f;
    }

    ProgressBar {
        margin-top: 1;
    }
    """

    BINDINGS = [
        # Sistema
        ("q", "quit", "Salir"),
        ("r", "refresh", "Actualizar"),
        ("i", "intelligence", "Inteligencia"),

        # Navegación principal
        ("1", "dashboard", "Dashboard"),
        ("2", "activities", "Actividades"),
        ("3", "videos", "Videos"),
        ("4", "concepts", "Conceptos"),
        ("5", "evidence", "Evidencias"),
        ("6", "intelligence", "Inteligencia"),
        ("7", "profile", "Perfil"),
        ("8", "course", "Curso"),
        ("9", "help", "Ayuda"),

        # Navegación de interfaz
        ("enter", "select", "Seleccionar"),
        ("tab", "focus_next", "Siguiente"),
        ("shift+tab", "focus_previous", "Anterior"),
        ("up", "cursor_up", "Arriba"),
        ("down", "cursor_down", "Abajo"),
        ("left", "cursor_left", "Izquierda"),
        ("right", "cursor_right", "Derecha"),
        ("home", "home", "Inicio"),
        ("end", "end", "Final"),
        ("escape", "close_menu", "Cerrar"),
        ("question_mark", "help", "Ayuda"),
        ("h", "help", "Ayuda"),
    ]

    score = reactive(0.0)

    def load_course(self) -> dict:
        if not COURSE_FILE.exists():
            return {}

        return json.loads(
            COURSE_FILE.read_text(
                encoding="utf-8"
            )
        )

    def database_state(self) -> dict:
        state = {
            "completed_videos": set(),
            "completed_activities": set(),
            "verified_concepts": set(),
            "evidence_count": 0,
        }

        if not DB_FILE.exists():
            return state

        with sqlite3.connect(DB_FILE) as db:
            db.row_factory = sqlite3.Row

            try:
                rows = db.execute(
                    """
                    SELECT item_id, completed
                    FROM item_progress
                    """
                ).fetchall()

                for row in rows:
                    if row["completed"]:
                        item_id = str(row["item_id"])

                        if item_id.startswith("video:"):
                            state["completed_videos"].add(
                                item_id.removeprefix("video:")
                            )
                        else:
                            state["completed_activities"].add(
                                item_id
                            )

            except sqlite3.OperationalError:
                pass

            try:
                rows = db.execute(
                    """
                    SELECT video_id
                    FROM video_progress
                    """
                ).fetchall()

                for row in rows:
                    state["completed_videos"].add(
                        str(row["video_id"])
                    )

            except sqlite3.OperationalError:
                pass

            try:
                state["evidence_count"] = db.execute(
                    """
                    SELECT COUNT(*)
                    FROM evidence
                    """
                ).fetchone()[0]

            except sqlite3.OperationalError:
                pass

        return state

    def calculate(self):
        course = self.load_course()
        state = self.database_state()

        activities = [
            item
            for item in course.get("items", [])
            if item.get("kind") == "activity"
        ]

        videos = course.get("videos", [])
        concepts = course.get("concepts", [])

        completed_activities = len(
            state["completed_activities"]
            & {
                str(item.get("id"))
                for item in activities
            }
        )

        completed_videos = len(
            state["completed_videos"]
            & {
                str(video.get("id"))
                for video in videos
            }
        )

        verified_concepts = len(
            state["verified_concepts"]
            & {
                str(concept.get("id"))
                for concept in concepts
            }
        )

        profile = ProfileEngine(PROFILE_FILE).load()

        progress = ProgressEngine().calculate(
            completed_videos=completed_videos,
            total_videos=len(videos),
            completed_activities=completed_activities,
            total_activities=len(activities),
            verified_concepts=verified_concepts,
            total_concepts=len(concepts),
            evidence_count=state["evidence_count"],
            profile=profile,
        )

        intelligence = IntelligenceEngine(profile=profile)

        video_ids = {
            str(video.get("id"))
            for video in videos
        }

        activity_ids = {
            str(item.get("id"))
            for item in activities
        }

        concept_ids = {
            str(concept.get("id"))
            for concept in concepts
        }

        signals = intelligence.signals(
            course,
            state["completed_videos"] & video_ids,
            state["completed_activities"] & activity_ids,
            state["verified_concepts"] & concept_ids,
            state["evidence_count"],
        )

        score = intelligence.learning_score(
            course,
            state["completed_videos"] & video_ids,
            state["completed_activities"] & activity_ids,
            state["verified_concepts"] & concept_ids,
            state["evidence_count"],
        )

        actions = intelligence.next_actions(
            course,
            state["completed_videos"] & video_ids,
            state["completed_activities"] & activity_ids,
            state["verified_concepts"] & concept_ids,
            state["evidence_count"],
        )

        return course, progress, signals, actions, score

    def compose(self) -> ComposeResult:
        course, progress, signals, actions, score = self.calculate()

        self.score = score

        title = course.get(
            "title",
            "Curso no disponible",
        )

        yield Header()

        with Container(id="body"):

            with Vertical(id="hero"):
                yield Label(
                    "🌿 VIDA · CENTRO INTELIGENTE DE APRENDIZAJE",
                    id="hero-title",
                )

                yield Label(
                    f"{title} · Seguimiento curricular · Evidencia · Inteligencia adaptativa",
                    id="hero-subtitle",
                )

            activities = [
                item
                for item in course.get("items", [])
                if item.get("kind") == "activity"
            ]

            videos = course.get("videos", [])

            evidence = progress.evidence_count

            with Horizontal(id="metrics"):

                yield MetricCard(
                    "LEARNING SCORE",
                    f"{score:.1f}%",
                    "Inteligencia adaptativa",
                ).add_class("metric")

                yield MetricCard(
                    "ACTIVIDADES",
                    f"{round(progress.operational / 100 * len(activities))} / {len(activities)}",
                    f"{progress.operational}% operacional",
                ).add_class("metric")

                if videos:
                    completed = round(
                        progress.operational / 100 * len(videos)
                    )

                    yield MetricCard(
                        "VIDEOS",
                        f"{completed} / {len(videos)}",
                        f"{round(completed / len(videos) * 100)}% completado",
                    ).add_class("metric")
                else:
                    yield MetricCard(
                        "VIDEOS",
                        "0",
                        "No registrados en el manifiesto",
                    ).add_class("metric")

                yield MetricCard(
                    "EVIDENCIA",
                    str(evidence),
                    "Registros disponibles",
                ).add_class("metric")

            with Horizontal(id="content"):

                with Vertical(classes="panel"):

                    yield Label(
                        "INTELLIGENCE SIGNALS",
                        classes="panel-title",
                    )

                    for signal in signals:
                        yield Label(
                            f"● {signal.name:<20} "
                            f"{signal.value:.3f} "
                            f"[{signal.kind}]",
                            classes=f"signal {signal.kind}",
                        )

                with Vertical(classes="panel"):

                    yield Label(
                        "NEXT ACTIONS",
                        classes="panel-title",
                    )

                    if actions:
                        for action in actions[:6]:

                            priority = action.get(
                                "priority",
                                "medium",
                            ).upper()

                            yield Label(
                                f"{priority:<6} → "
                                f"{action.get('title', 'Acción')}",
                                classes=(
                                    f"signal action-"
                                    f"{action.get('priority', 'medium')}"
                                ),
                            )

                    else:
                        yield Label(
                            "✓ No hay acciones pendientes.",
                            classes="signal action-low",
                        )

            with Vertical(id="progress-panel"):

                yield Label(
                    "PROGRESO OPERACIONAL",
                    classes="panel-title",
                )

                yield ProgressBar(
                    total=100,
                    show_eta=False,
                    id="main-progress",
                )

        yield Footer()

    def on_mount(self) -> None:
        self.query_one(
            "#main-progress",
            ProgressBar,
        ).update(
            progress=self.score
        )

    def action_dashboard(self) -> None:
        self.notify(
            "Dashboard principal de VIDA",
            title="1 · DASHBOARD",
            severity="information",
        )

    def action_activities(self) -> None:
        self.notify(
            "Módulo de actividades seleccionado",
            title="2 · ACTIVIDADES",
            severity="information",
        )

    def action_videos(self) -> None:
        self.notify(
            "Módulo de videos seleccionado",
            title="3 · VIDEOS",
            severity="information",
        )

    def action_concepts(self) -> None:
        self.notify(
            "Módulo de conceptos seleccionado",
            title="4 · CONCEPTOS",
            severity="information",
        )

    def action_evidence(self) -> None:
        self.notify(
            "Módulo de evidencias seleccionado",
            title="5 · EVIDENCIAS",
            severity="information",
        )

    def action_profile(self) -> None:
        self.notify(
            "Perfil SENA de aprendizaje seleccionado",
            title="7 · PERFIL",
            severity="information",
        )

    def action_course(self) -> None:
        self.notify(
            "Información del curso seleccionada",
            title="8 · CURSO",
            severity="information",
        )

    def action_help(self) -> None:
        self.notify(
            "Q Salir · R Actualizar · I Inteligencia · "
            "1-9 módulos · Enter seleccionar · Tab siguiente · "
            "Shift+Tab anterior · Flechas navegar · "
            "Home/End extremos · Esc cerrar",
            title="VIDA · ATAJOS DE TECLADO",
            severity="information",
        )

    def action_select(self) -> None:
        self.notify(
            "Elemento seleccionado",
            title="ENTER",
            severity="information",
        )

    def action_close_menu(self) -> None:
        self.notify(
            "Menú cerrado",
            title="ESC",
            severity="information",
        )

    def action_home(self) -> None:
        self.notify(
            "Inicio",
            title="HOME",
            severity="information",
        )

    def action_end(self) -> None:
        self.notify(
            "Final",
            title="END",
            severity="information",
        )

    def action_refresh(self) -> None:
        self.notify(
            "Actualizando estado de VIDA...",
            title="VIDA",
            severity="information",
        )

        self.refresh()

    def action_intelligence(self) -> None:
        self.notify(
            "Intelligence Engine activo · "
            "Observado ≠ Inferido ≠ Predicho",
            title="INTELLIGENCE",
            severity="information",
        )


if __name__ == "__main__":
    VIDAApp().run()
