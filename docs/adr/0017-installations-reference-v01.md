# ADR-0017: Capa de referencia de instalaciones (bases e infraestructura) v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P7, P9, No-objetivos), ADR-0002, ADR-0003, ADR-0008

---

## Contexto

La visión de producto pide capas de **bases militares** (aéreas, navales,
estratégicas, silos, centros de mando) e **infraestructura crítica** (centrales
eléctricas/nucleares, refinerías, puertos, aeropuertos, presas). A diferencia de
los cinco dominios, esto no es actividad observable que se mueve: es **geografía
de referencia estática**, una capa de contexto sobre la que se leen los dominios.

Es también la capa más adyacente a "desarrollo de objetivos". Por eso este ADR
fija con precisión qué es (referencia pública descriptiva) y qué nunca será
(insumo de targeting).

## Decisión

1. **Capa de referencia, no un dominio.** Las instalaciones no son detecciones de
   actividad; son contexto geográfico. Viven en una capa propia (`installations`),
   separada del eje de los cinco dominios. Son **`asserted`** (ubicaciones
   afirmadas por fuentes públicas), estáticas, sin posición en tiempo real.

2. **Solo fuentes públicas (P7).** Las ubicaciones provienen de fuentes abiertas
   (OpenStreetMap, Wikipedia, FAS, registros públicos). Nada clasificado ni
   filtrado. La `license_note` y la `source` viajan con el dato. El operador aporta
   un dataset JSON (como en superficie/marítimo); no hay descubrimiento propio.

3. **Modelo `Installation`** con `installation_type` (air_base, naval_base,
   army_base, missile_silo, command_center, radar_site, strategic, power_plant,
   nuclear_plant, refinery, port, airport, dam, other) y `category`
   (`military` | `critical_infrastructure`). Descriptivo, nunca un juicio.

4. **Honestidad (P2/P9):** las ubicaciones públicas pueden estar **desactualizadas
   o ser aproximadas**; se conserva la etiqueta `asserted` y una nota que lo
   declara. La capa se dibuja como referencia (marcadores discretos), distinta de
   las detecciones de actividad.

5. **Frontera dura (ADR-0000 No-objetivos, ADR-0003):** el sistema **no** computa
   nada operacional con estas instalaciones — ni proximidad-a-objetivo, ni índice
   de vulnerabilidad, ni priorización, ni recomendación. Es **visualización de
   geografía pública**, igual que Liveuamap, Wikipedia o un atlas muestran bases.
   Por decisión de diseño, las instalaciones **no entran** en el cálculo de
   proximidad geométrica (ADR-0014): son contexto, no entidades rastreadas, y
   mantenerlas fuera evita cualquier lectura de "activo cerca de objetivo".

## Justificación

- La geografía de instalaciones es información pública de contexto; mostrarla es
  conciencia situacional / OSINT, no targeting.
- Excluirla explícitamente del análisis operacional (proximidad, scoring) es lo que
  mantiene la capa del lado correcto de la frontera de ADR-0000.

## Consecuencias

**Positivas** — el globo gana contexto geográfico (la capa que más "llena"); base
para leer la actividad de los dominios sobre el terreno.
**Negativas** — es la capa más sensible; se mitiga con (a) solo fuentes públicas,
(b) etiqueta `asserted` + nota de posible desactualización, (c) exclusión explícita
de todo cómputo operacional.
**Neutras** — persistencia e integridad (I1/I2) en paridad con los dominios, porque
el patrón es barato y aporta auditabilidad de procedencia.

## Alternativas consideradas

### A. Modelar instalaciones como un sexto dominio
**Razón de rechazo:** los dominios son actividad observable; las instalaciones son
geografía estática. Mezclarlas confundiría el eje de incertidumbre.

### B. Calcular proximidad activo↔instalación o índice de vulnerabilidad
**Razón de rechazo:** es exactamente el deslizamiento hacia targeting que ADR-0000
prohíbe permanentemente. La capa es solo display.

## Alineación con ADR-0000

- **Refuerza P7** (solo fuentes públicas), **P9** (`asserted` + nota de aproximación).
- **Hace cumplir No-objetivos / ADR-0003:** sin cómputo operacional, sin scoring,
  sin proximidad-a-objetivo. Solo geografía pública descriptiva.

## Referencias

- OpenStreetMap; Wikipedia; Federation of American Scientists (FAS) — registros públicos de instalaciones.
- Liveuamap; ACLED — precedentes de capas de referencia OSINT públicas.
