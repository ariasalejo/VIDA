# 🧠 VIDA · BLUMIX
### Learning Command Center · Apropiación de los Conceptos en Ciberseguridad

> **Observar · verificar · comprender · demostrar · avanzar.**

VIDA es un **Command Center Learning**: un centro personal de aprendizaje cuya
ética es que *solo se registra lo que se demuestra, nunca lo que se asume*.

Se entrega con el curso SENA **«Apropiación de los Conceptos en Ciberseguridad»**
(48 horas · plataforma **Zajuna**) como su primera fuente de conocimiento, pero
**no está anclada a ese curso**: su **núcleo es estable** y su **perfil es adaptable**
a la siguiente fuente de conocimiento que decidas estudiar.

---

## 🧭 La idea en una frase

> El **núcleo de VIDA no varía** de una materia a otra: solo se **adapta en
> infraestructura y diseño** según lo que vayas a estudiar, y se **mejora en
> profundidad** — nunca se reconstruye desde cero.

VIDA separa lo que **siempre se mantiene** de lo que **cambia por curso**:

| 🔒 Núcleo estable (no varía) | 🧩 Capa adaptable (cambia por curso) |
|---|---|
| Motor de **evidencia** con trazabilidad verificable | Manifiesto del curso: objetivos, actividades, entregables |
| Motor de **inteligencia** determinista y explicable | Conceptos y pesos de valoración (skill profile) |
| Reglas de **certificación** y emisión única | Reglas y condiciones del curso |
| Progreso ponderado por componente | Materiales, sesiones grabadas y fechas |
| Interfaces web / TUI / CLI y la dedicatoria al docente | Identidad del aprendiz, instructor y dedicación |

Así, cambiar de carrera o de asignatura es **aportar un nuevo curso**, no
reescribir la plataforma. Ver [`docs/ADAPTACION.md`](docs/ADAPTACION.md).

---

## 👤 Protagonista

