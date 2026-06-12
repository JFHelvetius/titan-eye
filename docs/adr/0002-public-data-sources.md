# ADR-0002: Fuentes públicas por dominio y contrato de procedencia

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P7, P9), ADR-0001, ADR-0005

---

## Contexto

P7 exige que toda capacidad central sea reproducible con fuentes públicas, y prohíbe categóricamente fuentes clasificadas o filtradas. P9 exige distinguir observado/afirmado/inferido. Este ADR fija **qué fuentes** sostienen cada dominio y **qué contrato de procedencia** debe cumplir cada adaptador de ingestión.

## Decisión

### Fuentes primarias por dominio

| Dominio | Fuente primaria pública | Naturaleza del dato (P9) | Notas de TOS |
|---------|-------------------------|--------------------------|--------------|
| **Orbital** | CelesTrak (TLE/GP); Space-Track (opt-in con cuenta gratuita) | `observed` (catálogo derivado de sensores públicos USSF) | CelesTrak sin auth; Space-Track requiere cuenta y limita rate. |
| **Aerial** | OpenSky Network (ADS-B) | `observed` (posición declarada por el transpondedor de la aeronave) | API pública con rate limit; cuenta gratuita amplía. Uso no comercial por defecto. |
| **Suborbital** | NOTAMs públicos, avisos de zona marítima cerrada, comunicados oficiales, reportes de apogeo/alcance | `asserted` (reporte) → `inferred` (trayectoria reconstruida por Titan Eye) | Sin fuente única; agregación documentada por evento. |
| **Surface** | ACLED (Armed Conflict Location & Event Data); GDELT como complemento | `asserted` (evento reportado por un tercero) | ACLED requiere registro y atribución; términos de uso académico/no comercial. |

**Ninguna fuente clasificada, filtrada o de inteligencia restringida entra jamás (ADR-0000 P7, corolario duro).** Si un dato no es accesible legalmente por un nuevo usuario sin firmar acuerdos de confidencialidad, no pertenece al proyecto.

### Contrato de procedencia del adaptador

Todo adaptador de fuente en `ingestion/sources/` produce un `RawArtifact` que registra, como mínimo:

- `source_id` — identificador estable de la fuente (p. ej. `celestrak.gp`, `opensky.states`, `acled.events`).
- `request_url` y parámetros de consulta (sin secretos).
- `fetched_at` — timestamp UTC de la adquisición.
- `payload` — los **bytes exactos** recibidos.
- `content_hash` — SHA-256 de `payload` (ADR-0005).
- `epistemic_label` por defecto del dominio (`observed`/`asserted`), propagado a la capa Normalized (P9).
- `license_note` — condición de uso/atribución de la fuente, para que el output la respete.

El adaptador **no interpreta** el payload; solo lo adquiere y lo sella. La interpretación es trabajo de la capa Normalized (ADR-0001).

### Política cache-first

Toda adquisición pasa por una cache content-addressable (ADR-0005): si los mismos bytes ya existen por hash, no se vuelve a pedir. `max_age` configurable por fuente (las posiciones ADS-B caducan en segundos; un TLE, en horas; un evento ACLED es histórico e inmutable).

## Justificación

- **P7 por construcción:** la tabla de fuentes es la lista blanca. Añadir una fuente es un cambio de ADR, no un commit silencioso.
- **P9 por construcción:** la etiqueta epistémica nace en la ingestión y viaja con el dato. Imposible "ascender" un `asserted` a `observed` sin un cambio visible.
- **Cumplimiento de TOS (ADR-0000):** la `license_note` por fuente hace que la atribución y las restricciones no comerciales sean datos, no buenas intenciones.

## Consecuencias

**Positivas** — lista blanca auditable; procedencia y licencia como datos de primera clase.
**Negativas** — el dominio suborbital no tiene fuente única; cada evento exige documentar su agregación. Aceptado: es honesto sobre la naturaleza del dato.
**Neutras** — algunas fuentes (OpenSky, ACLED) requieren cuenta gratuita; se gestiona como secreto opcional (ADR-0012 planificado), nunca como dependencia dura de P3.

## Alternativas consideradas

### A. Scraping de FlightRadar24 / agregadores comerciales
**Razón de rechazo:** viola TOS y P7 (no reproducible legalmente por terceros).

### B. Una única fuente "todo en uno"
**Razón de rechazo:** no existe pública; y acoplaría los cuatro dominios a un proveedor.

## Alineación con ADR-0000

- **Refuerza P7** (lista blanca de fuentes públicas), **P9** (etiqueta epistémica desde el origen), **P1** (procedencia sellada por hash).
- **Tensión con P3:** OpenSky/ACLED con cuenta gratuita mejoran rate/cobertura. Mitigación: el núcleo funciona con los tiers sin auth; las cuentas son opt-in, nunca camino crítico.
- No roza la frontera ética: define de dónde se *observa*, no a quién se *apunta*.

## Referencias

- CelesTrak (T.S. Kelso). *GP/TLE data and API.*
- OpenSky Network. *Live API and historical database.*
- ACLED. *Armed Conflict Location & Event Data — Codebook and Terms of Use.*
