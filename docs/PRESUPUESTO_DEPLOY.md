# PRESUPUESTO DE DESPLIEGUE · VIDA (Vercel / @vercel/python)

Tamaño del artefacto que Vercel empaqueta en la lambda (los archivos del repo,
menos lo que excluye `.vercelignore`).

## Estado real (medido el 15/09/2026 · tras publicar el audio fuera de la lambda)

Desde el 15/09/2026 el audio del pódcast **deja de servirse desde la función**:
la lambda de Vercel no puede responder más de **4.5 MB** por llamada
(`FUNCTION_RESPONSE_PAYLOAD_TOO_LARGE`) y los MP3 pesan 20–38 MB. El catálogo
y el feed RSS anuncian **URLs públicas con Range** (`PODCAST_AUDIO_URLS` en
`vida.py`, hoy GitHub raw/objects).

| Componente | Tamaño (aprox.) |
|---|---|
| `media/videos/*.mp4` (5 sesiones) | ~125 MB |
| `podcast_audio/*.mp3` (EP01–04) · **solo respaldo** | ~113 MB |
| `vida_ui_pro/` (HTML/CSS/JS + portadas 1400² + thumbs + temporada) | ~2.5 MB |
| Código y manifiestos (`vida*.py`, motores, `data`, `media/materials`) | < 1 MB |
| **TOTAL** | **~243 MB decimal** (~232 MiB) |

**Límite duro de la lambda:** 250 MB (config `maxLambdaSize: "250mb"` en
`vercel.json`; `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` a nivel proyecto).

**Margen actual ≈ 7 MB decimal** (~3 %): los MP3 todavía viajan en el bundle
como **red de seguridad** por si una URL pública fallara. Una vez confirmado el
despliegue (los 4 episodios suenan en el sitio y en Spotify), el paso siguiente
es **excluir `podcast_audio/*.mp3` en `.vercelignore`** para bajar a ~130 MB,
recuperar más del 50 % de margen y acelerar los cold starts.

## Matriz de riesgo (ISO 31000 / IEC 31010 simplificada)

| Riesgo | P | I | Respuesta |
|---|---|---|---|
| Bundle > 250 MB y el build falla | Media (margen 7 MB hoy) | Alto | Excluir `podcast_audio/*.mp3` del bundle (audio ya viene de URLs públicas); Vercel mantiene el despliegue anterior sin interrupción. |
| Cambia la URL pública del audio (upload a hosting) | Baja | Medio | Actualizar `PODCAST_AUDIO_URLS` (+ `curl -I` de verificación). Si nada responde, `local_file`/`/media/podcast` funcionan en local. |
| Crecen los episodios de la Temporada 2 | Media | Medio | La regla editorial de 15–30 min + URLs públicas: cada EP ~15–30 MB fuera de la lambda. |
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