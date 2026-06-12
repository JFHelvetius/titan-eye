# Roadmap por fases — Titan Eye

El proyecto avanza por **fases incrementales**, cada una cerrada con un ADR de
cierre formal (igual que Orbital Sentinel cerró sus fases con ADR-0015/0021).
Una fase no se da por cerrada sin: (a) tests de regresión verdes, (b)
documentación de usuario, (c) honestidad sobre incertidumbre cumplida en sus
outputs, y (d) un smoke-test end-to-end reproducible.

El orden está pensado para construir **primero la columna de procedencia y un
dominio "fácil y verificable"**, y solo después los dominios donde la
incertidumbre es más delicada. No se construye analítica sofisticada sobre
datos sintéticos: cada fase se valida contra datos públicos reales.

---

## Fase 0 — Fundación (en curso)

**Objetivo:** brújula y esqueleto.

- [x] ADR-0000 (visión) + ADR-0001..0007 (planos, fuentes, incertidumbre, viz, procedencia, inmutabilidad, licencia).
- [x] Scaffold del paquete (`src/titan_eye`, `pyproject.toml`, layout de planos).
- [x] Núcleo: errores tipados, enum de dominios, identidad content-addressable.
- [x] Globo Cesium multidominio inicial (`docs/cesium/index.html`) + wrapper + shell Streamlit con datos de demostración.
- [ ] CI (tests + ruff + mypy), `requires-python >=3.11`.

**Cierre:** cuando el esqueleto compile, los tests base pasen y el globo renderice la demo.

## Fase 1 — Dominio aéreo (ADS-B) + columna de procedencia  *(en curso)*

**Por qué primero el aéreo:** es `observed`, de alta cadencia y fácilmente
verificable (cualquiera puede cruzar una posición con OpenSky). Es el dominio
ideal para estrenar la cadena Raw→Normalized→Derived y la verificación por hash.

- [x] Primitivas de ingestión reutilizables: `RawArtifact` sellado por SHA-256, `Transport`/`UrllibTransport`/`FakeTransport`, `FetchCache` CAS, `Clock` inyectable (ADR-0009).
- [x] Adaptador `ingestion/sources/opensky.py` con contrato de procedencia (ADR-0002), cache-first con `max_age` corto.
- [x] Normalizador puro `normalize_states` → `AircraftState`; honestidad con filas sin posición (P2); incertidumbre como dato (`last_contact_age_s`, `position_source`).
- [x] Traductor a payload de globo + CLI `titan-eye ingest aerial`. Validado end-to-end contra OpenSky real.
- [x] Persistencia DuckDB/Parquet (`aircraft_states`, un Parquet por snapshot, idempotente) — ADR-0008.
- [x] Verificadores de integridad (`provenance/`): I1 referencial Raw→Normalized + I2 reproducibilidad. CLI `verify-aerial`. Validado sobre 172 aeronaves reales (ok=true).
- [ ] Filtro de "aeronaves de interés" **descriptivo** (rangos ICAO/callsign militares públicos), nunca acusatorio. *(diferido; opcional)*

**Matemática:** geodesia de gran círculo, interpolación de posición con su incertidumbre temporal.
**Estado:** núcleo de Fase 1 cerrado (ingesta + persistencia + integridad, 38 tests verdes). Cierre formal pendiente del filtro descriptivo (opcional).

## Fase 2 — Dominio orbital (satélites)  *(núcleo cerrado)*

Reutiliza directamente el motor SGP4 y los patrones de Orbital Sentinel (ADR-0010).

- [x] Adaptador CelesTrak (TLE/GP) por GROUP o CATNR, con contrato de procedencia (ADR-0002).
- [x] Parser TLE estricto por columnas → Normalized `OrbitalElement` (conserva líneas originales + `tle_content_hash`).
- [x] Propagación SGP4 on-demand (`analytics/propagation/`): `twoline2rv` bit-exacto, TEME→ECEF (GMST IAU 1982)→geodésica esférica. Error baseline/crecimiento declarado (P2).
- [x] Persistencia `OrbitalElementsRepository` (Parquet/DuckDB, ADR-0008) en paridad con la aérea.
- [x] Render: satélites + groundtrack SGP4 en el globo + modo "CelesTrak en vivo" en la app. Validado contra CelesTrak real (25 sat del grupo `stations`, ISS 51.63°/93min/426km).
- [ ] Subconjunto "militar/dual-use" descriptivo desde catálogos públicos (sin clasificación de intención). *(diferido; opcional)*
- [ ] Verificador de integridad orbital I1/I2 (espejo del aéreo). *(pendiente)*

**Matemática:** SGP4 (Vallado), TEME→ECEF→geodésica, derivación de período/semieje. 52 tests verdes.

## Fase 3 — Dominio suborbital (trayectorias balísticas reconstruidas)  *(núcleo cerrado)*

El dominio más delicado en honestidad: el output es **`inferred`**, no medido (ADR-0011).

