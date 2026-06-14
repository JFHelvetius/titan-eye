# Titan Eye

[![ci](https://github.com/JFHelvetius/titan-eye/actions/workflows/ci.yml/badge.svg)](https://github.com/JFHelvetius/titan-eye/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![tests](https://img.shields.io/badge/tests-155%20passing-brightgreen.svg)](tests/)
[![ADRs](https://img.shields.io/badge/ADRs-21-informational.svg)](docs/adr/)

**Infraestructura verificable para afirmaciones sobre actividad militar observable con datos públicos.**

Titan Eye es software open-source que permite a cualquiera —sin acceso a datos privilegiados, sin autoridad, sin pedir confianza— **registrar, propagar y visualizar** eventos orbitales, suborbitales, aéreos y de superficie de relevancia militar, y **auditar** cualquier afirmación sobre ellos contra los bytes públicos que la originaron.

No es un sistema de targeting. No clasifica intención ni amenaza. Es un **registro de detección con procedencia content-addressable** que ata cada conclusión a su dato público de origen, con la incertidumbre declarada en primer plano.

> **¿De dónde viene?** Titan Eye hereda los protocolos de construcción del proyecto hermano [Orbital Sentinel](../orbital-sentinel) —arquitectura de planos, procedencia por hash, honestidad sobre incertidumbre— y los traduce a un dominio distinto: la actividad militar observable. Hereda los protocolos, no el dominio.

---

## Qué hace (y qué no)

La honestidad sobre el alcance es parte del contrato (ADR-0000, ADR-0003):

- **Cuatro dominios, datos públicos.** Orbital (TLEs de CelesTrak), aéreo (ADS-B de OpenSky), suborbital (trayectorias balísticas *reconstruidas* desde NOTAMs/avisos/reportes públicos) y superficie (eventos de conflicto de ACLED/GDELT).
- **Observado / afirmado / inferido, nunca confundidos.** Una posición ADS-B es declarada por la aeronave; un evento de conflicto es afirmado por un tercero; una trayectoria balística es reconstruida por Titan Eye. El sistema nunca presenta uno como otro (ADR-0000 P9).
- **Incertidumbre en primer plano.** Cada detección lleva su error declarado. Una línea fina nítida como trayectoria balística está *prohibida* como salida (ADR-0003).
- **Procedencia auditable por cualquiera.** Recalcula el SHA-256 del payload público y compáralo con el declarado: si coinciden, la cadena es válida; no necesitas confiar en nosotros (ADR-0005).

**Lo que Titan Eye NO es:**

- **No es un sistema de targeting** ni de apoyo a decisión de fuego. No calcula soluciones de tiro ni guiado.
- **No clasifica intención ni amenaza.** No emite "ataque", "hostil", ni scores de alerta. Produce geometría con error y conteos con procedencia.
- **No usa datos clasificados, filtrados ni de pago como fuentes primarias** (ADR-0000 P7).
- **El mapa de calor mide densidad de eventos *reportados*, no intensidad de conflicto.** Más cobertura mediática no es más guerra.

Si buscas un dashboard de amenazas con luces rojas y veredictos automáticos, este no es el proyecto.

## Dominios y fuentes

| Dominio | Qué observa | Fuente pública | Naturaleza (P9) |
|---------|-------------|----------------|-----------------|
| **Orbital** | Satélites militares / dual-use | CelesTrak, Space-Track | `observed` |
| **Aéreo** | Aeronaves militares en vuelo | OpenSky (ADS-B) | `observed` |
| **Suborbital** | Lanzamientos / trayectorias balísticas | NOTAMs, avisos, reportes | `asserted` → `inferred` |
| **Superficie** | Eventos de conflicto, movimientos | ACLED, GDELT | `asserted` |

Detalle y términos de uso por fuente en [ADR-0002](docs/adr/0002-public-data-sources.md).
**Guía práctica de feeds en tiempo real** (qué es gratis, qué necesita clave,
cada cuánto se actualiza): [`docs/sources.md`](docs/sources.md).

El dashboard arranca con **datos reales EN VIVO sin clave**: satélites (CelesTrak)
y aeronaves (OpenSky/ADS-B, como FlightRadar). Nada es inventado; los dominios que
necesitan tu clave o tu dataset (marítimo, superficie, suborbital, instalaciones,
OSINT) se activan en la barra lateral. En el globo cada objeto se distingue por su
**icono con forma**: ✈ avión y ⚓ buque orientados a su rumbo, 🛰 satélite, 🚀 misil.

## Arquitectura

Siete planos desacoplados por contratos de datos, con dependencias estrictas hacia abajo (ADR-0001):

```
orchestration  → pipelines + CLI
viz            → globo Cesium + dashboards
provenance     → cadena content-addressable, integridad
analytics      → Derived: propagación (SGP4 / balística / gran círculo)
catalog        → Raw → Normalized inmutable, versionado por hash
ingestion      → adaptadores de fuente pública, transporte, cache CAS
core           → tipos, errores, tiempo, geodesia, identidad
```

Eje ortogonal: cada plano de datos está particionado por **dominio** (orbital/suborbital/aéreo/superficie), porque el régimen de error de cada uno es radicalmente distinto.

## Estado actual

**Los cuatro dominios con núcleo operativo, culminando en un dashboard Streamlit.**
Fundación (ADR-0000 a 0008) cerrada. **80 tests sin red en verde**, validado
end-to-end contra fuentes públicas reales.

- **Aéreo (ADS-B / OpenSky)** — `observed`: cadena `Raw → Normalized` sellada por
  hash, cache content-addressable, persistencia DuckDB/Parquet y verificadores de
  integridad (I1 referencial + I2 reproducibilidad). Aeronaves sin posición
  conservadas y contadas aparte; antigüedad del último mensaje como dato.
- **Orbital (TLE / CelesTrak)** — `observed`: parser TLE estricto, propagación SGP4
  on-demand (`twoline2rv` bit-exacto, TEME→ECEF→geodésica), groundtracks en el globo,
  persistencia + integridad. Error declarado que crece con la antigüedad del TLE.
- **Suborbital (reportes balísticos)** — `asserted → inferred`: reconstrucción
  Kepleriana de vacío con solución cerrada y **banda de incertidumbre declarada**
  (σ del reporte + suelo de error del modelo). El reporte (afirmado) y la trayectoria
  (inferida) **nunca se confunden** (P9). Render como tubo de error, nunca línea fina.
- **Superficie (eventos de conflicto)** — `asserted`: ingesta de datasets públicos
  (ACLED/GDELT) con `geoloc_resolution` declarada, y **mapa de calor por KDE** con
  ancho de banda declarado. El peso mide **densidad de eventos reportados**, nunca
  intensidad de conflicto ni amenaza (ADR-0003).
- **Marítimo (buques y flotas)** — `observed`: ingesta AIS con clases de buque
  descriptivas (portaaviones, destructor, fragata, submarino, anfibio, patrullero).
  Honestidad reforzada (ADR-0015): el AIS es **autodeclarado y falsificable**, los
  buques de guerra lo apagan/falsean y los submarinos sumergidos no transmiten —
  *ausencia ≠ inexistencia*.

```bash
pip install -e ".[dev,app]"
titan-eye ingest aerial  --bbox "35,60,-10,40"           # ADS-B real de una región
titan-eye ingest orbital --group stations                # TLEs reales de CelesTrak
titan-eye reconstruct-ballistic --report evento.json     # asserted -> inferred
titan-eye ingest surface --events eventos.json           # eventos de conflicto
titan-eye heatmap --events eventos.json --bandwidth-km 50 # mapa de calor KDE
titan-eye verify-aerial  --data-root ./data              # integridad I1 + I2
streamlit run app/streamlit_app.py                       # dashboard de situación
```

## Dashboard

El proyecto culmina en un **panel de situación Streamlit** (`app/streamlit_app.py`)
que combina los cuatro dominios sobre un único globo táctico Cesium, con KPIs,
tablas por dominio etiquetadas por epistemología, y una pestaña de verificación de
procedencia (I1/I2). Cada panel declara la naturaleza del dato y su incertidumbre.

## Desplegar el dashboard en una URL (Streamlit Community Cloud)

El repo está **listo para desplegar** (`requirements.txt` + bootstrap de path en
la app). En **share.streamlit.io** → *New app*:

- **Repository:** `JFHelvetius/titan-eye` · **Branch:** `main`
- **Main file path:** `app/streamlit_app.py`

Tras *Deploy* (~1 min) el dashboard queda en una URL pública
`https://<algo>.streamlit.app`. Es gratis para repos públicos. El globo Cesium se
sirve aparte desde GitHub Pages (`https://jfhelvetius.github.io/titan-eye/cesium/`)
y el dashboard lo embebe automáticamente.

## Caso de situación auditable por cualquiera

Como Orbital Sentinel emite un `InvestigationCase`, Titan Eye empaqueta una
instantánea situacional en un **`SituationCase`** portable, atado por hash a los
bytes públicos que lo originaron (ADR-0013). Cualquier tercero puede recomputar el
hash y detectar manipulación, sin acceso a tu base de datos ni asimetría
productor/revisor:

```bash
titan-eye build-case  --data-root ./data --out caso.json   # ensambla el caso
titan-eye verify-case --case caso.json                     # ok=true si no fue alterado
```

Ver el [roadmap por fases](docs/architecture/roadmap.md).

## El globo

El corazón visual vive en [`docs/cesium/index.html`](docs/cesium/index.html): un globo CesiumJS autocontenido con 7 proveedores de imagery sin token, panel de capas multidominio (satélites, aeronaves, trayectorias, eventos, mapa de calor, anillos de alcance), time-slider y representación honesta por etiqueta epistémica. Se embebe en la app Streamlit vía iframe + `postMessage` (ADR-0004).

```bash
pip install -e ".[app]"
streamlit run app/streamlit_app.py
```

## Documentación

La arquitectura se documenta como ADRs en [`docs/adr/`](docs/adr/). Ruta de lectura:

1. [ADR-0000 — Visión a largo plazo](docs/adr/0000-long-term-vision.md) — qué es y qué no es el proyecto.
2. [ADR-0003 — Incertidumbre y prohibición de clasificar intención](docs/adr/0003-uncertainty-and-no-intent.md) — la columna ética y de rigor.
3. [ADR-0002 — Fuentes públicas por dominio](docs/adr/0002-public-data-sources.md) — de dónde sale cada dato.
4. [ADR-0005 — Procedencia content-addressable](docs/adr/0005-content-addressable-provenance.md) — auditoría sin autoridad.
5. [ADR-0004 — Visualización Cesium](docs/adr/0004-cesium-visualization.md) — el globo y su honestidad gráfica.

## Licencia

[Apache License 2.0](LICENSE). Uso comercial permitido. Concesión de patentes incluida. La neutralidad de la licencia convive con un diseño orientado a la transparencia (ADR-0007): el proyecto elige qué construir, y eso lo gobierna ADR-0000.
