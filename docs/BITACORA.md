# BITÁCORA · Cierre Temporada 1 → despliegue público

Sesión del **14/09/2026** (aprox. continua desde el 13/09). Cada cambio queda
registrado en `git log`; este documento resume el *porqué*.

## Lo que ya estaba hecho y se valida
- Temporada 1 del canal «BLUMIX · Las Voces del Código»: EP01, EP02 (guion),
  EP03 y EP04, con `PODCAST_META`, numeración por `num` y slots.
- NEXUS con carpeta de temporada, portadas reales por episodio, reproductores.
- Centro de evidencias con tarjeta de pódcast EP01, filtro `PODCAST_LISTEN` y
  estilos `ev-podcast-card` / `pod-season`.
- Certificado con impresión a una página (198 mm) en `style_cert.css`.
- Portadas y thumbs regeneradas con la marca de temporada.

## Cambios de esta sesión (para «terminar y desplegar con excelencia»)

1. **Radio del error acotado (vida.py)**
   - Helper `_podcast_ep_entry`: un MP3 ilegible / de 0 bytes se **omite** en el
     catálogo y en el feed RSS en vez de tumbar el endpoint (el poke de un solo
     archivo ya no derriba la casa). `skipped_unreadable` informa el descarte.
   - `/api/podcast/evidence` tolera payloads malformados con `400` en lugar de
     500, y parsea `completed` como booleano estricto (evita `bool("false")`).
2. **Audio EP04 publicado** (`podcast_camino_principiante_1h.mp3`, Kimi, ~28 min).
3. **Presupuesto de despliegue saneado:** los MP3 se re-encodearon de 128 a
   96 kbps mono (44100 Hz, duraciones idénticas). Bundle ≈ **255 MB → ~223 MB**
   decimal: por fin margen real bajo el tope de 250 MB de la lambda. Véase
   `PRESUPUESTO_DEPLOY.md`.
4. **Pruebas nuevas (47 → 52):**
   - catálogo ordenado por `num` + metadatos de temporada;
   - ciclo de vida de `POST /api/podcast/evidence` (201 / ya / 202 / 404,
     idempotencia y grupo `podcast` en `/api/evidence`);
   - payload inválido → 400;
   - feed RSS bien formado con campos iTunes;
   - **contención**: MP3 de 0 bytes no rompe ni catálogo ni feed.
5. **Privacidad en sitio público (permitido: acceso público en producción):**
   - el SSO de Vercel bloqueaba el feed RSS/audio públicos (Spotify/Apple/YouTube
     no podrían jalarlos). El usuario aprobó abrir producción (`ssoProtection=null`);
   - ese cambio obligó a verificar el perímetro: `/api/evidence` y
     `/media/evidence/*` ahora exigen cuenta (401) — datos personales a salvo.
     Material y videos de curso siguen públicos por diseño.
   - Pruebas: 47 → 53.
6. **Sin repetición de pódcast en el curso:** por decisión del usuario, cada
   episodio aparece en un único lugar:
   - la tarjeta genérica «Súper IAs en acción» del dashboard se eliminó
     (duplicaba el portal); la escucha vive en **VIDA · NEXUS** (`/vida`);
   - el portal oculta el episodio de evidencia (EP 01) para que no se repita
     con su tarjeta de evidencia; EP 01 aparece solo en el centro de evidencias.
7. **Registro en Spotify/YouTube:** al validar el feed con Spotify for Creators
   salía un error de procesamiento. Causa raíz: las duraciones del feed se
   estimaban con una fórmula que asumía 128 kbps, pero el audio va a 96 kbps
   mono → <itunes:duration> quedaba ~25 % corto. Ahora la duración real se lee
   del MP3 (mutagen) y el feed emite los segundos exactos (53:16, 52:16 y
   27:53). El feed vive en una URL estable por proyecto (no por deploy).
5. **Documentación nueva:** `docs/ESTANDARES.md`, `docs/CANAL_PODCAST.md`,
   `docs/ERRORES_Y_CORRECCIONES.txt` y `docs/PRESUPUESTO_DEPLOY.md`.
6. **README:** sección «Estándares y marco normativo» + `docs/` en la
   estructura + actualizaciones honestas del pódcast.
7. **Pie del dashboard:** línea discreta de estándares
   (ISO/IEC 27001 · Ley 1581/2012 · NIST CSF).

## Verificación antes de salir al público
- `python3 -m pytest tests/ -q` → 52/52 ✅.
- Smoke local de `GET /api/podcast`, `GET /podcast.xml` (XML válido y con
  EP04), `GET /vida`, `GET /static/covers/seasons/temporada_1.png` y el EP04
  ✅.
- Smoke remoto en Vercel tras el push (plan: home, `/vida`, `/api/podcast`,
  `/podcast.xml`, portadas y reproductores EP01/EP03/EP04).

## Gobernanza
- Tag de rollback: `v0.9-pre-temporada-1` (creado antes de esta entrega).
- Tag de referencia post-deploy: `v1.0-temporada-1-baseline`.

---

# Sesión · 15/09/2026 · Audio público con Range + curso Linux activo en deploy

## Problemas reportados
1. **Los audios del pódcast no suenan** («error») en el sitio publicado y en
   Spotify: los reproductores y el rastreador de Spotify no podían descargar
   los MP3.
2. **Curso Linux «trocado» respecto al selector junto al reloj**: en producción
   el curso activo seguía siendo Ciberseguridad (el cambio a `sena_linux` solo
   existía en el `data/registry.json` local, sin commit), mientras que el curso
   Linux aparecía «EN COLECCIÓN» en NEXUS.

