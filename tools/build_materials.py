#!/usr/bin/env python3
"""Genera las guías de estudio de VIDA en media/materials/.

Lee data/course.json para extraer actividades, conceptos y ruta de aprendizaje
para que el material nunca se desalinee del currículo real. Salida: un HTML
autocontenido (imprimible a PDF) por actividad con la identidad visual de VIDA.

Uso:  python3 tools/build_materials.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COURSE = ROOT / "data" / "course.json"
OUT_DIR = ROOT / "media" / "materials"

STYLE = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#06111d;--panel:#0b1b2a;--panel2:#071522;--line:#1b3d56;--cyan:#45e6ff;
      --blue:#2e8bff;--green:#47e0b7;--gold:#d4af37;--text:#eef8ff;--muted:#8aa8ba}
body{background:radial-gradient(circle at top,rgba(46,139,255,.16),transparent 34%),
  linear-gradient(180deg,#06111d,#03080f);color:var(--text);min-height:100vh;
  font-family:Inter,system-ui,-apple-system,sans-serif;line-height:1.6}
.wrap{max-width:860px;margin:0 auto;padding:38px 22px 60px}
.head{display:flex;justify-content:space-between;align-items:center;gap:12px;
  padding-bottom:16px;border-bottom:1px solid var(--line);margin-bottom:26px;flex-wrap:wrap}
.brand{color:var(--cyan);letter-spacing:.2em;font-weight:900;font-size:12px}
.chip{font:10px ui-monospace,monospace;letter-spacing:.12em;color:#021018;
  background:linear-gradient(135deg,var(--blue),var(--cyan));border-radius:999px;padding:5px 12px;font-weight:800}
h1{font-size:30px;font-weight:900;line-height:1.2;margin:8px 0 6px}
.kicker{color:var(--muted);letter-spacing:.18em;font-size:11px;font-weight:800}
.brief{color:var(--muted);font-size:14.5px;margin:8px 0 0;max-width:70ch}
.deliv{margin-top:10px;font-size:13px;color:var(--green)}
section{margin-top:30px}
section h2{font-size:15px;letter-spacing:.1em;color:var(--cyan);font-weight:900;
  text-transform:uppercase;margin-bottom:14px;display:flex;align-items:center;gap:8px}
section h2::before{content:"✦";color:var(--gold)}
.card{background:linear-gradient(180deg,var(--panel),var(--panel2));
  border:1px solid var(--line);border-radius:16px;padding:20px 22px}
.card+.card{margin-top:12px}
.concept{display:flex;gap:14px;align-items:flex-start}
.concept b{color:var(--gold);white-space:nowrap;font-size:14px}
.concept p{color:var(--muted);font-size:13.5px}
ol.steps{counter-reset:step;list-style:none}
ol.steps li{counter-increment:step;position:relative;padding:0 0 16px 46px;font-size:14px;color:var(--text)}
ol.steps li::before{content:counter(step,decimal-leading-zero);position:absolute;left:0;top:0;
  width:32px;height:32px;display:grid;place-items:center;border:1px solid var(--cyan);
  color:var(--cyan);border-radius:9px;font-weight:800;font-size:13px;background:#071522}
ol.steps li b{color:var(--cyan)}
ol.steps li small{display:block;color:var(--muted);font-size:12.5px;margin-top:2px}
ul.check{list-style:none}
ul.check li{position:relative;padding:7px 0 7px 34px;font-size:13.5px;color:var(--text);border-bottom:1px dashed var(--line)}
ul.check li:last-child{border-bottom:0}
ul.check li::before{content:"□";position:absolute;left:4px;top:6px;color:var(--cyan);font-size:16px;font-weight:800}
code{background:var(--panel2);border:1px solid var(--line);color:#8cc7db;padding:2px 7px;border-radius:6px;font-size:12px}
.pill{display:inline-block;margin-top:16px;padding:8px 14px;border:1px solid #1d574c;color:var(--green);
  border-radius:999px;letter-spacing:.12em;font-size:10px}
.printbar{position:sticky;top:10px;text-align:right;margin-bottom:6px}
.btn{background:linear-gradient(135deg,var(--blue),var(--cyan));border:0;color:#021018;
  font-weight:800;letter-spacing:.06em;padding:10px 18px;border-radius:11px;cursor:pointer;font-size:12.5px}
.foot{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);
  color:#6f8fa3;font-size:11px;text-align:center}
@media print{.printbar{display:none}body{background:#fff;color:#0b1b2a}
  .card{border:1px solid #d8e6f0;background:#fff}section h2{color:#0b3d66}
  .concept b{color:#8a6d1a}.kicker,.brand{color:#4a6780}}
""".strip()

FOOTER = """
<div class="foot">Material de estudio generado por BLUMIX · VIDA a partir del
manifiesto del curso. No constituye certificación oficial del SENA · Imprimible a PDF.</div>
"""


