# ADR-0011: Dominio suborbital — reconstrucción balística v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P2, P9), ADR-0001, ADR-0003, ADR-0004, ADR-0005, ADR-0006

---

## Contexto

Fase 3. El dominio suborbital es el **más delicado en honestidad** de todo el
proyecto: a diferencia del aéreo (ADS-B) y el orbital (TLE), **no existe un track
de sensor público**. Lo que hay son **reportes**: NOTAMs, avisos de zona marítima
cerrada, comunicados oficiales, prensa, que declaran parámetros de un lanzamiento
balístico (punto de lanzamiento, apogeo, alcance, hora). A partir de esos
parámetros, Titan Eye **reconstruye** una trayectoria.

Esto cruza dos categorías epistémicas (P9) en un solo flujo:
- El **reporte** es `asserted` (afirmado por un tercero, con procedencia).
- La **trayectoria reconstruida** es `inferred` (calculada por Titan Eye con un
  modelo declarado).

El sistema nunca debe presentar la reconstrucción como una medición. Este ADR fija
cómo se mantiene esa distinción y cómo se declara la incertidumbre del modelo.

## Decisión

1. **Dos modelos, dos etiquetas epistémicas:**
   - `BallisticReport` (`asserted`): el reporte público estructurado — punto de
     lanzamiento, punto de impacto, apogeo reportado, sus tolerancias declaradas,
     fuente y URL. Es el Raw/Normalized del dominio: la afirmación de un tercero.
   - `BallisticTrajectory` (`inferred`): la trayectoria reconstruida — puntos
     (lat, lon, alt), elementos derivados (semieje, excentricidad, alcance,
     altitud máxima) y su **banda de incertidumbre declarada**. FK por hash al
     report (`content_hash_source`, ADR-0005).

2. **Modelo físico v0.1 — balística Kepleriana de vacío:** la trayectoria es una
   elipse Kepleriana (masa puntual, foco en el centro de la Tierra) sobre **Tierra
   esférica, sin rotación, sin arrastre atmosférico**. Dado el punto de lanzamiento,
   el de impacto (→ ángulo central Φ por gran círculo) y el apogeo r_a = R + h_a,
   la excentricidad y el semieje tienen **solución cerrada**:

   ```
   ρ = r_a / R ;  c = cos(Φ/2)
   e = (ρ − 1) / (ρ − c)
   a = r_a / (1 + e)
   ```

   La trayectoria es simétrica con el apogeo en el punto medio del gran círculo.
   Se muestrea r(θ) = a(1−e²)/(1 − e·cos θ) para θ ∈ [−Φ/2, +Φ/2].

3. **Incertidumbre declarada, no fabricada (P2, ADR-0003):** la banda se calcula
   **linealizada** desde las tolerancias declaradas del reporte (σ del apogeo, σ
   de geolocalización) **más un suelo de error del modelo** (`MODEL_UNCERTAINTY_KM`)
   que representa explícitamente la física omitida (rotación terrestre, arrastre,
   achatamiento). No se hace un Monte Carlo que aparente una precisión que el
   modelo de vacío no tiene. El identificador del modelo (`BALLISTIC_MODEL_NAME =
   "keplerian_vacuum_spherical_nonrotating_v1"`) encoda las asunciones; una
   versión con Tierra rotante y arrastre exigirá un identificador distinto.

4. **Render honesto (ADR-0004):** la trayectoria `inferred` se dibuja como **tubo
   / corredor de incertidumbre**, nunca línea fina. El impacto lleva su elipse de
   dispersión. El infobox declara "RECONSTRUCCIÓN desde reporte público · NO es
   track de sensor".

5. **Ingestión sin red:** el reporte es un JSON estructurado que el operador compone
   desde fuentes públicas. Se sella como `RawArtifact` (dominio SUBORBITAL,
   `asserted`) con la misma cadena de procedencia que las demás fuentes.

6. **Persistencia justificada (ADR-0006):** una `BallisticTrajectory` es un Derived
   **raro y valioso** (un evento, no millones de muestras); su pérdida rompería el
   registro histórico. Se persiste (a diferencia de la propagación orbital, que es
   masiva y on-demand). Identidad content-addressable por hash del reporte + modelo.

## Justificación

- La solución cerrada Kepleriana es exacta para el régimen de vacío y trivial de
  testear (el apogeo de la trayectoria reconstruida == apogeo de entrada; el
  alcance == gran círculo). Esto da una base verificable antes de añadir física.
- Cruzar `asserted`→`inferred` en un flujo declarado es exactamente la garantía P9
  que distingue a Titan Eye de un sistema que afirma certezas.

## Consecuencias

**Positivas** — tercer dominio operativo; trayectorias verificables; honestidad
epistémica máxima en el dominio donde más importa.
**Negativas** — el modelo de vacío sin rotación tiene error real (decenas de km en
impacto para alcances largos). Se declara como `MODEL_UNCERTAINTY_KM` y se documenta
como deuda a cerrar en v0.2 (Tierra rotante) / v0.3 (arrastre). No se esconde.
**Neutras** — si no se reporta apogeo, v0.1 lo exige; la trayectoria de mínima
energía (apogeo implícito por alcance) es v0.2.

## Alternativas consideradas

### A. Monte Carlo sobre los parámetros de entrada
**Razón de rechazo (para v0.1):** un Monte Carlo sobre un modelo de vacío produce
una banda de aspecto riguroso que no captura el error dominante (la física omitida).
Es más honesto declarar la banda linealizada + suelo de modelo. Monte Carlo entra
cuando el modelo físico sea realista (v0.2+).

### B. Trayectoria con empuje (boost phase modelado)
**Razón de rechazo:** requiere parámetros (perfil de empuje, masa) que los reportes
públicos no dan. Quedaría fuera de P7 (reproducible con datos públicos).

## Alineación con ADR-0000

- **Implementa P9** (asserted→inferred declarado, nunca colapsado), **P2** (banda +
  suelo de modelo declarados; identificador de modelo machine-readable), **P5/P7**
  (reportes públicos con procedencia).
- **Hace cumplir ADR-0003/0004:** tubo de error, nunca línea fina; ningún veredicto
  de intención (el reporte describe un lanzamiento observado públicamente, Titan Eye
  reconstruye su geometría, no juzga su propósito).
- **Sin tensiones con la frontera ética:** reconstrucción geométrica de un evento
  ya público, con incertidumbre declarada. No es targeting ni predicción de fuego.

## Referencias

- Wright, D., & Grego, L. *Ballistic missile trajectory estimation from public data.*
- Vallado, D. A. (2013). *Fundamentals of Astrodynamics and Applications* — mecánica orbital de dos cuerpos.
- Orbital Sentinel, patrón Derived persistido con justificación (ADR-0019).