| | |
|---|---|
| 🎓 **Aprendiz** | Eduar Alejandro Arias Londoño |
| 🏛 **Institución** | SENA · Zajuna |
| ⏱ **Horas** | 48 |
| 🌐 **Fuente de conocimiento (2026)** | [zajuna.sena.edu.co](https://zajuna.sena.edu.co/) |

> ✦ Al final del dashboard, VIDA lleva una **dedicatoria al docente y al SENA**, en letra cursiva. ✦

---

## 🚀 Características

- 📈 **Progreso operativo ponderado**: actividades, sesiones grabadas y conceptos.
- 🧠 **Intelligence Engine**: señales observadas vs. inferidas vs. predichas (sin inventar evidencia).
- 🎬 **Media Engine**: reproducción de sesiones sincrónicas con registro de posición, duración y completitud.
- 📤 **Evidencias reales**: subida de entregas (PDF, imágenes, XLSX…) con trazabilidad verificable.
- ⚖️ **Reglas transparentes**: quién califica, con qué pesos y bajo qué condiciones se certifica.
- 🏆 **Certificado verificable por curso y por aprendiz**, protegido con clave privada y nombre + cédula.
- 🔑 **Autenticación real** con perfil completo (nombre y cédula) mediante `api_me` / `PATCH /api/profile`.
- 🔊 **Guía por voz** en español (preferencia de **voz femenina**).
- 🚧 **Zona en construcción**: lo que está por llegar, sin engaños.
- 🛰 **Multi-curso adaptativo**: selector en tiempo real (el perfil se ajusta solo).
- 📟 Tres interfaces: **web** (Flask), **TUI** (Textual) y **CLI**.
- 🎛 **Dashboard pro**: desglose por componente, señales del motor (OBSERVADO/INFERIDO/PREDICHO), próximos pasos y ruta curricular.

---

## 🧰 Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3 · Flask |
| UI web | HTML · CSS · JS (SPA ligera por hash) |
| TUI | Textual |
| Datos | SQLite (`vida.db`) / PostgreSQL (Neon) + manifiestos JSON |
| Storage de evidencias | Vercel Blob (blobs `vida/evidence/…` y `vida/certificates/…`) |
| Inteligencia | Motor determinista y explicable (`IntelligenceEngine`) |
| Deploy | Vercel (`@vercel/python` → `api/index.py`) |

---

## 📂 Estructura

```
vida.py                # Núcleo: app Flask, motor, comandos CLI, API
vida_db.py             # Capa de datos (SQLite local / PostgreSQL en Neon)
vida_engines/          # Motores estables: progreso, evidencia, inteligencia,
                       #   conocimiento, curso, medios, eventos, perfil, reglas, certificado
vida_ui_pro/           # UI web profesional (dashboard pro en Vercel)
vida_core/             # UI web clásica (templates/static)
vida_ui.py             # Interfaz TUI (terminal)
api/index.py           # Punto de entrada para Vercel
data/                  # Manifiestos, perfil, reglas y base SQLite
  course.json          #   ↓ fuente de conocimiento actual
  courses/<id>.json    #   → cursos disponibles
  profiles/<id>.json   #   → pesos + componentes por curso
  registry.json        #   → curso activo
data/evidence/, data/certificates/   # Evidencias y certificados locales
media/videos/          # 🎬 Sesiones grabadas (MP4)
media/materials/       # 📚 Material de aprendizaje
docs/                  # 📖 Documentación del proyecto
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

VIDA guarda **posición, duración, porcentaje y completitud** en SQLite/Postgres.
No guarda credenciales de la plataforma del curso. La sesión del dashboard es un clip de ~12 MB.

> ⚠️ **Sobre el deploy del video:** las cinco sesiones quedaron comprimidas por debajo
> del límite de 100 MB por archivo de GitHub (dashboard ~12 MB, AA1 ~64 MB, AA2 ~81 MB,
> AA3 ~95 MB, AA4 ~90 MB). Vercel (límite de función ~250 MB) no puede servir ~340 MB
> de videos de modo fiable; para una versión completa en el servidor, múdalo a un
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
- El **certificado** se emite una sola vez por curso y por aprendiz, con reglas explícitas y verificables ante el instructor.

BLUMCL, BLUMELIX y VIDA son proyectos con responsabilidades separadas.

---

## 📖 Documentación

- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) — núcleo estable, capa adaptable, motores y flujo de datos.
- [`docs/ADAPTACION.md`](docs/ADAPTACION.md) — cómo llevar VIDA a tu próxima fuente de conocimiento.

---

## 📜 Licencia

Proyecto de **Eduar Alejandro Arias Londoño**, publicado bajo
**Apache License 2.0**. Ver [`LICENSE`](LICENSE) y [`COPYRIGHT`](COPYRIGHT)
para los términos completos.

---

## 🧪 Pruebas

```bash
source .venv/bin/activate
pytest -q
```

---

## 🏗 Hoja de ruta

- [x] Núcleo estable: progreso, evidencia, inteligencia y certificados
- [x] Capa adaptable por curso (manifiesto, perfil, reglas, registro)
- [x] UI web profesional responsive + multi-curso
- [x] Autenticación con nombre y cédula + certificado por aprendiz
- [x] Guía por voz en español (voz femenina)
- [x] Sesión grabada integrada y desplegada en Vercel
- [x] Dedicatoria especial al docente y al SENA (final del dashboard, en cursiva)
- [x] Sesiones por actividad (AA1–AA4) más video del dashboard
- [x] Evidencias AA1 en el servidor (trazables y verificables)
- [ ] Material de aprendizaje por actividad
- [ ] Evidencias AA2–AA4 en el servidor
- [ ] Certificado final emitido

🚧 *VIDA es obra viva: crece con cada sesión, cada entrega y cada concepto demostrado.* 🚧