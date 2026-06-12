# ADR-0010: Dominio orbital — TLE + propagación SGP4 v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0008, ADR-0009

---

## Contexto

Fase 2. El dominio orbital observa satélites militares/dual-use a partir de TLEs
públicos (CelesTrak, ADR-0002). Es el dominio donde Titan Eye más directamente
reutiliza el conocimiento del proyecto hermano Orbital Sentinel: el régimen
TLE+SGP4, su error característico y su matemática están ya validados allí.

## Decisión

1. **Fuente y Raw:** `ingestion/sources/celestrak.py` adquiere texto TLE por
   GROUP (p. ej. `active`, `stations`, grupos militares públicos) o por CATNR,
   y lo sella como `RawArtifact` (dominio ORBITAL, `observed`, license_note de
   CelesTrak). Reusa transporte/cache/reloj de ADR-0009.

2. **Normalized `OrbitalElement`:** parser TLE estricto por columnas que produce
   un modelo frozen por satélite, conservando **las dos líneas originales**
   (`line1`, `line2`) y el `tle_content_hash = sha256(line1+\n+line2)`, además de
   los elementos keplerianos parseados (inclinación, RAAN, excentricidad, arg.
   perigeo, anomalía media, movimiento medio) y la época. FK por hash al Raw
   (`content_hash_source`).

3. **Propagación SGP4 on-demand:** `analytics/propagation/` envuelve la librería
   `sgp4` (Vallado/Rhodes). **Construye el `Satrec` con `twoline2rv(line1,line2)`**
   desde las líneas originales —nunca desde campos parseados— para mantener
   coherencia bit-exacta con la librería. No persiste efemérides (ADR-0006): el
   volumen sería enorme; se calculan bajo demanda.

4. **Marcos de referencia declarados:** salida nativa TEME → ECEF vía GMST
   (IAU 1982 simplificado, UT1≈UTC) → geodésica esférica para groundtrack. El
   modelo GMST y la Tierra esférica se declaran como identificadores
   (`GMST_MODEL_NAME`, nota de error sub-km vs WGS84), muy por debajo del
   régimen SGP4 dominante.

5. **Honestidad sobre incertidumbre (P2, ADR-0003):** cada salida declara el
   error baseline (~1–3 km en época) y crecimiento (~1–3 km/día), más la
   antigüedad del TLE. El render del globo dibuja groundtrack con esa
   incertidumbre, no como verdad nítida. **Ningún veredicto de intención** sobre
   "satélite militar": la etiqueta de tipo/operador proviene del catálogo
   público y es descriptiva, nunca acusatoria.

6. **Persistencia e integridad en paridad con la aérea:** `OrbitalElementsRepository`
   (Parquet/DuckDB, ADR-0008, un archivo por snapshot) + verificador de
   integridad I1 (referencial) e I2 (reproducibilidad del parseo).

## Justificación

- Reutilizar SGP4 valida la decisión arquitectónica de "heredar protocolos del
  hermano" en el dominio donde más madura está.
- Conservar las líneas originales y construir con `twoline2rv` evita acoplar la
  precisión física a la fidelidad del parser (lección directa de Orbital Sentinel).

## Consecuencias

**Positivas** — segundo dominio `observed` operativo; groundtracks 3D en el globo;
matemática validada.
**Negativas** — el parser TLE por columnas es frágil ante formatos no estándar;
se mitiga con validación estricta y errores tipados con línea/columna.
**Neutras** — la propagación on-demand implica recomputar para cada vista; es el
trade-off correcto frente a materializar terabytes (P3).

## Alternativas consideradas

### A. Persistir efemérides propagadas
**Razón de rechazo:** viola P3 a escala de catálogo. On-demand es el patrón de Orbital Sentinel.

### B. Construir `Satrec` con `sgp4init()` desde campos parseados
**Razón de rechazo:** acopla la precisión a la fidelidad del parser. `twoline2rv` desde las líneas originales es bit-exacto con la librería.

## Alineación con ADR-0000

- **Refuerza P1** (líneas originales + hash; propagación determinista), **P2**
  (error declarado), **P5/P7** (CelesTrak público con license_note), **P9**
  (`observed` sellado).
- **No roza la frontera ética:** posiciones orbitales públicas; tipo/operador
  descriptivos del catálogo, sin clasificación de intención.

## Referencias

- Hoots & Roehrich (1980). *Spacetrack Report No. 3.*
- Vallado, D. A. (2013). *Fundamentals of Astrodynamics and Applications.*
- Rhodes, B. *python-sgp4.*
- Orbital Sentinel, ADR-0005/0014 (SGP4) y `propagation/frames.py`.
