# ADR-0012: Dominio superficie — eventos de conflicto y mapa de calor v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P2, P9), ADR-0002, ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0008

---

## Contexto

Fase 4, el cuarto y último dominio. Cubre eventos de conflicto reportados
públicamente (datasets abiertos tipo ACLED, GDELT) y el **mapa de calor** que el
usuario pidió desde el principio. Es el dominio donde es más tentador —y más
deshonesto— confundir **cobertura de reportes** con **intensidad de conflicto**.
Este ADR fija que Titan Eye mide lo primero y lo declara explícitamente.

## Decisión

1. **Eventos `asserted`.** Un `ConflictEvent` es una **afirmación de un tercero**
   (P9), no un hecho verificado por Titan Eye. Lleva su `geoloc_resolution`
   declarada (`exact` / `city` / `region` / `country`), porque la precisión de la
   geolocalización es parte de la honestidad (P2): un evento ubicado a nivel de
   región no se dibuja como un punto nítido (el render usa el halo, ADR-0004).

2. **Ingestión desde dataset estructurado.** Como el dominio suborbital (ADR-0011),
   la entrada es un fichero estructurado (JSON) que el operador exporta de la
   fuente pública, sellado como `RawArtifact` (dominio SURFACE, `asserted`) con su
   `license_note` (ACLED exige registro y atribución; GDELT es abierto — ADR-0002).
   Un adaptador con API en vivo (ACLED requiere clave) se difiere a ADR-0013
   (secretos) para no acoplar el núcleo a una credencial (P3/P7).

3. **Mapa de calor por KDE con ancho de banda declarado.** `analytics/surface/`
   computa una estimación de densidad por kernel (Gaussiano) sobre las posiciones
   de los eventos, en una rejilla lat/lon, con un **`bandwidth_km` declarado** que
   viaja en el resultado. El identificador del modelo (`KDE_KERNEL_NAME =
   "gaussian_great_circle_v1"`) encoda el kernel y la métrica (distancia de gran
   círculo).

4. **El peso es densidad de REPORTES, no de "amenaza" ni de "intensidad"
   (ADR-0003).** El peso por defecto es **1 por evento reportado** (un reporte es
   un reporte). El sistema **no** pondera por número de víctimas como proxy de
   intensidad ni emite ningún score de amenaza. La leyenda del mapa, en el globo y
   en la API, dice explícitamente "densidad de eventos **reportados**". Más
   cobertura mediática no es más guerra; confundirlas violaría P2.

5. **Persistencia e integridad en paridad** con los demás dominios:
   `ConflictEventsRepository` (Parquet/DuckDB, ADR-0008) + verificador I1/I2
   (`verify-surface`). El mapa de calor es Derived **on-demand** (se computa para
   una ventana/consulta), no se persiste (ADR-0006): es un resumen recomputable.

## Justificación

- Declarar `geoloc_resolution` y el `bandwidth_km` convierte la honestidad (P2) en
  datos de primera clase, no en una nota.
- Fijar el peso en "reportes, no intensidad" es la decisión que impide que el mapa
  de calor se deslice hacia un mapa de amenaza (la frontera de ADR-0000/0003).

## Consecuencias

**Positivas** — cuarto dominio operativo; el mapa de calor que cierra la visión
inicial; honestidad estructural sobre qué mide.
**Negativas** — sin API en vivo (requiere clave, diferido). El usuario exporta el
dataset. Aceptado: mantiene P3/P7 y la testabilidad sin red.
**Neutras** — la elección de kernel/bandwidth es del operador; el resultado
declara ambos para que cualquiera reproduzca el mapa (P1).

## Alternativas consideradas

### A. Ponderar el KDE por víctimas/severidad
**Razón de rechazo:** convierte "densidad de reportes" en un proxy de "intensidad",
exactamente el deslizamiento que ADR-0003 prohíbe. Las víctimas reportadas pueden
mostrarse como atributo del evento, nunca como peso del mapa de calor.

### B. Heatmap como bins fijos (histograma 2D)
**Razón de rechazo:** los bins duros ocultan la incertidumbre de geolocalización;
el KERNEL con bandwidth declarado representa mejor la difuminación real y es
honesto sobre la resolución.

## Alineación con ADR-0000

- **Implementa P9** (eventos `asserted`, nunca presentados como hechos),
  **P2** (geoloc_resolution + bandwidth declarados; el render usa halo),
  **P5/P7** (datasets públicos con license_note).
- **Hace cumplir ADR-0003:** el mapa mide reportes, no amenaza; sin scores.
- **Sin tensiones con la frontera ética:** cartografía de eventos ya públicos con
  su incertidumbre; ningún veredicto de intención ni de actor hostil.

## Referencias

- Raleigh, C. et al. (2010). *Introducing ACLED.* J. Peace Research.
- Leetaru, K., & Schrodt, P. (2013). *GDELT: Global Data on Events, Location and Tone.*
- Silverman, B. W. (1986). *Density Estimation for Statistics and Data Analysis* — KDE y ancho de banda.
- Orbital Sentinel, patrón de honestidad sobre incertidumbre (ADR-0008).