def concept_definitions(course: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for concept in course.get("concepts", []):
        out[concept["id"]] = concept.get("definition", "")
    return out


def learning_map(course: dict) -> dict[str, list[str]]:
    """activity_id -> lista de concept_ids asociados en la ruta de aprendizaje."""
    mapping: dict[str, list[str]] = {}
    for step in course.get("learning_path", []):
        activity = step.get("activity")
        if activity:
            seen = mapping.setdefault(activity, [])
            for cid in step.get("concepts", []):
                if cid not in seen:
                    seen.append(cid)
    return mapping


def steps_for(id: str) -> list[tuple[str, str]]:
    return {
        "aa1": [
            ("Inventario de activos", "Identifica hardware, software, personas, datos y documentos que sostienen los procesos de la organización."),
            ("Clasificación por valor", "Clasifica cada activo según su criticidad en los criterios CIA: Confidencialidad, Integridad y Disponibilidad."),
            ("Valoración del impacto", "Estima el impacto de una pérdida o degradación de cada activo (bajo, medio, alto, muy alto)."),
            ("Informe técnico", "Consolida en un documento PDF con tablas, criterios y conclusiones."),
        ],
        "aa2": [
            ("Clases de amenazas", "Clasifica amenazas humanas, técnicas, físicas y de origen natural según tu contexto."),
            ("Vulnerabilidades asociadas", "Cruza cada amenaza con la vulnerabilidad de que se aprovecha y el activo afectado."),
            ("Análisis probabilidad-impacto", "Valora probabilidad e impacto para priorizar; usa la escala que defina tu organización."),
            ("Infografía", "Representa el proceso de análisis y evaluación de riesgos de forma visual (PDF o imagen)."),
        ],
        "aa3": [
            ("Contexto y alcance", "Define el alcance de los procesos y activos que entran en la matriz."),
            ("Cuantificación", "Asigna probabilidad (1-5) e impacto (1-5) a cada riesgo y calcula su nivel."),
            ("Niveles y zonas de atención", "Ubica cada riesgo en la matriz y marca umbrales de aceptación."),
            ("Tratamiento", "Propón controles por riesgo y registra el riesgo residual esperado."),
        ],
        "aa4": [
            ("Procesos críticos", "Selecciona los procesos de la gestión de seguridad de la información que vas a sintetizar."),
            ("Nodos conceptuales", "Enlaza los conceptos clave: activo, amenaza, vulnerabilidad, riesgo, control."),
            ("Relaciones", "Conecta cada concepto con los procesos y controles asociados."),
            ("Mapa mental", "Sintetiza visualmente en un mapa mental claro y jerarquizado (imagen o PDF)."),
        ],
    }.get(id, [("Estudia el material guía", "Revisa la sesión grabada y los conceptos asociados.")])


def check_for(id: str) -> list[str]:
    return {
        "aa1": [
            "El inventario cubre activos tangibles, intangibles y de información.",
            "Cada activo tiene clasificación CIA y nivel de criticidad.",
            "El informe incluye criterios, justificación y conclusiones.",
        ],
        "aa2": [
            "Se diferencian amenazas, vulnerabilidades y riesgos.",
            "Probabilidad e impacto tienen escala y criterios explícitos.",
            "La infografía transmite el proceso completo de evaluación.",
        ],
        "aa3": [
            "Todos los riesgos identificados tienen probabilidad e impacto.",
            "El mapa visual refleja niveles y prioridades.",
            "Cada riesgo crítico tiene tratamiento y riesgo residual estimado.",
        ],
        "aa4": [
            "El mapa cubre los procesos de la gestión de seguridad.",
            "Incluye activos, amenazas, vulnerabilidades, riesgos y controles.",
            "La síntesis es visual, jerarquizada y legible.",
        ],
    }.get(id, [])


def render(course: dict, item: dict, concepts: dict[str, str], steps: list, checks: list) -> str:
    aid = item["id"]
    defs = concepts
    concept_list = learning_map(course).get(aid, [])
    concept_html = "".join(
        f'<div class="card concept"><b>{concepts.get(cid, cid).split(" ")[0]}</b>'
        f'<p><b>{concepts.get(cid, cid)}</b>'
        f" — {defs.get(cid, 'Concepto de la ruta de aprendizaje del curso.')}</p></div>"
        for cid in concept_list
    )
    steps_html = "".join(
        f'<li><b>{title}</b><small>{detail}</small></li>' for title, detail in steps
    )
    checks_html = "".join(f"<li>{c}</li>" for c in checks)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{item.get('title')} · VIDA</title>
<style>{STYLE}</style></head>
<body><div class="wrap">
<div class="printbar"><button class="btn" onclick="window.print()">🖨 Imprimir / PDF</button></div>
<header class="head">
  <div class="brand">🧠 BLUMIX · VIDA</div>
  <span class="chip">{aid.upper()} · SENA</span>
</header>
<div class="kicker">GUÍA DE ESTUDIO · {item.get('title','')}</div>
<h1>{item.get('title','')}</h1>
<p class="brief">{item.get('brief','')}</p>
<p class="deliv">📦 Entregable: {item.get('deliverable','')}</p>

<section><h2>Conceptos clave</h2>{concept_html}</section>

<section><h2>Ruta de trabajo</h2>
<ol class="steps">{steps_html}</ol></section>

<section><h2>Checklist de entrega</h2>
<div class="card"><ul class="check">{checks_html}</ul>
<span class="pill">PERSONAL · UNA ENTREGA POR EVIDENCIA</span></div></section>

{FOOTER}
</div></body></html>
"""


def main() -> None:
    course = json.loads(COURSE.read_text(encoding="utf-8"))
    concepts = concept_definitions(course)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for item in course.get("items", []):
        if item.get("kind") != "activity":
            continue
        aid = item["id"]
        html = render(
            course,
            item,
            concepts,
            steps_for(aid),
            check_for(aid),
        )
        target = OUT_DIR / f"{aid}_guia.html"
        target.write_text(html, encoding="utf-8")
        written.append(target.name)
    print("Guías generadas:", ", ".join(written))


if __name__ == "__main__":
    sys.exit(main())