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

## Fase 6 — Dominio marítimo (buques y flotas, AIS)  *(núcleo cerrado)*

Quinto dominio (ADR-0015). La capa naval que se suele olvidar.

- [x] `Domain.MARITIME` + `VesselPosition` (`observed`) con clases descriptivas (portaaviones, destructor, fragata, submarino, anfibio, patrullero, auxiliar).
- [x] Normalizador AIS (`normalize_ais`), repo Parquet, verificador I1/I2 (`verify-maritime`), CLI `ingest maritime`. Capa naval en el globo + KPI + tabla + proximidad.
- [x] **Honestidad reforzada (P2):** AIS autodeclarado y falsificable; buques de guerra lo apagan/falsean; submarinos sumergidos no transmiten; *ausencia ≠ inexistencia*. Declarado en el dominio y en el render.
- [ ] AIS en vivo (clave en la mayoría de proveedores → ADR-0016 secretos). *(diferido)*

**Estado:** cinco dominios (`observed`×3, `asserted`, `inferred`), 108 tests verdes.

## Estado del proyecto

El núcleo está cerrado: **cinco dominios** (orbital/aéreo/marítimo `observed`,
superficie `asserted`, suborbital `inferred`), la cadena de procedencia con
verificadores de integridad, el caso de situación auditable por hash, la proximidad
geométrica sin veredictos, y el dashboard de situación. Lo que queda son
**profundizaciones declaradas**: APIs en vivo con clave (ADR-0016 secretos),
reproducibilidad formalizada (ADR-0017), y el cierre formal con contrato congelado
(ADR-0018), análogo al contrato criptográfico v1.0.0 de Orbital Sentinel.

## Fase 7 — Capa de inteligencia: índice de tensión y alertas  *(núcleo cerrado)*

Headline de la visión de producto, construido en su **forma honesta** (ADR-0016).

- [x] **Titan Tension Index (TGTI, 0-100)**: composición transparente de actividad militar OBSERVABLE (eventos, balística, aeronaves, buques) con normalización saturante y pesos declarados. Cada índice trae su **desglose completo** y su metodología — reproducible y editable. Etiqueta epistémica = la más débil de sus componentes.
- [x] **Alertas descriptivas**: reportan actividad ya observable/pública (balística presente, concentración naval, eventos de conflicto, hotspot), con su procedencia. **No predicen ni emiten veredictos de amenaza.**
- [x] Pestaña "Índice & Alertas" en el dashboard. `analytics/intelligence.py`, 11 tests.

**Frontera mantenida (ADR-0000/0003/0016):** el TGTI mide actividad observable, no
intención ni futuro; es el patrón `Pc`-con-asunciones de Orbital Sentinel (ADR-0020)
aplicado aquí. **Sin** soluciones de targeting ni apoyo a decisión de fuego — esa
sigue siendo la única línea dura, y ninguna capa pedida la cruza.

## Fase 8 — Capa de referencia: bases e infraestructura  *(núcleo cerrado)*

Geografía pública estática (ADR-0017), no un dominio de actividad.

- [x] `Installation` (`asserted`) con tipos militares (base aérea/naval/army, silo, centro de mando, radar) e infraestructura crítica (central eléctrica/nuclear, refinería, puerto, aeropuerto, presa). `Domain.REFERENCE` como tag del Raw.
- [x] Normalizador, repo Parquet, `verify-installations`, CLI `ingest installations`. Capa "Bases e infraestructura" en el globo (militar ▣ / infra ◆) + tabla en el dashboard.
- [x] **Frontera dura:** solo fuentes públicas; etiqueta `asserted` + nota de posible desactualización; **excluidas del cálculo de proximidad y de todo cómputo operacional** (sin proximidad-a-objetivo, sin scoring de vulnerabilidad). Solo display.

## Fase 9 — Filtro transversal por país y tipo  *(núcleo cerrado)*

Hace el seguimiento *operable* (ADR-0018): filtro de vista, no inferencia.

- [x] Cada entrada del globo expone `country` y `kind` (clase filtrable). `filter_payload` puro + `available_countries`/`available_kinds`.
- [x] País real donde el dato lo soporta: aéreo (origin_country), marítimo (bandera), superficie (país del reporte — campo nuevo en `ConflictEvent`), instalaciones (país). Orbital/suborbital vacíos (faltan satcat/reporte) — declarado, no inventado.
- [x] Multiselect país + tipo en el dashboard; aplica a los cinco dominios + referencia.
- [x] **Sin atribución de bando ni amenaza (ADR-0003):** solo país declarado y clase técnica; no hay "aliado/enemigo".

## Fase 10 — Línea temporal histórica  *(núcleo cerrado)*

"Máquina del tiempo" sobre el store append-only (ADR-0019), sin almacenamiento nuevo.

- [x] `analytics/timeline.py` puro: `daily_activity` (evolución día a día por dominio), `payload_for_day` (replay de la situación de un día), `available_days`/`date_range`/`summarize`.
- [x] Loader desde el data-root (superficie→event_date; aéreo/marítimo→día de snapshot). CLI `timeline`. Pestaña "Línea temporal" en el dashboard (gráfica de actividad + slider de día con replay en el globo).
- [x] **Honestidad (P2):** un día sin datos está **vacío**, no se interpola — vacío = "no se capturó", no "sin actividad". Orbital/suborbital/instalaciones fuera de v0.1 (propagación / sin fecha de evento / estático), declarado.

## Fase 11 — Capa OSINT: noticias y RRSS geolocalizadas  *(núcleo cerrado)*

Inteligencia narrativa con procedencia (ADR-0020), no veredicto de veracidad.

- [x] `OsintItem` (`asserted`) con `source_tier` (news_agency/government/local_media/social_media). `Domain.OSINT` como tag del Raw.
- [x] Normalizador, repo Parquet, `verify-osint`, CLI `ingest osint`. Capa "Noticias/RRSS" en el globo (marcador ✎ con enlace a la fuente) + tabla + filtro (kind=tier).
- [x] **Honestidad dura (ADR-0020):** Titan Eye **no verifica veracidad** ni puntúa credibilidad/desinformación. Garantiza **procedencia** (qué fuente, cuándo, URL, hash); el tier describe el TIPO de fuente, no su verdad. Sin sello "verificado por Titan Eye".

## Fase 12 — Fichas país y alianzas + dashboard desplegable  *(núcleo cerrado)*

- [x] `CountryProfile` (`asserted`, ADR-0021): presupuesto militar, personal activo/reservas, alianzas — cifras de fuentes públicas (SIPRI/IISS) con año y fuente. Normalizador + repo + `verify-countries` + CLI `ingest countries`. Pestaña "Países & Alianzas" en el dashboard (ficha + agrupación por alianza declarada). **Sin ranking de poder ni 'amenazas activas'** (ADR-0003): solo cifras con procedencia.
- [x] **Dashboard desplegable en una URL**: `requirements.txt` + bootstrap de `sys.path` en `app/streamlit_app.py` → arranca en Streamlit Community Cloud (boot 200 sin PYTHONPATH). Instrucciones en el README.

> **Capas alineadas pendientes:** clasificación por tipo de aeronave/satélite
> (requiere reference DB / satcat); adaptadores en vivo con clave (ADR de secretos).

---

## Disciplina anti-trampa

Heredada de Orbital Sentinel: **no construir analítica sobre fixtures
sintéticos**. Cada fase se valida con datos públicos reales y declara su error
contra ground truth público conocido. Si un dominio no se puede validar
honestamente, su fase no se cierra.
