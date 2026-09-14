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