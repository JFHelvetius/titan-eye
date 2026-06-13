# ADR-0018: Filtro transversal por país y tipo v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P2, P9), ADR-0003, ADR-0004

---

## Contexto

Con cinco dominios y la capa de referencia, el seguimiento sólo es *operable* si
se puede acotar: ver solo las aeronaves de un país, solo la flota de otro, solo
las centrales nucleares. Es un **filtro de vista**, transversal a todos los
dominios: no añade inferencia ni cambia el dato, solo selecciona lo ya observado.

## Decisión

1. **Dos ejes de filtro: `country` y `category`.** Cada entrada del payload del
   globo expone, además de su geometría, un `country` y un `category`
   (string; `""` si el dato no lo soporta). El filtro es una **función pura** que
   conserva las entradas cuyo país ∈ selección (si hay) y cuya categoría ∈
   selección (si hay). Sin selección, no filtra.

2. **`category` = la clase primaria de cada capa** (descriptiva, ADR-0003):
   aéreo→clase de aeronave (si la fuente la da), marítimo→tipo de buque,
   superficie→tipo de evento, suborbital→`ballistic`, instalaciones→tipo de
   instalación. Orbital queda sin clase en v0.1 (clasificar satélites exige un
   satcat; diferido).

3. **`country` desde el dato real disponible** (P2, honestidad sobre lo que se
   sabe): aéreo→país de origen ADS-B, marítimo→bandera, superficie→país del
   reporte (campo nuevo en `ConflictEvent`, lo trae ACLED), instalaciones→país.
   Orbital y suborbital quedan con país `""` salvo que el dataset lo aporte: el
   TLE no lleva operador y un reporte balístico no siempre lo dice. **No se
   inventa el país; vacío es vacío.**

4. **El filtro no recalcula agregados.** El mapa de calor (KDE) es un agregado de
   superficie; el filtro de vista no lo recomputa (sería otra operación). Se
   documenta para no confundir "filtrado" con "recomputado".

5. **Sin clasificación de bando ni amenaza (ADR-0003).** Filtrar por país es
   selección descriptiva, no atribución de hostilidad. No hay categoría "enemigo"
   ni "amigo": solo el país declarado por el dato y la clase técnica del objeto.

## Justificación

- Un filtro de vista puro mantiene la honestidad: opera sobre lo observado, no
  produce conocimiento nuevo. El `country`/`category` vacío es la declaración
  honesta de "este dato no lo soporta" (P2/P9).

## Consecuencias

**Positivas** — el seguimiento se vuelve operable por país y por tipo en los cinco
dominios + referencia.
**Negativas** — país orbital/suborbital y clase de aeronave/ satélite quedan
parcialmente vacíos en v0.1 (faltan reference DB / satcat); declarado, no oculto.
**Neutras** — el filtro vive en `analytics/filtering.py` (puro) y se aplica en el
dashboard; la CLI puede adoptarlo después.

## Alternativas consideradas

### A. Clasificar bando/afiliación (aliado/adversario) por país
**Razón de rechazo:** es atribución de hostilidad = juicio prohibido (ADR-0003).
Solo se filtra por país declarado y clase técnica, sin etiqueta de bando.

### B. Inferir país de satélites/aeronaves sin fuente
**Razón de rechazo:** inventar el país viola P2. Vacío honesto en su lugar.

## Alineación con ADR-0000

- **Refuerza P2/P9** (país/clase vacíos cuando el dato no los soporta; nada
  inventado) y **ADR-0003** (sin bando ni amenaza; filtro descriptivo).
- **Sin tensiones con la frontera ética:** es selección de vista sobre datos
  públicos ya mostrados.

## Referencias

- ACLED codebook (campo país por evento).
- OpenSky (origin_country); AIS (flag state).
