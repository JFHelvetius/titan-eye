# ADR-0009: Cadena de ingestión del dominio aéreo v0.1 (ADS-B / OpenSky)

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0001, ADR-0002, ADR-0005, ADR-0006, ADR-0003

---

## Contexto

Primer incremento de la Fase 1. ADR-0002 ya decidió OpenSky como fuente del
dominio aéreo y su contrato de procedencia; este ADR registra las decisiones de
**implementación** de la cadena `Raw → Normalized` para ese dominio, que no
estaban fijadas y que sientan patrones reutilizables por las fases siguientes.

## Decisión

1. **Primitivas de ingestión reutilizables** (no específicas de OpenSky):
   - `RawArtifact` (Pydantic frozen) sellado por `content_hash = SHA-256(payload)`, con el contrato de procedencia de ADR-0002 (source_id, dominio, url, fetched_at, etiqueta epistémica, license_note).
   - `Transport` Protocol con `UrllibTransport` (stdlib, cero deps, P3) y `FakeTransport` (tests sin red, falla ruidoso ante URL no registrada).
   - `FetchCache` content-addressable: blobs por SHA-256 + índice JSONL append-only (ADR-0006). Política cache-first con `max_age` por request.
   - `Clock` inyectable (`SystemClock`/`FixedClock`) para determinismo de tests (P1).

2. **`max_age` corto para ADS-B** (15 s por defecto): las posiciones aéreas son
   de altísima cadencia; reutilizar un snapshot viejo sería deshonesto.

3. **Normalizador puro `normalize_states`**: función determinista sin red. Mapea
   el vector de estado de OpenSky a `AircraftState` (Normalized), propagando
   `content_hash_source` (FK por hash, ADR-0005) y `epistemic_label="observed"`.

4. **Honestidad sobre filas sin posición (P2):** las aeronaves cuyo `lat/lon` es
   nulo se **conservan** como `AircraftState` con `has_position=False`; NO se
   inventan coordenadas ni se descartan en silencio. El consumidor decide si
   filtrarlas; el render del globo las omite (no se pueden dibujar) pero la CLI
   reporta `n_states` y `n_with_position` por separado.

5. **Incertidumbre como dato (P2):** `last_contact_age_s` (antigüedad del último
   mensaje) y `position_source` (ADS-B/MLAT/...) viajan en el modelo. Una
   posición antigua o de MLAT no se presenta igual que una ADS-B reciente.

6. **CLI** `titan-eye ingest aerial [--bbox] [--cache]`: núcleo testeable
   (`run_ingest_aerial`) separado del wiring de red para inyectar fuentes fake.

7. **Versionado:** `RAW_ARTIFACT_SCHEMA_VERSION`, `AIRCRAFT_STATE_SCHEMA_VERSION`
   y `NORMALIZER_VERSION` = `0.1.0` (ADR-0006, versiones independientes por modelo).

## Justificación

- Las primitivas se diseñan **agnósticas de fuente** para que CelesTrak (Fase 2),
  los reportes balísticos (Fase 3) y ACLED (Fase 4) reusen transporte, cache,
  artefacto y reloj sin reescribirlos.
- Conservar las filas sin posición es la aplicación directa de P2: el sistema no
  oculta lo que no sabe.

## Consecuencias

**Positivas** — cadena Raw→Normalized completa, sin red en tests, validada
end-to-end contra OpenSky real. Patrones reutilizables establecidos.
**Negativas** — todavía **sin persistencia DuckDB/Parquet** (la Normalized vive
en memoria / cache de bytes). La capa de catálogo persistente espera a ADR-0008
(storage), planificado. Deuda explícita, no oculta.
**Neutras** — el filtro de "aeronaves de interés" (rangos militares públicos) se
difiere; sería **descriptivo, nunca acusatorio** (ADR-0003) cuando llegue.

## Alternativas consideradas

### A. Persistir ya en DuckDB/Parquet
**Razón de rechazo:** requiere fijar antes ADR-0008 (storage). Mejor cerrar la
cadena lógica y su verificación primero, como hizo Orbital Sentinel (propagación
on-demand antes que persistencia).

### B. Descartar filas sin posición en el normalizador
**Razón de rechazo:** viola P2 (oculta datos). Se conservan y se cuentan aparte.

## Alineación con ADR-0000

- **Refuerza P1** (reloj inyectable, hashes deterministas), **P2** (filas sin
  posición conservadas; incertidumbre como dato), **P5/P7** (fuente pública con
  license_note propagada), **P9** (etiqueta `observed` sellada desde ingestión).
- **No roza la frontera ética:** registra posiciones públicas; ningún veredicto.

## Referencias

- OpenSky Network REST API, endpoint `/api/states/all`.
- Orbital Sentinel, pipeline de ingestión CelesTrak (artifact + transport + cache).
