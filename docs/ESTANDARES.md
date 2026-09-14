# ESTÁNDARES · VIDA

> **Advertencia honesta:** VIDA es un proyecto de aprendizaje. Este documento
> describe las **intenciones de diseño** y su **mapeo** a marcos normativos y
> buenas prácticas. **No reclama certificaciones** (ISO, NIST ni ninguna otra)
> sobre la solución: el mapeo es de *referencia y trazabilidad*, no de
> conformidad auditada.

| Marco | Uso en VIDA | Dónde se ve |
|---|---|---|
| **ISO/IEC 27000:2018** | Vocabulario común: activos, vulnerabilidad, riesgo, control, evaluación de riesgos. VIDA lo usa literal (los conceptos del curso). | `data/course.json`, guiones y evidencia |
| **ISO/IEC 27001:2022** | Mentalidad de gestión de riesgos: solo se registra lo observado; las predicciones nunca se vuelven hechos. | `vida_engines/intelligence_engine.py` |
| **ISO/IEC 27002:2022** | Controles de referencia: resguardo de acceso (cuentas con hash), cifrado en reposo, registro (auditoría de evidencia), gestión de sesiones. | `vida_secret.py` (cifrado), `vida_store.py` (accounts), `vida_engines/evidence_engine.py` |
| **ISO 31000:2018 + IEC 31010** | Matriz de riesgo en el material AA3 y en el presupuesto de despliegue (probabilidad × impacto). | `docs/PRESUPUESTO_DEPLOY.md`, `media/materials/aa3_guia.html` |
| **NIST CSF 2.0** | Funciones Gobernar · Identificar · Proteger · Detectar · Responder · Recuperar aplicadas al proyecto y al curso. | README, hoja de ruta |
| **Ley 1581/2012 + Decreto 1377/2013** | Tratamiento de datos personales: no se publican ni el nombre del instructor ni claves; mínimo de datos; el expediente es del propio aprendiz. | README «🔑 Clave del certificado», `.gitignore` |
| **CONPES 3995/2020** | Política nacional de confianza digital y ciberseguridad: contexto colombiano del aprendizaje. | Guiones del pódcast y `docs/CANAL_PODCAST.md` |
| **Grado de seguridad (app)** | Headers (`nosniff`, `DENY`, CSP, Referrer-Policy), `secrets.compare_digest`, claves separadas por entorno, `.env*` y bases nunca versionadas. | `vida.py`, `.gitignore`, `.vercelignore` |

## Principios que el equipo se compromete a sostener

1. **La evidencia observada es la única que alimenta el progreso.**
   El motor no adivina: OBSERVADO ≠ INFERIDO ≠ PREDICHO.
2. **Radio de daño acotado:** un archivo roto no tumba el catálogo ni el feed
   público; un payload inválido devuelve `4xx`, nunca un 500 general.
3. **Privacidad por diseño:** secretos y datos personales fuera del repo.
4. **Reversibilidad:** cada entrega a producción tiene un tag/rollback definido
   antes de salir (ver `docs/BITACORA.md`).

## Dudas razonables (declaración de límites)

- El cifrado en reposo usa `cryptography.Fernet` con clave maestra por entorno;
  es un control de la capa de datos, no una certificación.
- El mapeo a normativas se actualiza con el curso; si una norma cambia, este
  documento debe revisarse antes de afirmar conformidad.