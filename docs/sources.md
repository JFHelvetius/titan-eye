# Fuentes de datos en tiempo real

Esta página dice, sin rodeos, **de dónde sale cada cosa que ves en el globo**,
si es gratis o necesita clave, cada cuánto se actualiza y qué naturaleza
epistémica tiene (P9). Nada en Titan Eye es inventado: o es un feed público en
vivo, o es un dataset/clave que **tú** aportas. El panel por defecto solo carga
las fuentes **gratuitas y sin clave** (orbital + aéreo).

> Regla de oro (ADR-0000 P7): solo fuentes **públicas**. Nada clasificado, de
> pago como fuente primaria, ni filtrado.

## Resumen rápido

| Dominio | Fuente | Clave | En el panel por defecto | Cadencia típica | Naturaleza (P9) |
|---|---|---|---|---|---|
| 🛰 Orbital (satélites) | [CelesTrak](https://celestrak.org/NORAD/elements/) (TLE) | **No** | ✅ Sí, en vivo | TLEs ~1–3×/día; posición propagada al instante | `observed` |
| ✈ Aéreo (aeronaves) | [OpenSky Network](https://opensky-network.org/) (ADS-B) | **No** (anónimo) | ✅ Sí, en vivo | ~10 s (anónimo: ventana limitada) | `observed` |
| ⚓ Marítimo (buques) | [AISStream](https://aisstream.io/) (AIS) | **Sí** (gratis) | ❌ No (aporta dataset/clave) | segundos–minutos | `observed` |
| 🔥 Superficie (conflicto) | [GDELT](https://www.gdeltproject.org/) / [ACLED](https://acleddata.com/) | GDELT no · ACLED sí | ❌ No (aporta dataset) | GDELT ~15 min; ACLED semanal | `asserted` |
| 🚀 Suborbital (balístico) | NOTAMs / avisos / reportes públicos | depende | ❌ No (aporta reporte) | por evento | `asserted` → `inferred` |
| 🏛 Instalaciones | OpenStreetMap / Wikipedia / FAS | No | ❌ No (aporta dataset) | estático | `asserted` (referencia) |
| ✎ OSINT (noticias/RRSS) | agencias / RRSS con URL | depende | ❌ No (aporta dataset) | por ítem | `asserted` |

«En vivo» = se ingiere en el momento de cargar el panel, con caché corta para
respetar los límites de cada API.

---

## Sin clave, en vivo (cargado por defecto)

### 🛰 Orbital — CelesTrak (TLE → SGP4)

- **Qué es:** elementos orbitales TLE de objetos catalogados (NORAD). Titan Eye
  los propaga con **SGP4** (`twoline2rv` bit-exacto) y los pinta como satélite con
  su groundtrack.
- **Clave:** no.
- **Endpoint:** `https://celestrak.org/NORAD/elements/gp.php?GROUP=<grupo>&FORMAT=tle`
  (grupos: `stations`, `active`, `visual`, `military`, …).
- **Cadencia:** CelesTrak refresca los TLE varias veces al día; la **posición** se
  recalcula al instante para la hora actual. El error declarado crece con la
  antigüedad del TLE (ADR-0003).
- **Naturaleza:** `observed`.
- **Caché en el panel:** 10 min (`_cached_orbital`).
- **Cambiar lo que se carga:** barra lateral → *Orbital · CelesTrak (TLE)* → campo
  `GROUP`.

### ✈ Aéreo — OpenSky Network (ADS-B), «como FlightRadar»

- **Qué es:** estados de vuelo ADS-B (posición, altitud, rumbo, velocidad) que las
  propias aeronaves emiten. Es la misma clase de dato que ves en FlightRadar24 /
  Flightradar, servido por una red abierta.
- **Clave:** no (acceso anónimo). Con cuenta gratuita subes los límites de
  consulta; sin cuenta, la ventana temporal y la frecuencia son más limitadas.
- **Endpoint:** `https://opensky-network.org/api/states/all?lamin=..&lomin=..&lamax=..&lomax=..`
- **bbox por defecto:** Europa + Mediterráneo + Próximo Oriente
  (`lat 25–70, lon −12–60`). Cámbialo en la barra lateral.
- **Cadencia:** ~10 s en la fuente; el panel cachea 2 min (`_cached_aerial`) para
  no exceder el límite anónimo.
- **Naturaleza:** `observed` — **pero la posición la declara la aeronave** y es
  *spoofable*. Los vuelos militares a menudo apagan o falsean el transpondedor.
  Ausencia ≠ inexistencia.

#### Filtro «solo militar» (heurística, activado por defecto)

El foco de Titan Eye es lo militar, así que el panel **filtra el tráfico aéreo a
las aeronaves probablemente militares** con la técnica estándar de la comunidad
ADS-B (`src/titan_eye/analytics/military_filter.py`), combinando dos señales
**públicas**:

1. **Prefijo de indicativo** (callsign): p. ej. `RCH` = USAF Reach, `RRR` = RAF.
2. **Rango ICAO24** (dirección hex del transpondedor): bloques que la OACI/Estados
   asignan a aeronaves militares/de Estado (la misma lista que usa `readsb`).

⚠️ **Honestidad (P9):** la posición sigue siendo `observed`, pero la etiqueta
«militar» es una **inferencia heurística AFIRMADA, no verificada**. Da falsos
positivos (un civil con indicativo coincidente) y falsos negativos (un militar con
indicativo neutro o el ADS-B apagado). Desactiva *Solo militar* en la barra lateral
para ver todo el tráfico, o amplía el bbox si no aparece nada.

Para satélites, el panel **agrega varios grupos militares/de doble uso** de
CelesTrak (no `stations`): `military`, `gps-ops` (GPS), `glo-ops` (GLONASS),
`beidou`, `galileo`, `sbas`, `radar`, `nnss`, `musson`. Se deduplican por NORAD y
da ~200+ satélites reales (validado). Si un grupo no responde, se salta y se sigue
con el resto (el transporte reintenta con backoff y se identifica con User-Agent,
lo que evita los *timeouts* de CelesTrak ante clientes anónimos).

Por defecto el aéreo muestra **todo el tráfico** del bbox con los militares
**resaltados en rojo** (anti-saturación: los civiles van pequeños y sin etiqueta).
El toggle *Solo militar* de la barra lateral oculta el tráfico civil.

### Noticias en vivo · GDELT DOC 2.0 (sin clave)

- **Qué:** artículos de prensa mundial sobre conflicto/militar de las últimas 24h,
  geolocalizados y volcados en la capa OSINT. Se cargan **por defecto**, sin subir
  nada (`_cached_gdelt_news`).
- **Endpoint:** `https://api.gdeltproject.org/api/v2/doc/doc` (mode=artlist).
- **Sin clave.** Tiene un **rate-limit público** agresivo (~1 req/5 s por IP); el
  panel cachea 5 min y reintenta con backoff. Si ves «Noticias GDELT no
  disponibles ahora», es throttling temporal: se rellena al recargar.
- **Naturaleza:** `asserted` — afirmación de la prensa, **no verificada** por
  Titan Eye (ADR-0020). Además se geolocaliza por **país de la FUENTE** (centroide),
  no por el lugar del suceso; se declara en cada ítem. Densidad = volumen de
  cobertura, no intensidad del conflicto (ADR-0003).

### Eventos de conflicto en vivo · GDELT 2.0 Events (sin clave)

- **Qué:** eventos de **violencia material** (combate, asalto, coerción, violencia
  masiva — CAMEO QuadClass 4) de las últimas ~2h, geolocalizados por el **lugar
  del suceso** (ActionGeo). Pueblan la capa de superficie + el mapa de calor; se
  cargan **por defecto**, sin subir nada.
- **Cómo:** ficheros `export.CSV.zip` que GDELT publica cada 15 min; el panel agrega
  las 8 últimas ventanas, deduplica por id y cachea 15 min (`_cached_gdelt_events`).
- **Sin clave.** Validado: ~440 eventos/2h en ~2s.
- **Naturaleza:** `asserted` — evento extraído de prensa por GDELT, **no verificado**
  por Titan Eye. El conteo es **densidad de reportes**, NO intensidad ni bajas
  (ADR-0003); las víctimas nunca son peso del mapa. El halo del globo refleja la
  resolución de geolocalización declarada (país/región/ciudad), nunca un punto
  nítido sobre una posición aproximada (P2).

### Bases militares · OpenStreetMap / Overpass (sin clave)

- **Qué:** instalaciones militares mapeadas en OSM (bases navales, aeródromos
  militares, cuarteles, bases del ejército) en la capa de referencia (ADR-0017).
- **Cómo se sirve:** por defecto desde un **snapshot bundleado** en
  `data/osm_military_bases.json` (dato real de OSM, capturado y versionado) →
  carga **instantánea, sin red**. Un barrido global en vivo de Overpass es lento
  (~1-2 min) y satura la instancia pública, por eso es solo un **refresco opcional**
  (`_fetch_osm_bases`, con fallback entre mirrors).
- **Naturaleza:** `asserted` — geografía pública mantenida por la comunidad;
  **puede estar incompleta o desactualizada** y los emplazamientos sensibles a
  menudo no están mapeados (P2). Ausencia ≠ inexistencia. Solo display: sin
  proximidad-a-objetivo ni cómputo operacional (ADR-0017). © OpenStreetMap (ODbL).

### Clasificación militar de satélites

Cada satélite se clasifica además por **misión** (la categoría del grupo CelesTrak
de origen: navegación GPS/GLONASS/BeiDou/Galileo, militar, radar/vigilancia,
NNSS…) y por **régimen orbital** (LEO/MEO/GEO/HEO, derivado de física pública).
Son clasificaciones de la fuente y de la física, no inferencias de Titan Eye; se
pueden filtrar por misión en el panel (p. ej. solo navegación o solo militar).

---

## Requieren clave gratuita o un dataset que aportas tú

Estos no se cargan solos para no inventar nada ni filtrar una clave en el repo.
Actívalos en la barra lateral subiendo un JSON, o (marítimo) con tu clave.

### ⚓ Marítimo — AIS (AISStream)

- **Qué es:** posiciones AIS de buques (MMSI, tipo, rumbo, velocidad, bandera).
- **Clave:** **sí, gratuita** en [aisstream.io](https://aisstream.io/) (WebSocket).
  También sirve cualquier export AIS público en JSON.
- **Formato que acepta el normalizador:** lista de buques, o `{"vessels":[...]}` /
  `{"states":[...]}`. Mapea tipos AIS conocidos a clases descriptivas
  (portaaviones, destructor, fragata, submarino, anfibio, patrullero).
- **Honestidad (ADR-0015):** el AIS es **autodeclarado y falsificable**; los buques
  de guerra lo apagan o falsean y los submarinos sumergidos no transmiten.
- **Naturaleza:** `observed` (autodeclarado).

### 🔥 Superficie — eventos de conflicto (GDELT / ACLED)

- **GDELT:** gratuito, sin clave, near-real-time (~15 min). API de eventos/GKG.
- **ACLED:** requiere clave gratuita; cadencia semanal, geolocalización curada.
- **Qué hace Titan Eye:** ingiere el dataset, declara `geoloc_resolution` por
  evento y calcula un **mapa de calor por KDE** con ancho de banda declarado.
- **Aviso (ADR-0003):** el peso del heatmap mide **densidad de eventos
  reportados**, NO intensidad de conflicto ni amenaza. Más cobertura ≠ más guerra.
- **Naturaleza:** `asserted` (lo afirma un tercero; Titan Eye no lo verifica).

### 🚀 Suborbital — reportes balísticos

- **Qué es:** un reporte público (NOTAM, aviso, nota de prensa) de un lanzamiento,
  con apogeo/alcance/coordenadas declarados.
- **Qué hace Titan Eye:** **reconstruye** la trayectoria con un modelo Kepleriano
  de vacío de solución cerrada y una **banda de incertidumbre declarada**.
- **Naturaleza:** el reporte es `asserted`; la trayectoria es `inferred`. **Nunca**
  se confunden (P9). Render como tubo de error, nunca línea fina.

### 🏛 Instalaciones (referencia) y ✎ OSINT

- **Instalaciones:** geografía pública estática (OpenStreetMap / Wikipedia / FAS).
  Solo display, sin cómputo operacional (ADR-0017).
- **OSINT:** ítems de noticias/RRSS con URL de origen. Titan Eye **no verifica
  veracidad** ni puntúa credibilidad; el *tier* solo describe el tipo de fuente
  (ADR-0020).
- **Naturaleza:** `asserted`.

---

## Cómo añadir tu propia fuente

1. Escribe un *source* en `src/titan_eye/ingestion/sources/` (transporte + sello
   del `RawArtifact` con su hash de procedencia).
2. Escribe un *normalizer* puro y determinista en
   `src/titan_eye/catalog/normalizers/` (`Raw → Normalized`, sin red).
3. Traduce a payload de globo en
   `src/titan_eye/orchestration/globe_payload.py` (cada entrada lleva `country` y
   `kind` para los filtros, y `heading`/`course` si orienta su icono).
4. Conéctalo en la barra lateral de `app/streamlit_app.py`.

El contrato no negociable: cada dato lleva su **hash de origen** (ADR-0005) y su
**etiqueta epistémica** (P9). Si una fuente no permite declarar honestamente su
incertidumbre, no entra.
