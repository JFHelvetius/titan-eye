# ADR-0003: Honestidad sobre incertidumbre y prohibición de clasificar intención

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P2, P9, No-objetivos), ADR-0004, ADR-0014

---

## Contexto

Este es el ADR que más directamente implementa la columna vertebral ética y de rigor de ADR-0000. El dominio militar es precisamente donde más fácil —y más peligroso— es mentir: presentar una reconstrucción como una medición, un reporte como un hecho, o una geometría como una intención. Este ADR fija reglas duras para que el sistema no pueda hacerlo, ni siquiera por accidente.

## Decisión

### 1. La incertidumbre es un campo obligatorio, no una nota

Todo modelo de detección persistido lleva, por construcción, los campos que cuantifican su error. No hay detección sin error declarado. Ejemplos por dominio:

- **Orbital:** error baseline (km) y crecimiento (km/día) heredados del régimen SGP4, más la antigüedad del TLE usado.
- **Suborbital:** banda de incertidumbre de la trayectoria reconstruida, derivada de la incertidumbre de los parámetros de entrada (apogeo/alcance reportados con su tolerancia).
- **Aerial:** precisión nominal de la posición ADS-B y antigüedad del último mensaje; flag de posible inconsistencia (proxy de spoofing) **descriptivo, nunca acusatorio**.
- **Surface:** resolución de la geolocalización del evento (exacta / ciudad / región) tal como la declara la fuente.

### 2. La etiqueta epistémica (P9) gobierna la representación

Cada detección lleva `epistemic_label ∈ {observed, asserted, inferred}` (ADR-0002). La visualización (ADR-0004) **debe** representar la etiqueta visualmente: un `inferred` (trayectoria balística reconstruida) nunca se dibuja igual que un `observed` (posición ADS-B). Una línea fina nítida para una trayectoria reconstruida está **prohibida** como salida del proyecto, igual que en Orbital Sentinel una órbita SGP4 sin banda de error.

### 3. Prohibición dura: nada de clasificación de intención ni amenaza

El sistema **no** computa, persiste ni muestra:

- veredictos de intención ("ataque", "hostil", "defensivo"),
- scores de amenaza o de "nivel de alerta" agregado,
- probabilidades de intención o de escalada,
- identificación o atribución de objetivos.

Lo que el sistema **sí** produce: geometría con error, conteos de eventos con su procedencia, densidad de *reportes* (no de "amenaza"), proximidad geométrica con incertidumbre. La diferencia entre "dos objetos están a 4 ± 3 km" y "amenaza de colisión" es exactamente la diferencia entre Titan Eye y un sistema de targeting. El proyecto se queda, siempre, en el primer lado.

### 4. El mapa de calor mide reportes, no realidad

El mapa de calor de conflicto (ADR-0014 planificado) agrega **densidad de eventos reportados** con un kernel de ancho de banda declarado. Su leyenda dice explícitamente "densidad de eventos *reportados*", nunca "intensidad del conflicto". Más cobertura mediática no es más guerra; confundirlos sería violar P2.

## Justificación

- **P2 es inejecutable como buena intención;** este ADR lo convierte en restricciones de esquema (campos obligatorios) y de render (la etiqueta gobierna el dibujo).
- **La prohibición de intención es lo que hace legítimo el proyecto.** Un registro de detección con procedencia es transparencia OSINT; un clasificador de amenaza es otra cosa. ADR-0000 eligió ser lo primero.
- **Paralelo con Orbital Sentinel:** allí "no AI, no scoring, no threat classification — geometría con incertidumbre, nada más". Titan Eye hereda ese filo exactamente.

## Consecuencias

**Positivas** — el output es defendible y auditable; la honestidad es estructural, no convencional.
**Negativas** — el producto será "menos sensacionalista" que un dashboard de amenazas con luces rojas. Es deliberado.
**Neutras** — la ausencia de scores no impide al *usuario* sacar conclusiones; impide que *Titan Eye* las saque por él sin mostrar el dato crudo.

## Alternativas consideradas

### A. Score de amenaza opcional, desactivable
**Razón de rechazo:** "opcional" no existe una vez que el campo está en el esquema y en el render. Viola No-objetivos de ADR-0000 de forma irreversible.

### B. Clasificación de intención con incertidumbre declarada
**Razón de rechazo:** declarar la incertidumbre de un veredicto de intención no lo hace honesto; lo hace una mentira con barra de error. El dato público no soporta inferencia de intención. P2 + No-objetivos.

## Alineación con ADR-0000

- **Implementa P2 y P9** directamente (campos obligatorios + etiqueta que gobierna el render).
- **Hace cumplir los No-objetivos** sobre intención/amenaza, convirtiéndolos en restricciones de esquema.
- **Sin tensiones.** Es la materialización de la frontera ética del proyecto.

## Referencias

- Orbital Sentinel, ADR-0008 y "What this is not" (no scoring, no threat classification).
- Tufte, E. (1983). *The Visual Display of Quantitative Information.*
- Munzner, T. (2014). *Visualization Analysis and Design* — representación de incertidumbre.
