# PRESUPUESTO DE DESPLIEGUE · VIDA (Vercel / @vercel/python)

Tamaño del artefacto que Vercel empaqueta en la lambda (los archivos del repo,
menos lo que excluye `.vercelignore`).

## Estado real (medido el 15/09/2026 · tras publicar el audio fuera de la lambda)

Desde el 15/09/2026 el audio del pódcast **deja de servirse desde la función**:
la lambda de Vercel no puede responder más de **4.5 MB** por llamada
(`FUNCTION_RESPONSE_PAYLOAD_TOO_LARGE`) y los MP3 pesan 20–38 MB. El catálogo
y el feed RSS anuncian las URLs del propio sitio (`/media/podcast/…`), que
**Vercel sirve como estáticas** con `Range` y `Content-Type: audio/mpeg`:
los MP3 viven en el bundle, pero se sirven desde el CDN estático y **nunca
pasan por la lambda** (ver ruta `/media/podcast/*` en `vercel.json`). GitHub
raw/objects no sirve (devuelve `application/octet-stream`, que Spotify
rechaza).

| Componente | Tamaño (aprox.) |
|---|---|
| `media/videos/*.mp4` (5 sesiones) | ~125 MB |
| `podcast_audio/*.mp3` (EP01–04) · **sirven como estáticos en el sitio** | ~113 MB |
| `vida_ui_pro/` (HTML/CSS/JS + portadas 1400² + thumbs + temporada) | ~2.5 MB |
| Código y manifiestos (`vida*.py`, motores, `data`, `media/materials`) | < 1 MB |
| **TOTAL** | **~243 MB decimal** (~232 MiB) |

**Límite duro de la lambda:** 250 MB (config `maxLambdaSize: "250mb"` en
`vercel.json`; `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` a nivel proyecto).

**Margen actual ≈ 7 MB decimal** (~3 %): los MP3 **deben** viajar en el bundle
porque son ellos los que el CDN estático sirve en `/media/podcast/*` con Range y
`audio/mpeg`. No se excluyen; de hacerlo, el sitio y Spotify perderían el audio.
El margen se recuperará migrando el audio a Blob/streaming (el podcast y los
vídeos salen del bundle y `maxLambdaSize` puede bajar).

## Matriz de riesgo (ISO 31000 / IEC 31010 simplificada)

| Riesgo | P | I | Respuesta |
|---|---|---|---|
| Bundle > 250 MB y el build falla | Media (margen 7 MB hoy) | Alto | Excluir `podcast_audio/*.mp3` del bundle (audio ya viene de URLs públicas); Vercel mantiene el despliegue anterior sin interrupción. |
| Cambia el plan del audio (Blob/streaming) | Baja | Medio | Actualizar la ruta `/media/podcast/*` de `vercel.json` y el helper `_podcast_audio_url()` (+ `curl -I` de verificación: `206` y `audio/mpeg`). Si nada responde, el audio deja de sonar en el sitio y en Spotify; Vercel mantiene el despliegue anterior. |
| Crecen los episodios de la Temporada 2 | Media | Medio | La regla editorial de 15–30 min + URLs públicas: cada EP ~15–30 MB fuera de la lambda. |
| Subida/commit de un archivo enorme por error | Media | Medio | `.vercelignore`/`.gitignore` protegen chunk_*, `*.db`, `.env*`, `tests/`, backups; revisar `git status` antes de cada `push`. |

## Qué se excluye del bundle (`.vercelignore`)
`chunk_*`, `concat.txt`, cachés (`*.pyc`, `__pycache__`, `.pytest_cache`),
`data/*.db`, `data/evidence|events|reports`, `certificates/*.issued.json`,
`tests/`, `.vercel`, backups locales.

## Verificación de salida (bloqueante)
1. `python3 -m pytest tests/ -q` → 54/54 ✅ (incluye test de MP3 roto y el test
   de `Content-Type: audio/mpeg` en `/media/podcast/*`).
2. Smoke local de `/api/podcast`, `/podcast.xml` (XML válido + EP04 + orden por
   num + enclosure en `/media/podcast/…`), `/vida`, portada de temporada y
   reproductores EP01/EP03/EP04 ✅.
3. `du`/medición del bundle ≤ ~223 MB ≪ 250 MB ✅.
4. Push a `main` → deploy automático; smoke remoto descrito en `BITACORA.md`
   (curl `-I` y `Range: bytes=0-99` sobre `/media/podcast/<ep>.mp3` del sitio
   publicado: `206` + `Content-Type: audio/mpeg`).

> **Plan a futuro:** cuando se migre el pod a Blob, este documento se actualiza
> y `maxLambdaSize` puede bajar sin desplegar vídeos/audios en la lambda.