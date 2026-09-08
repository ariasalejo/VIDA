# 🧠 VIDA · BLUMIX
### Learning Command Center · Apropiación de los Conceptos en Ciberseguridad

> **Observar · verificar · comprender · demostrar · avanzar.**

Centro personal de aprendizaje del curso SENA **«Apropiación de los Conceptos en Ciberseguridad»**
(48 horas · plataforma **Zajuna**). VIDA no es un gestor de tareas: es un **motor de evidencia
e inteligencia adaptativa** que solo registra lo que se demuestra, nunca lo que se asume.

---

## 👤 Protagonista

| | |
|---|---|
| 🎓 **Aprendiz** | Eduar Alejandro Arias Londoño |
| 🏛 **Institución** | SENA · Zajuna |
| ⏱ **Horas** | 48 |
| 🌐 **Fuente del curso** | [zajuna.sena.edu.co](https://zajuna.sena.edu.co/) |

> ✦ Al final del dashboard, VIDA lleva una **dedicatoria al docente y al SENA**, en letra cursiva. ✦

---

## 🚀 Características

- 📈 **Progreso operativo** ponderado: actividades, sesiones grabadas y conceptos.
- 🧠 **Intelligence Engine**: señales observadas vs. inferidas vs. predichas (sin inventar evidencia).
- 🎬 **Media Engine**: reproducción de sesiones sincrónicas con registro de posición, duración y completitud.
- 📤 **Evidencias reales**: subida de entregas (PDF, imágenes, XLSX…) con trazabilidad verificable.
- ⚖️ **Reglas transparentes**: quién califica, con qué pesos y bajo qué condiciones se certifica.
- 🏆 **Certificado verificable**, protegido con clave privada.
- 🔊 **Guía por voz** en español (preferencia de **voz femenina**).
- 🚧 **Zona en construcción**: lo que está por llegar, sin engaños.
- 🛰 **Multi-curso adaptativo**: selector en tiempo real (el perfil se ajusta solo).
- 📟 Tres interfaces: **web** (Flask), **TUI** (Textual) y **CLI**.
- 🎛 **Dashboard pro**: desglose de progreso por componente, señales del motor (OBSERVADO/INFERIDO/PREDICHO), próximos pasos y ruta curricular con las actividades reales.
- ✦ **Dedicatoria final** al docente y al SENA, en letra cursiva.

---

## 🧰 Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3 · Flask |
| UI web | HTML · CSS · JS (SPA ligera por hash) |
| TUI | Textual |
| Datos | SQLite (`vida.db`) + manifiestos JSON |
| Inteligencia | Motor determinista y explicable (`IntelligenceEngine`) |
| Deploy | Vercel (`@vercel/python`) |

---

## 📂 Estructura

```
vida.py                # Núcleo: app Flask, motor, comandos CLI
vida_engines/          # Motores: progreso, evidencia, inteligencia, certificado…
vida_ui_pro/           # UI web profesional (index_pro, app_pro, estilos)  ← la que ves en Vercel
vida_core/             # UI web clásica (templates/static)
vida_ui.py             # Interfaz TUI (terminal)
api/index.py           # Punto de entrada para Vercel
data/                  # Manifiestos, perfil, reglas y base SQLite
media/videos/          # 🎬 Sesiones grabadas (MP4)
media/materials/       # 📚 Material de aprendizaje
tests/                 # Suites de prueba (pytest)
```

---

## ⚡ Arranque local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python vida.py init     # prepara carpetas y base
python vida.py web      # servidor → http://127.0.0.1:8787
python vida.py tui      # interfaz de terminal
python vida.py seed     # (para pruebas) registra trabajos como entregados
python vida.py cert     # emite el certificado (si cumples las condiciones)
```

---

## 🎬 Sesiones grabadas

Coloca el MP4 de la sesión en `media/videos/` y regístralo en `data/course.json`
(cada actividad en `items[].video` y la sesión del dashboard en `videos[0]`):

```json
{ "id": "video_dashboard", "title": "Ciberseguridad · sesión del dashboard", "file": "media/videos/dashboard_sesion.mp4", "required": true }
```

| Sesión | Archivo en `media/videos/` | Actividad |
|---|---|---|
| Dashboard · Ciberseguridad | `dashboard_sesion.mp4` | Reproductor principal |
| AA1 · Informe de activos | `Und_Bien.mp4` | `aa1` |
| AA2 · Infografía de riesgos | `aa2_infografia.mp4` | `aa2` |
| AA3 · Matriz de riesgo | `aa3_matriz_riesgo.mp4` | `aa3` |
| AA4 · Mapa mental | `aa4_mapa_mental.mp4` | `aa4` |

VIDA guarda **posición, duración, porcentaje y completitud** en SQLite.
No guarda credenciales de Zajuna. La sesión del dashboard es un clip de ~12 MB.

> ⚠️ **Sobre el deploy del video:** las cinco sesiones quedaron comprimidas por debajo
> del límite de 100 MB por archivo de GitHub (dashboard ~12 MB, AA1 ~64 MB, AA2 ~81 MB,
> AA3 ~95 MB, AA4 ~90 MB), por lo que sí pueden subirse al repo. El problema de tamaño
> se resuelve, pero **Vercel** (límite de función ~250 MB) no puede servir ~340 MB de
> videos de modo fiable; para una versión completa en el servidor, múdalo a un
> bucket/streaming y cambia `file` por una URL pública.

---

## 🔑 Clave del certificado

El certificado y los cambios de curso están protegidos por una **clave privada de solo lectura**
(no se publica aquí). Se configura con la variable de entorno `VIDA_CERT_KEY`;
la primera vez se escribe en `data/.cert_token` (local) y está excluida del README por seguridad.

> 🔒 **Privacidad:** ni el nombre del instructor ni la clave del certificado aparecen en este documento.

---

## 🔊 Guía por voz

El botón 🔊 del encabezado narra la sección en la que estás. VIDA:
- habla **español** (`es-CO`), ritmo calmado (`0.94`) y tono más agudo (`pitch 1.12`);
- **prioriza voces femeninas** disponibles en tu sistema (Laura, Helena, Mónica, Ximena, Google español…);
- si no hay voces en español, usa la mejor opción disponible del navegador.

---

## 🚧 Zona en construcción

El panel **«🚧 Zona en construcción»** del dashboard es la honestidad del motor:
- 📼 sesiones que aún no están disponibles en el servidor;
- 📚 materiales de aprendizaje por montar;
- 📝 entregas pendientes;
- 🏆 el certificado, que solo se emite cuando *demuestras* todo.

Nada se marca como hecho sin evidencia. *El motor no adivina.*

---

## 🧠 Filosofía

**Aprender → practicar → construir → comprender → avanzar.**

- La **evidencia observada** es la única que alimenta el progreso.
- La **predicción** nunca se convierte en hecho.
- El **certificado** se emite una sola vez, con reglas explícitas y verificables ante el instructor.

BLUMCL, BLUMELIX y VIDA son proyectos con responsabilidades separadas.

---

## 🧪 Pruebas

```bash
source .venv/bin/activate
pytest -q
```

---

## 🏗 Hoja de ruta

- [x] Motor de progreso, evidencia, inteligencia y certificados
- [x] UI web profesional responsive + multi-curso
- [x] Guía por voz en español (voz femenina)
- [x] Sesión grabada integrada y desplegada en Vercel
- [x] Dedicatoria especial al docente y al SENA (final del dashboard, en cursiva)
- [x] Sesiones por actividad (AA1–AA4) más video del dashboard
- [ ] Material de aprendizaje por actividad
- [ ] Certificado final emitido

🚧 *VIDA es obra viva: crece con cada sesión, cada entrega y cada concepto demostrado.* 🚧