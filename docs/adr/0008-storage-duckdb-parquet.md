# ADR-0008: Storage DuckDB + Parquet particionado

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P1, P3, P8), ADR-0006, ADR-0001, ADR-0009

---

## Contexto

ADR-0006 fijó inmutabilidad y versionado de las capas de datos, pero no el
formato físico. La cadena aérea (ADR-0009) ya produce modelos Normalized en
memoria; para sostener un registro histórico citable por hash (visión ADR-0000)
hace falta persistirlos en disco de forma local-first (P8), barata (P3) y
auditable (P1). Es la misma necesidad que Orbital Sentinel resolvió con
DuckDB + Parquet, cuyo patrón se valida aquí para Titan Eye.

## Decisión

- **Parquet** como formato canónico en disco (columnar, comprimido zstd, portátil, sin servidor).
- **DuckDB** como motor de consulta **read-only** sobre globs de Parquet (`read_parquet(..., hive_partitioning=false)`). No se usa un fichero `.duckdb` mutable: la base es el conjunto de Parquets inmutables.
- **Un archivo Parquet por snapshot de origen**, nombrado por el hash del Raw que lo produjo: `snap_<content_hash_source>.parquet`. Todas las filas Normalized derivadas de un mismo Raw viven en ese único archivo. **Idempotencia por archivo**: si el archivo ya existe, la inserción es no-op (ADR-0006).
- **Particionamiento Hive por tiempo de snapshot**, con granularidad por dominio:
  - Aéreo (alta cadencia): `data/normalized/aerial/year=YYYY/month=MM/day=DD/`.
  - Orbital (cadencia horaria/diaria): `year=YYYY/month=MM/` (Fase 2).
  El particionado mantiene acotado el número de archivos por directorio.
- **Sesión DuckDB forzada a `SET TimeZone='UTC'`**: no depender de la TZ del SO (precondición de reproducibilidad, P1; evita exigir tzdata IANA en Windows).
- **Escritura atómica**: escribir a `.tmp` y `replace()` para no dejar Parquets a medias ante un fallo.
- **La capa Raw del dominio aéreo es la cache CAS** (ADR-0009): los bytes crudos ya viven content-addressed como blobs. No se duplican en Parquet. El Parquet persiste la capa **Normalized**, anclada al Raw por `content_hash_source` (ADR-0005).

## Justificación

- **P3/P8:** cero servidor, cero coste recurrente; corre en un portátil. Un Parquet por snapshot es trivial de auditar y parallel-safe (cada escritor toca su archivo).
- **P1:** Parquet inmutable + sesión UTC + idempotencia por hash = el dato citado ayer se reproduce hoy.
- **Validado en el proyecto hermano:** Orbital Sentinel ejecutó un benchmark de concurrencia sobre este patrón (pico ~2000 ins/s, cero corrupción) y decidió mantenerlo. Titan Eye hereda esa evidencia.

## Consecuencias

**Positivas** — local-first, auditable, sin servidor, append-only por construcción.
**Negativas** — muchos archivos pequeños a largo plazo (especialmente aéreo de alta cadencia). Mitigación: particionado por día y, si en 5 años el reader se degrada (>~50k archivos/dir), abrir un ADR de compactación con tombstones, nunca borrado in-place. La escala real de Titan Eye no persiste propagación masiva (ADR-0006), así que el volumen lo dominan snapshots, no efemérides.
**Neutras** — formato aislado tras los repositorios de `catalog/`; un swap futuro (p. ej. a un único Parquet dataset) no toca a los consumidores.

## Alternativas consideradas

### A. SQLite
**Razón de rechazo:** single-writer, peor para analítica columnar, y un fichero mutable rompe la inmutabilidad por archivo de ADR-0006.

### B. Un fichero `.duckdb` mutable como base
**Razón de rechazo:** introduce un blob mutable con lock global; contradice append-only y el patrón content-addressable.

### C. Parquet dataset único (un directorio, muchos row-groups)
**Razón de rechazo:** complica la idempotencia por hash y la escritura concurrente. El archivo-por-snapshot es más simple y auditable. Reconsiderable si el conteo de archivos se vuelve problema.

## Alineación con ADR-0000

- **Refuerza P1** (inmutable + UTC + idempotente), **P3/P8** (sin servidor, portátil).
- **Implementa el soporte físico de ADR-0006.**
- **Sin tensiones.** Es infraestructura de almacenamiento; no roza la frontera ética.

## Referencias

- Orbital Sentinel, ADR-0004 (DuckDB+Parquet) y benchmark de concurrencia.
- DuckDB documentation — `read_parquet`, Hive partitioning.
- Apache Parquet specification.
