# Planos y contratos de datos — Titan Eye

Documento de referencia de la arquitectura de planos (ADR-0001) y de cómo fluye
un dato desde los bytes públicos hasta el píxel del globo, sin romper la
procedencia (ADR-0005) ni la honestidad epistémica (ADR-0000 P9).

## Los siete planos

| # | Plano | Responsabilidad | Importa de |
|---|-------|-----------------|-----------|
| 1 | `core` | Tipos, errores, tiempo, geodesia, identidad content-addressable, enum de dominios | nadie |
| 2 | `ingestion` | Adaptadores de fuente pública, transporte HTTP, cache CAS, `RawArtifact` sellado | core |
| 3 | `catalog` | Raw → Normalized: modelos inmutables, versionados, content-addressable, por dominio | core, ingestion |
| 4 | `analytics` | Derived: propagación (SGP4 / balística / gran círculo), agregación geométrica, KDE | core, catalog |
| 5 | `provenance` | Cadena content-addressable, verificadores de integridad y reproducibilidad | core, catalog, analytics |
| 6 | `viz` (`app/`) | Globo Cesium + dashboards; traduce modelos a payload de render | todos los de datos |
| 7 | `orchestration` | Pipelines de composición + CLI | todos |

**Regla de dependencias:** cada plano solo importa de planos inferiores. Excepción: los *workflows* de `orchestration/` (sufijo `Pipeline`/`Workflow`) componen y pueden importar de cualquiera.

## Eje de dominio

Ortogonal a los planos. `core/domains.py::Domain ∈ {orbital, suborbital, aerial, surface}`. Cada fila de `catalog` y `analytics` pertenece a exactamente un dominio. La razón es P2: el error de un TLE (~km) y el de un evento ACLED (resolución de ciudad) no son comparables; mezclarlos sin declararlo sería deshonesto.

## Las tres capas de datos (dentro de catalog/analytics)

Heredadas de Orbital Sentinel, adaptadas:

- **Raw** — los bytes exactos de la fuente, sellados por `content_hash` (ADR-0005). Inmutable (ADR-0006). No se interpreta.
- **Normalized** — el modelo Pydantic frozen derivado del Raw, con FK por hash al Raw (`content_hash_source`) y con `epistemic_label` (P9). Inmutable, versionado (`schema_version`, `engine_version`).
- **Derived** — el resultado de propagar/agregar. On-demand por defecto (no se persiste); persistido solo por excepción justificada (detecciones raras y valiosas). Doble/triple FK por hash a sus entradas Normalized.

**Regla de no-copia:** si un dato vive en una capa, no se duplica en otra; se recupera por FK de hash. Una capa puede borrarse sin romper las inferiores (prueba de fronteras limpias).

## Etiqueta epistémica (P9) — cómo viaja

```
fuente pública ──(ingestion)──► RawArtifact.epistemic_label (default del dominio, ADR-0002)
                                     │
                                     ▼
                            Normalized.epistemic_label  (sellado, inmutable)
                                     │
                  ┌──────────────────┼───────────────────┐
                  ▼ (analytics)      ▼                    ▼
        reconstrucción balística → epistemic_label = "inferred"   (cambia explícitamente, nunca en silencio)
                                     │
                                     ▼ (viz, ADR-0004)
                      el render ELIGE el estilo según la etiqueta:
                      observed → punto nítido + error nominal
                      asserted → halo = resolución de geolocalización
                      inferred → banda/tubo de incertidumbre (línea fina PROHIBIDA)
```

Una promoción de `asserted`/`inferred` a `observed` es imposible sin un cambio
de código visible y un ADR. Esa es la garantía estructural de honestidad.

## Flujo end-to-end (ejemplo: una aeronave)

1. `ingestion/sources/opensky.py` pide el estado a OpenSky → `RawArtifact{payload, content_hash, epistemic_label="observed", license_note}`.
2. `catalog` normaliza → `AircraftTrack{icao24, lat, lon, alt, ..., content_hash_source, schema_version}`.
3. `analytics` interpola posición a un instante con su incertidumbre temporal.
4. `provenance` puede verificar: ¿el `content_hash_source` existe en Raw? ¿se reproduce el hash del payload?
5. `viz` traduce a payload del globo; el render dibuja el punto con su error nominal y su antigüedad.

En ningún punto el sistema emite un veredicto de intención. Solo geometría, error y procedencia.