- [x] Dos modelos con dos etiquetas epistémicas: `BallisticReport` (`asserted`, el reporte público) → `BallisticTrajectory` (`inferred`, la reconstrucción). Nunca se colapsan (P9).
- [x] Física Kepleriana de vacío con **solución cerrada** (e, a desde apogeo + ángulo central); muestreo sobre gran círculo (slerp). Validado: altitud máx == apogeo; alcance == gran círculo; extremos en superficie.
- [x] **Banda de incertidumbre declarada** (linealizada desde σ del reporte + suelo de error del modelo `MODEL_UNCERTAINTY_KM`, que representa la física omitida). No se fabrica Monte Carlo de falsa precisión.
- [x] Ingestión del reporte como JSON sellado (`asserted`), normalizador puro, persistencia justificada `BallisticTrajectoryRepository` (ADR-0006/0011).
- [x] Render: **tubo/corredor de incertidumbre**, nunca línea fina (ADR-0003/0004) + elipse de dispersión de impacto. CLI `reconstruct-ballistic`. Validado end-to-end.
- [ ] v0.2: Tierra rotante; trayectoria de mínima energía (apogeo implícito); Monte Carlo cuando el modelo físico sea realista. *(diferido)*

**Matemática:** elipse Kepleriana de dos cuerpos (vacío, esférica, no rotante), banda linealizada + suelo de modelo declarado. 66 tests verdes.

## Fase 4 — Dominio de superficie (eventos de conflicto) + mapa de calor  *(núcleo cerrado)*

ADR-0012. El cuarto y último dominio; enciende el mapa de calor.

- [x] Ingesta de datasets públicos (ACLED/GDELT exportado a JSON) sellada como `asserted`, con `license_note`.
- [x] `ConflictEvent` con **`geoloc_resolution`** declarada (exact/city/region/country); el render usa halo, no punto nítido.
- [x] **Mapa de calor por KDE** Gaussiano con distancia de gran círculo y **`bandwidth_km` declarado**. Peso = 1 por evento: mide densidad de eventos **REPORTADOS**, nunca intensidad ni amenaza (ADR-0003). Las víctimas son atributo, jamás peso.
- [x] Persistencia `ConflictEventsRepository` + verificador I1/I2 (`verify-surface`). Validado end-to-end.
- [ ] Adaptador ACLED/GDELT con API en vivo (requiere clave → ADR-0013 secretos). *(diferido)*

**Matemática:** KDE Gaussiano con bandwidth explícito; sin confundir cobertura con realidad (ADR-0003). 80 tests verdes.

## Fase 5 — Dashboard de situación integrado  *(CERRADA)*

- [x] **Panel de situación Streamlit** (`app/streamlit_app.py`): combina los cuatro dominios sobre un único globo Cesium, con sidebar de control por dominio, KPIs, tablas por dominio etiquetadas por epistemología, y pestaña de verificación de procedencia (I1/I2). Es la culminación del proyecto (como Orbital Sentinel acaba en Streamlit).
- [x] **Caso de situación portable y verificable** (ADR-0013): `SituationCase` con `case_hash` content-addressable, digest invariante al orden, verificación de auto-consistencia y detección de manipulación. CLI `build-case` / `verify-case`. Validado: caso limpio ok=true, caso manipulado detectado. Análogo del `InvestigationCase` de Orbital Sentinel.
- [x] **Tubos de error 3D** para los `inferred` en el globo (`polylineVolume` de sección ∝ `band_km`): la línea fina queda definitivamente prohibida (ADR-0004).
- [x] **Proximidad geométrica multidominio con incertidumbre, sin veredictos** (ADR-0014): `find_proximities` reporta distancia horizontal y separación vertical por separado, incertidumbre combinada y etiqueta epistémica más débil. Panel en el dashboard. **Sin scores de amenaza ni veredictos de intención** — geometría con error, como las conjunciones de Orbital Sentinel.

**Invariante de cierre cumplido:** ningún panel del dashboard emite scores de
amenaza ni clasificación de intención. Lo que muestra es geometría, conteos y
procedencia. **Las cinco fases tienen núcleo operativo, 97 tests verdes.**

---

## Estado del proyecto

Las cinco fases del roadmap tienen su núcleo cerrado: los cuatro dominios
(`observed`/`asserted`/`inferred`), la cadena de procedencia con verificadores de
integridad, el caso de situación auditable por hash, y el dashboard de situación.
Lo que queda son **profundizaciones declaradas, no fases nuevas**: APIs en vivo con
clave (ADR-0015 secretos), reproducibilidad bajo entorno declarado formalizada
(ADR-0016), y el cierre formal con contrato congelado (ADR-0017), análogo al
contrato criptográfico v1.0.0 de Orbital Sentinel.

---

## Disciplina anti-trampa

Heredada de Orbital Sentinel: **no construir analítica sobre fixtures
sintéticos**. Cada fase se valida con datos públicos reales y declara su error
contra ground truth público conocido. Si un dominio no se puede validar
honestamente, su fase no se cierra.
