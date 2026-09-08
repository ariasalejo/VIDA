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
| 🧑🏫 **Instructor** | Libardo Antonio Contreras |
| 🏛 **Institución** | SENA · Zajuna |
| ⏱ **Horas** | 48 |
| 🏆 **Clave del certificado** | `1035868489` |
| 🌐 **Fuente del curso** | [zajuna.sena.edu.co](https://zajuna.sena.edu.co/) |

> 💛 *A Libardo Antonio Contreras, mi instructor y guía, por acompañarme en este primer logro educativo de muchos que vienen.*

---

## 🚀 Características

- 📈 **Progreso operativo** ponderado: actividades, sesiones grabadas y conceptos.
- 🧠 **Intelligence Engine**: señales observadas vs. inferidas vs. predichas (sin inventar evidencia).
- 🎬 **Media Engine**: reproducción de sesiones sincrónicas con registro de posición, duración y completitud.
- 📤 **Evidencias reales**: subida de entregas (PDF, imágenes, XLSX…) con trazabilidad verificable.
- ⚖️ **Reglas transparentes**: quién califica, con qué pesos y bajo qué condiciones se certifica.
- 🏆 **Certificado verificable**, protegido con clave (`1035868489`).
- 🔊 **Guía por voz** en español (preferencia de **voz femenina**).
- 🚧 **Zona en construcción**: lo que está por llegar, sin engaños.
- 🛰 **Multi-curso adaptativo**: selector en tiempo real (el perfil se ajusta solo).
- 📟 Tres interfaces: **web** (Flask), **TUI** (Textual) y **CLI**.

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

Coloca el MP4 de la sesión en `media/videos/` y regístralo en `data/course.json`:

```json
{ "id": "video_und_bien", "title": "Und Bien", "file": "media/videos/Und_Bien.mp4", "required": false }
```

VIDA guarda **posición, duración, porcentaje y completitud** en SQLite.
No guarda credenciales de Zajuna. La sesión actual ya vive en `media/videos/Und_Bien.mp4` y se despliega a Vercel.

> ⚠️ **Sobre el deploy del video:** es un archivo de ~64 MB y se sirve a través de la función
> de Python. La reproducción funciona, pero en planes gratuitos de Vercel puede tardar en el
> primer arranque. Para una versión ultrarrápida, múdalo a un bucket/streaming y cambia `file`
> por una URL pública (`https://…/sesion01.mp4`).

---

## 🔑 Clave del certificado

El certificado y los cambios de curso están protegidos. La clave del sistema es:

```
1035868489
```

Se puede sobrescribir con la variable de entorno `VIDA_CERT_KEY`.
La primera vez se escribe en `data/.cert_token` (local); en el deploy se usa el valor por defecto.

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
- [ ] Material de aprendizaje por actividad
- [ ] Más sesiones grabadas (AA2–AA4)
- [ ] Certificado final emitido

🚧 *VIDA es obra viva: crece con cada sesión, cada entrega y cada concepto demostrado.* 🚧