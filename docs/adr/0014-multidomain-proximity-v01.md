# ADR-0014: Proximidad geométrica multidominio v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P2, P9, No-objetivos), ADR-0003

---

## Contexto

Última pieza de la Fase 5. Con los cuatro dominios operativos, surge la pregunta
natural: ¿qué objetos están **geométricamente cerca** entre sí? (una aeronave y un
punto de impacto balístico estimado; un satélite sobrevolando una zona de evento).
Esta es exactamente la frontera donde un sistema se desliza de "geometría" a
"amenaza". Este ADR fija que Titan Eye se queda, siempre, en geometría con
incertidumbre declarada — igual que las conjunciones de Orbital Sentinel producen
distancia con σ, nunca un veredicto.

## Decisión

- **`find_proximities`** computa, sobre un conjunto de entidades posicionadas, los
  pares cuya **distancia horizontal** (gran círculo) está por debajo de un umbral.
  Reporta, por par:
  - `horizontal_distance_km` y `vertical_separation_km` **por separado** (nunca
    colapsados en una única "distancia"): un satélite a 400 km de altitud sobre una
    aeronave está "cerca" en tierra pero lejísimos en vertical, y el sistema lo
    muestra así.
  - `combined_uncertainty_km` = √(σ_a² + σ_b²) a partir de la incertidumbre
    declarada de cada entidad (P2).
  - las **dos etiquetas epistémicas** y la `weakest_epistemic`: una proximidad
    entre un `observed` y un `inferred` es tan sólida como el `inferred` (P9).
- **Prohibición dura (ADR-0003, No-objetivos):** el resultado **no** contiene
  score de amenaza, probabilidad de intercepción, clasificación de riesgo ni
  veredicto de intención. Lleva una `note` que lo declara explícitamente. Una
  proximidad es un hecho geométrico con error, no un juicio.
- **Representación por entidad:** cada detección aporta un punto representativo con
  su incertidumbre declarada (aeronave: posición ADS-B; satélite: punto subastral;
  evento: ubicación con radio según `geoloc_resolution`; balístico: punto de
  impacto estimado con su dispersión). El muestreo denso de trayectorias se difiere.

## Justificación

- Separar horizontal/vertical y declarar la incertidumbre combinada es la
  implementación honesta de P2 en el cruce de dominios.
- Heredar la etiqueta epistémica más débil impide presentar una coincidencia
  geométrica especulativa (con un `inferred`) como si fuera un hecho medido.
- Es el paralelo exacto de las conjunciones de Orbital Sentinel: geometría + σ, sin
  Pc presentado como certeza ni veredicto.

## Consecuencias

**Positivas** — cierra la visión "seguimiento integrado" sin cruzar a targeting;
geometría auditable y honesta.
**Negativas** — O(N²) en el número de entidades; se acota con un `max_pairs`
defensivo. El muestreo denso de arcos balísticos (proximidad continua) es v0.2.
**Neutras** — el consumidor (dashboard) decide el umbral; el resultado lo declara.

## Alternativas consideradas

### A. Un "índice de riesgo" combinando proximidad + tipo de objeto
**Razón de rechazo:** es exactamente el deslizamiento a clasificación de amenaza
que ADR-0000/0003 prohíben de forma permanente.

### B. Colapsar horizontal y vertical en una distancia 3D única
**Razón de rechazo:** oculta que dos objetos "próximos en tierra" pueden estar a
cientos de km en vertical. Reportarlos por separado es más honesto.

## Alineación con ADR-0000

- **Implementa P2** (incertidumbre combinada declarada; horizontal/vertical
  separados) y **P9** (etiqueta epistémica más débil heredada).
- **Hace cumplir los No-objetivos / ADR-0003:** ningún score de amenaza ni
  veredicto de intención. Solo geometría con error.
- **Sin tensiones con la frontera ética:** es el caso límite, y la decisión lo
  resuelve quedándose del lado de la geometría.

## Referencias

- Orbital Sentinel, análisis de conjunciones (distancia mínima con régimen de incertidumbre declarado, sin veredicto).
- ADR-0003 (honestidad sobre incertidumbre y prohibición de clasificar intención).
