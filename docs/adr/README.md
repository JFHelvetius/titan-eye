# Architecture Decision Records — Titan Eye

Este directorio contiene las decisiones arquitectónicas del proyecto en
formato ADR (Nygard extendido). **Una decisión sin ADR no se considera
tomada** (ADR-0000, P6).

## Política de ADRs

1. **ADR-0000 es la brújula.** Todo ADR posterior incluye una sección
   "Alineación con ADR-0000" (ver `template.md`). Una PR con un ADR que la
   omita no se mergea.
2. **Los ADR no se reescriben; se enmiendan.** Una decisión que cambia se
   documenta con un historial de enmiendas al pie, o se *supersede* por un
   ADR nuevo. La historia es parte del contrato.
3. **Frontera ética dura.** Ningún ADR puede mover el proyecto hacia
   targeting, apoyo a decisión de fuego, o clasificación de intención/amenaza
   (ADR-0000 sección de alcance, ADR-0003).
4. **Numeración estable.** Los números no se reutilizan ni se reordenan.

## Índice

| ADR | Título | Estado |
|-----|--------|--------|
| [0000](0000-long-term-vision.md) | Visión a largo plazo | Aceptado |
| [0001](0001-planes-architecture.md) | Arquitectura de planos por contratos de datos | Aceptado |
| [0002](0002-public-data-sources.md) | Fuentes públicas por dominio y contrato de procedencia | Aceptado |
| [0003](0003-uncertainty-and-no-intent.md) | Honestidad sobre incertidumbre y prohibición de clasificar intención | Aceptado |
| [0004](0004-cesium-visualization.md) | Visualización geoespacial con Cesium embebido | Aceptado |
| [0005](0005-content-addressable-provenance.md) | Identidad content-addressable y cadena de procedencia | Aceptado |
| [0006](0006-data-immutability.md) | Inmutabilidad y versionado de las capas de datos | Aceptado |
| [0007](0007-apache-license.md) | Licencia Apache-2.0 | Aceptado |
| [0008](0008-storage-duckdb-parquet.md) | Storage DuckDB + Parquet particionado | Aceptado |
| [0009](0009-aerial-ingestion-v01.md) | Cadena de ingestión del dominio aéreo v0.1 (ADS-B / OpenSky) | Aceptado |
| [0010](0010-orbital-sgp4-v01.md) | Dominio orbital — TLE + propagación SGP4 v0.1 | Aceptado |
| [0011](0011-suborbital-ballistic-v01.md) | Dominio suborbital — reconstrucción balística v0.1 | Aceptado |
| [0012](0012-surface-conflict-heatmap-v01.md) | Dominio superficie — eventos de conflicto y mapa de calor v0.1 | Aceptado |
| [0013](0013-situation-case-v01.md) | Caso de situación portable y verificable v0.1 | Aceptado |
| [0014](0014-multidomain-proximity-v01.md) | Proximidad geométrica multidominio v0.1 | Aceptado |
| [0015](0015-maritime-ais-v01.md) | Dominio marítimo — buques y flotas (AIS) v0.1 | Aceptado |
| [0016](0016-tension-index-alerts-v01.md) | Índice de tensión y alertas de actividad observable v0.1 | Aceptado |
| [0017](0017-installations-reference-v01.md) | Capa de referencia de instalaciones (bases e infraestructura) v0.1 | Aceptado |
| [0018](0018-country-type-filter-v01.md) | Filtro transversal por país y tipo v0.1 | Aceptado |
| [0019](0019-historical-timeline-v01.md) | Línea temporal histórica (replay sobre store append-only) v0.1 | Aceptado |
| [0020](0020-osint-news-layer-v01.md) | Capa OSINT — noticias y redes sociales geolocalizadas v0.1 | Aceptado |

## Planificados (no escritos aún)

| ADR | Título tentativo |
|-----|------------------|
| 0021 | Gestión de secretos (tokens OpenSky, ACLED/AIS/OSINT API en vivo) |
| 0022 | Fichas país y alianzas (referencia pública) |
| 0023 | Reproducibilidad bajo entorno declarado / cierre formal con contrato congelado |

> Nota de numeración: 0009 (aéreo) se aceptó antes que 0008 (storage). Los
> números reflejan orden de aceptación, no de dependencia; no se reordenan.
