# CANAL DE PÓDCAST · «BLUMIX · Las Voces del Código»

Canal seguro de estudio del curso SENA **«Apropiación de los Conceptos en
Ciberseguridad»**. Acompaña a El Aprendiz desde cero, sin humo: ciberseguridad
y programación contadas por BLUMIX y las súper IAs.

- **Serie:** `BLUMIX · Las Voces del Código`
- **Temporada:** 1
- **Propietario del feed (owner email):** `PODCAST_OWNER_EMAIL` en `vida.py`
- **Feed RSS:** `GET /podcast.xml` (RSS 2.0 + iTunes, listo para Spotify,
  Apple Podcasts y YouTube).
- **Catálogo JSON:** `GET /api/podcast` (ordena por **número real**, nunca por
  posición en la lista).

## Episodios · Temporada 1

| EP | Key (slug) | Título | Slot | Voz(es) | Duración | Audio |
|---|---|---|---|---|---|---|
| 01 | `podcast_ciberseguridad_1h` | Ciberseguridad y Código · Tu primera zancada | `evidence` | Salomé (es-CO) | ~53 min | ✅ publicado |
| 02 | `podcast_capitulo2_1h` | Tu castillo, tu llave y los anzuelos invisibles | `dashboard` | Gonzalo (es-CO) | — | ⏳ guion listo, audio pendiente |
| 03 | `podcast_superias_1h` | Secretos de la programación y las IAs | `dashboard` | BLUMIX (es-CO) · OpenCode (es-MX) | ~52 min | ✅ publicado |
| 04 | `podcast_camino_principiante_1h` | El camino del principiante | `dashboard` | Kimi (es-CO) | ~28 min | ✅ publicado |

- **`slot = dashboard`**: aparece en el centro de mando y en la NEXUS.
- **`slot = evidence`**: aparece como **pódcast de evidencia** (escuchar ≥ 95 %
  lo registra como observación verificable).

## Reglas de producción (editorial y técnica)

1. **Formato:** guion en `podcast_guion_*.md` con marcadores `**HABLANTE:**`
   y tabla de conteo de palabras/intervenciones al pie.
2. **Duración ideal 15–30 min.** Los episodios largos de estudio (~50 min de la
   temporada 1) se aceptan por ser material de repaso tipo clase, con ritmo
   sostenido; el objetivo de la temporada 2 es recortar.
3. **Voces:** español neutro cercano (`es-CO` preferido; invitados pueden ser
   `es-MX`), ritmo calmado, **voz femenina por defecto** cuando exista.
4. **Calidad de audio:** MP3 mono 44.1 kHz. Se bajó a **96 kbps** para mantener
   el bundle de despliegue bajo el tope de 250 MB de la lambda (ver
   `PRESUPUESTO_DEPLOY.md`); la pérdida es inaudible para narración.
5. **Arte:** portada cuadrada 1400×1400 (`tools/make_covers.py`), thumb 1280×720
   (`tools/make_thumb.py`) y portada/meta de temporada en
   `covers/seasons/temporada_1.png`.
6. **Numeración:** el número del episodio vive en `PODCAST_META[slug]["num"]`.
   Nunca se deriva del índice de la lista.
7. **Chunks intermedios:** no se versionan ni se despliegan
   (`.vercelignore` y `.gitignore`).

## Evidencia verificable de escucha

`POST /api/podcast/evidence` registra un evento **`PODCAST_LISTEN`** (resultado
**`VERIFIED_LISTEN`**) en el expediente **una sola vez por episodio** y solo cuando:

- el audio existe y el episodio es reconocido por su `num`;
- el aprendiz completó **≥ 95 %** de la reproducción (lo manda el reproductor
  `app_pro.js` con `completed: true` o se calcula de `position/duration`).

Reglas de respuesta (radio de error acotado):

| Caso | HTTP |
|---|---|
| Sin sesión | 401 |
| Episodio no reconocido | 404 |
| Audio no disponible | 404 |
| Payload inválido (`position`/`duration` no numéricos) | 400 |
| Escucha incompleta (< 95 %) | 202 |
| Registrado por primera vez | 201 |
| Ya registrado (idempotente) | 200 + `already: true` |

El front-end degrada con gracia: si el catálogo falla, las tarjetas se
esconden en vez de romper el dashboard (`try/catch` en `app_pro.js`).

## Promoción y directorios

- Página propia del canal: `/vida` (botón «⚡ ENTRAR A VIDA · NEXUS»).
- Botones **ESCÚCHALO EN** Spotify / Apple / YouTube enlazados al feed RSS.
- `itunes:season`, `itunes:episode`, `itunes:series` y `itunes:episodeType`
  presentes en cada `<item>`.