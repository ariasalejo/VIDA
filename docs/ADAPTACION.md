# 🧩 Adaptar VIDA a una nueva fuente de conocimiento

> Transferencia de VIDA a otro curso: **el núcleo no se toca**, se agrega el curso.

## Cuándo usar esta guía

Cuando termines (o intercambies) tu fuente de conocimiento actual y quieras que el
Command Center mire al siguiente curso — otra materia, otro programa, otro proveedor.
VIDA cambiará **infraestructura y diseño según lo que estudies**, manteniendo el mismo
núcleo.

## Paso 0 · Concepción

Define el nuevo curso antes de tocar archivos:

- **ID corto** en minúsculas y sin espacios: `medicina_prep`, `redes_ccna`, `analisis_datos`.
- **Título, proveedor, horas, plataforma y fuente** (URL).
- **Objetivos de aprendizaje** (5–8) y **actividades** con entregable y fecha.
- **Conceptos clave** por actividad.
- **Sesiones grabadas y materiales** si los tienes.
- **Pesos** de valoración para `profile`.

## Paso 1 · Crear el manifiesto del curso

Copia `data/courses/<actual>.json` y ajusta: id, título, proveedor, plataforma,
objetivos, ítems (kind, título, brief, entregable, video, materiales, `knowledge`),
fechas `due` y la dedicación.

```bash
cp data/courses/sena_ciberseguridad.json data/courses/nuevo_curso.json
```

## Paso 2 · Crear el perfil de valoración

Copia `data/profiles/<actual>.json` y ajusta `components` y `weights` del tema nuevo:

```bash
cp data/profiles/sena_ciberseguridad.json data/profiles/nuevo_curso.json
```

Reglas prácticas de pesos: `activity` y `mastery` deben sumar la mayor parte;
`evidence` refleja cuánto exige demostrar tu programa.

## Paso 3 · Registrar el curso

En `data/registry.json`, agrega el id nuevo a `courses` y activa el que quieras ver:

```json
{ "active": "nuevo_curso", "courses": [ "sena_ciberseguridad", "nuevo_curso" ] }
```

El dashboard muestra un **selector multi-curso** en tiempo real; los perfiles se
ajustan automáticamente.

## Paso 4 · Ajustar reglas (si hace falta)

`data/rules.json` declara la política de certificación. El núcleo evalúa condiciones
como `operational_progress == 100`, `evidence_count > 0`, `unknown_required == 0` y
`user_confirmation == true`. Cambia solo lo que tu nuevo programa exige de forma
distinta; el patrón del archivo se conserva.

## Paso 5 · Evidencias y certificados

- Evidencias nuevas se guardan bajo `vida/evidence/<user>/<curso>/` con **trazabilidad
  y verificación** automáticas (ver `docs/ARQUITECTURA.md`, sección 5).
- El **certificado es por curso y por aprendiz**: emitir uno no bloquea a otro curso, y
  cada aprendiz recibe el suyo con nombre y cédula.

## Paso 6 · Videos y materiales

- Coloca los MP4 en `media/videos/` y referencia el `file` en `items[].video`
  (ver README, sección *Sesiones grabadas*).
- Materiales de estudio van a `media/materials/` (el servidor los sirve localmente).

## Paso 7 · Verificar

```bash
python -m pytest -q
python vida.py web   # revisa el dashboard del nuevo curso
```

## Qué NO cambia

- Los motores de `vida_engines/` (núcleo).
- La política de evidencia honesta (no adivinar, no inventar).
- Las interfaces web / TUI / CLI y el flujo del dashboard.
- La base de datos y el despliegue en Vercel.

Si un curso necesita una *capacidad nueva* (un tipo de ítem distinto, una métrica
extra), se implementa en el **núcleo** como mejora de profundidad, nunca como una
versión paralela: **el núcleo no varía, solo se mejora en profundidad**.