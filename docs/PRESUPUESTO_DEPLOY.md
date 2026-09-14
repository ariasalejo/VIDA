# PRESUPUESTO DE DESPLIEGUE · VIDA (Vercel / @vercel/python)

Tamaño del artefacto que Vercel empaqueta en la lambda (los archivos del repo,
menos lo que excluye `.vercelignore`).

## Estado real (medido el 14/09/2026)

| Componente | Tamaño (aprox.) |
|---|---|
| `media/videos/*.mp4` (5 sesiones, ya muy comprimidas) | ~125 MB |
| `podcast_audio/*.mp3` (EP01 + EP03 + EP04) | ~96 MB |
| `vida_ui_pro/` (HTML/CSS/JS + portadas 1400² + thumbs + temporada) | ~2.5 MB |
| Código y manifiestos (`vida*.py`, motores, `data`, `media/materials`) | < 1 MB |
| **TOTAL** | **~223 MB decimal** (~213 MiB) |

**Límite duro de la lambda:** 250 MB (config `maxLambdaSize: "250mb"` en
`vercel.json`; `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` a nivel proyecto).

**Margen actual ≈ 27 MB decimal** (~11 %). ¿Por qué no se quedó en 255 MB?
El re-encode a **96 kbps mono** de los tres MP3 (128 → 96, duración intacta)
quitó ~32 MB; la caída es inaudible en narración.

## Matriz de riesgo (ISO 31000 / IEC 31010 simplificada)

| Riesgo | P | I | Respuesta |
|---|---|---|---|
| Bundle > 250 MB y el build falla | Baja (hay medición) | Alto | Vercel mantiene el despliegue anterior (sin interrupción); rollback a tag `v0.9-pre-temporada-1` y/o `git revert`. |
| Tope cambia a 250 MB estricto por cuenta | Media | Alto | Migrar MP3/MP4 a **Vercel Blob** (el token `BLOB_READ_WRITE_TOKEN` ya existe en el proyecto), dejando ~3 MB de bundle. |
| Crecen los episodios de la Temporada 2 | Media | Medio | La regla editorial de 15–30 min + Blob: cada EP ~15–30 MB, presupuesto no escala indefinidamente. |
| Subida/commit de un archivo enorme por error | Media | Medio | `.vercelignore`/`.gitignore` protegen chunk_*, `*.db`, `.env*`, `tests/`, backups; revisar `git status` antes de cada `push`. |

## Qué se excluye del bundle (`.vercelignore`)
`chunk_*`, `concat.txt`, cachés (`*.pyc`, `__pycache__`, `.pytest_cache`),
`data/*.db`, `data/evidence|events|reports`, `certificates/*.issued.json`,
`tests/`, `.vercel`, backups locales.

## Verificación de salida (bloqueante)
1. `python3 -m pytest tests/ -q` → 52/52 ✅ (incluye test de MP3 roto).
2. Smoke local de `/api/podcast`, `/podcast.xml` (XML válido + EP04 + orden por
   num), `/vida`, portada de temporada y reproductores EP01/EP03/EP04 ✅.
3. `du`/medición del bundle ≤ ~223 MB ≪ 250 MB ✅.
4. Push a `main` → deploy automático; smoke remoto descrito en `BITACORA.md`.

> **Plan a futuro:** cuando se migre el pod a Blob, este documento se actualiza
> y `maxLambdaSize` puede bajar sin desplegar vídeos/audios en la lambda.