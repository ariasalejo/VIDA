# 🏗 Arquitectura de VIDA

> Documento de proyecto · VIDA · Learning Command Center

## 1. Visión general

VIDA es un **Command Center Learning**: una plataforma cuyo comportamiento se describe
como un *núcleo estable* rodeado de una *capa adaptable*. El núcleo implementa la
ética del motor — *solo se registra lo que se demuestra* — y la capa describe a qué
se aplica (el curso o fuente de conocimiento actual).

```
┌──────────────────────────────────────────────────────────────┐
│                    CAPA ADAPTABLE (por curso)                  │
│   data/course.json  ·  data/courses/<id>.json                  │
│   data/profiles/<id>.json  ·  data/rules.json  ·  registry      │
│   materials / videos / fechas / identidad del aprendiz          │
├──────────────────────────────────────────────────────────────┤
│                      NÚCLEO ESTABLE (motores)                  │
│   curso · progreso · conocimiento · evidencia · inteligencia    │
│   medios · eventos · reglas · perfil · certificado              │
├──────────────────────────────────────────────────────────────┤
│              INTERFACES (no cambia la lógica)                  │
│   web (vida_ui_pro) · TUI (vida_ui) · CLI (vida.py)            │
└──────────────────────────────────────────────────────────────┘
```

## 2. Núcleo estable

Los **motores** en `vida_engines/` son independientes del curso; solo reciben datos:

| Motor | Responsabilidad |
|---|---|
| `course_engine` | Lee el manifiesto del curso, expone ítems, objetivos y videos |
| `progress_engine` | Progreso operativo ponderado por componente |
| `knowledge_engine` | Conceptos, verificación y retención (Knowledge Checks + reintento) |
| `evidence_engine` | Registro de evidencias observadas con trazabilidad y recuento Blob-aware |
| `intelligence_engine` | Distingue señales OBSERVADO / INFERIDO / PREDICHO |
| `media_engine` | Reproducción de sesiones, posición, duración y completitud |
| `event_engine` | Registro y lectura de eventos de aprendizaje |
| `rule_engine` | Aplica las reglas declarativas del curso |
| `profile_engine` | Pesos y componentes del curso |
| `certificate_engine` | Emisión única por curso y por aprendiz (nombre + cédula) |

## 3. Capa adaptable

Todo lo que cambia cuando se estudia otra cosa vive en `data/` como **manifiestos JSON**:

| Archivo | Contenido | Rol |
|---|---|---|
| `data/course.json` | ítems, videos, materiales, fechas | fuente de conocimiento activo |
| `data/courses/<id>.json` | manifiesto completo por curso | catálogo de cursos |
| `data/profiles/<id>.json` | pesos y componentes (`video`, `activity`, `mastery`, `evidence`) | cómo se valora |
| `data/rules.json` | principios + política de certificación + reglas | qué se exige |
| `data/registry.json` | curso activo | selector multi-curso |

## 4. Persistencia y despliegue

- **Local:** SQLite `data/vida.db` + carpetas `data/evidence/`, `data/certificates/`.
- **Producción (Vercel + Neon):** PostgreSQL remoto; las **evidencias y certificados**
  se guardan en **Vercel Blob** bajo `vida/evidence/<user>/<course>/<aa>/…` y
  `vida/certificates/<user>/<course>.issued.json`.
- **API de entrada:** `api/index.py` → `vida.create_app()` (`vercel.json`).

> ⚠️ Nota técnica: con `vercel>=0.10`, `get_blob` devuelve `GetBlobResult.content`
> (bytes), no `stream`. `vida.py` lo normaliza vía `_blob_body()` para soportar
> ambas versiones del SDK.

## 5. Flujo de datos (evidencia)

```
Aprendiz sube entrega → evidencia_engine
   → se guarda en Blob (producción) o `data/evidence/` (local)
   → evento ACTIVITY_COMPLETE (OBSERVED, DELIVERED)
   → intelligence_engine clasifica OBSERVADO / INFERIDO / PREDICHO
   → progress_engine pondera con el perfil del curso
   → si se cumplen todas las condiciones → certificate_engine (emisión única)
```

## 6. Principios que nunca cambian

1. **NO_GUESSING** — nada se asume.
2. **NO_INVENTED_EVIDENCE** — la evidencia se observa, no se fabrica.
3. **OBSERVATION_SEPARATE_FROM_INTERPRETATION** — ver el video no es dominio.
4. **MISSING_DATA_IS_UNKNOWN** — lo que falta es desconocido.
5. **CERTIFICATE_IS_ISSUED_ONCE_PER_COURSE** — por curso y por aprendiz.
6. **USER_CONFIRMATION_IS_FINAL** — el aprendiz confirma antes de certificar.

## 7. Documentos relacionados

- [`ADAPTACION.md`](ADAPTACION.md) — cómo agregar la siguiente fuente de conocimiento.
- `README.md` — visión, características y arranque.