## Causa raíz (verificada, no asumida)
- **Audio:** Vercel Functions limita la respuesta a **4.5 MB**
  (`FUNCTION_RESPONSE_PAYLOAD_TOO_LARGE`). Los MP3 finales pesan 20–38 MB, así
  que `GET /media/podcast/*.mp3` fallaba en producción (en local todo funcionaba:
  `54/54` pruebas y Range 206). Se confirmó con la documentación de Vercel y con
  smoke local.
- **Linux:** `data/registry.json` (trackeado) tenía `active: sena_linux` solo en
  local; cada deploy copia el archivo commiteado → producción seguía con
  `sena_ciberseguridad`.

## Solución aplicada
1. **Audio publicado fuera de la lambda**: los MP3 ya estaban en GitHub (repo
   `ariasalejo/VIDA`). Los `enclosure`/`guid` del feed RSS y el campo `file` del
   catálogo `/api/podcast` ahora apuntan a URLs públicas estables con Range
   (verificadas `206` para los 4 episodios); el catálogo conserva `local_file`
   (`/media/podcast/…`) como respaldo en desarrollo. Nuevo helper
   `_podcast_audio_url()` y diccionario `PODCAST_AUDIO_URLS` en `vida.py`. Los
   MP3 siguen viajando en el bundle esta vez como **red de seguridad**; el paso
   siguiente es excluirlos en `.vercelignore` (ver `PRESUPUESTO_DEPLOY.md`).
2. **Curso Linux activo en producción**: se versiona `data/registry.json` con
   `active: sena_linux` y se despliega; el selector junto al reloj y la NEXUS
   mostrarán Linux como **● ACTIVO**.
3. **Documentación** (`CANAL_PODCAST.md`, `PRESUPUESTO_DEPLOY.md`, `README.md`)
   actualizada al nuevo modelo de publicación de audio.

## Verificación
- `python3 -m pytest tests/ -q` → **54/54** ✅ (incl. contenedor de catálogo/feed,
  `local_file` de respaldo y el Range local).
- Smoke local de `/api/podcast` (4 episodios con URL pública) y `/podcast.xml`
  (enclosure + guid con las URLs públicas) ✅.
- `curl -H "Range: bytes=0-99"` contra cada URL pública → `206` ✅.
- Smoke remoto (plan): en el sitio publicado los 4 reproductores (EV EP01 +
  NEXUS) suenan; en Spotify for Creators > contenido los 4 episodios dejan de
  marcar error; selector de curso junto al reloj y NEXUS muestran Linux ACTIVO.

---

# Sesión · 16/09/2026 · Spotify rechazaba el audio por `application/octet-stream`

## Problema reportado
Los 4 episodios siguen marcando **error** en Spotify («ningún pódcast suena»),
aunque en el sitio los reproductores y el feed ya usaban URLs públicas con Range.

## Causa raíz (verificada, no asumida)
GitHub raw/objects sí responde `206` con `Range`, pero sirve el MP3 como
**`Content-Type: application/octet-stream`** (verificado con `curl -I` sobre
`raw.githubusercontent.com/ariasalejo/VIDA/main/podcast_audio/<ep>.mp3`).
**Spotify no reproduce audio con ese tipo MIME**; por eso cada episodio marcaba
error aunque el feed y el rango estaban bien.

## Solución aplicada
1. **El audio se sirve desde el propio sitio**, no desde GitHub:
   - `vercel.json`: nueva ruta **estática** `/media/podcast/*` → archivos de
     `podcast_audio/` (Vercel las sirve desde el CDN con `Range` y
     `Content-Type: audio/mpeg`, **sin pasar por la lambda**, así que el tope de
     4.5 MB ni se entera). En los builds legacy hace falta **registrar el
     archivo como estático** con el builder `@vercel/static`
     (`podcast_audio/podcast_*.mp3`); la primera verificación en producción dio
     `404` justo por eso (solo la ruta no publica el asset).
   - `vida.py`: se elimina `PODCAST_AUDIO_URLS` (GitHub raw); el helper
     `_podcast_audio_url()` ahora devuelve `{base}/media/podcast/<stem>.mp3`
     absoluta; el catálogo `/api/podcast` y el contexto de evidencia la
     construyen con `_site_url()`; CSP `media-src` pasa a `'self' blob:`.
2. **Tests actualizados (siguen 54/54):** el catálogo/feed deben exponer URLs del
   propio sitio (`/media/podcast/…`) y `/media/podcast/*` debe responder
   `Content-Type: audio/mpeg` además del `206` de Range.
3. **Docs** (`README.md`, `CANAL_PODCAST.md`, `PRESUPUESTO_DEPLOY.md`):
   el modelo de audio pasa de «URLs públicas externas» a «estáticos del sitio».

## Verificación
- `python3 -m pytest tests/ -q` → **54/54** ✅ (incluye test de `audio/mpeg`).
- Smoke local de `/api/podcast` (4 episodios con URL del sitio, `audio/mpeg`) y
  `/podcast.xml` (enclosure + guid en `/media/podcast/…`) ✅.
- Smoke remoto: `curl` con `Range: bytes=0-99` sobre los **4**
  `/media/podcast/<ep>.mp3` del sitio publicado → **`206` +
  `Content-Type: audio/mpeg`** para todos ✅ (tamaños reales: 38.4 / 20.5 / 37.6 /
  20.1 MB). /podcast.xml anuncia los 4 enclosures en `/media/podcast/…` ✅.
  El cambio de `guid`/`enclosure` fuerza la re-ingesta en Spotify for Creators.