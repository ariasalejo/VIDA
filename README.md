# 🧠 VIDA Studio

Centro personal de aprendizaje de BLUMIX. Terminal + UI/UX web local + SQLite + motor de progreso.

## Arranque

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python vida.py init
python vida.py tui
python vida.py web
```

## Vídeos

Coloca grabaciones en `media/videos/` y añade su entrada en `data/course.json`:

```json
{"id":"conf01","kind":"video","title":"Conferencia 01","file":"conf01.mp4"}
```

VIDA registra posición, duración, porcentaje y completitud en SQLite. No guarda credenciales de Zajuna.

## Filosofía

Aprender → practicar → construir → comprender → avanzar.

BLUMCL, BLUMELIX y VIDA son proyectos/componentes con responsabilidades separadas.
