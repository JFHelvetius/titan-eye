# ADR-0016: Índice de tensión y alertas de actividad observable v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P2, P9), ADR-0003, ADR-0014

---

## Contexto

La visión del producto pide una capa de inteligencia: un **índice de tensión**
(0-100) y **alertas** de actividad militar. Es la frontera más delicada del
proyecto, porque un "índice de amenaza" opaco sería exactamente la afirmación
basada en autoridad, sin falsabilidad, que ADR-0000 combate.

Pero el proyecto ya tiene un precedente que resuelve la tensión: el proyecto
hermano Orbital Sentinel **sí computa un número de riesgo** (la probabilidad de
colisión `Pc`), y lo hace legítimo obligando a declarar **7 campos de asunciones**
que contextualizan el número (su ADR-0020). La lección: *un número derivado es
admisible si su metodología y sus componentes son transparentes y se etiqueta por
lo que es (composición de actividad observable), no por lo que no es (predicción o
veredicto de intención).* Este ADR aplica ese mismo patrón.

## Decisión

1. **Titan Tension Index (TGTI), 0-100 — composición TRANSPARENTE.** Se computa a
   partir de **conteos de actividad observable** (eventos de conflicto reportados,
   trayectorias balísticas reconstruidas, aeronaves militares, buques) mediante una
   normalización saturante declarada y pesos declarados. **Cada índice incluye su
   desglose completo por componente** (conteo crudo, valor normalizado, peso,
   contribución) y su `methodology`. No hay "número mágico": cualquiera reproduce
   el cálculo y discute los pesos.

2. **Etiqueta obligatoria (P2, P9).** El resultado lleva una `note` fija e
   inseparable: *"Índice de actividad militar OBSERVABLE reportada. NO es
   predicción de conflicto, evaluación de amenaza ni juicio de intención. Compone
   actividad ya pública con pesos declarados."* La etiqueta epistémica del índice
   es la **más débil** de sus componentes (un índice que incluye `inferred` o
   `asserted` no es `observed`).

3. **Alertas = notificaciones de actividad observada/reportada, no profecías.**
   Una alerta describe algo que **ya está en los datos públicos** ("se ha
   reconstruido una trayectoria balística en la situación", "N buques de guerra en
   la región", "N eventos de conflicto reportados"). Lleva su dominio, su conteo, su
   etiqueta epistémica y su procedencia. **No** existe la alerta "ataque inminente",
   "guerra probable" ni ningún pronóstico: el sistema no predice, **reporta lo
   observable**. Una "declaración de guerra" o un "golpe" entran solo como *evento
   reportado por una fuente pública*, con su procedencia, nunca como predicción.

4. **Prohibición que se mantiene (ADR-0000 No-objetivos, ADR-0003):** ningún
   output del proyecto computa soluciones de targeting, guiado de fuego, ni
   recomendación operacional. El índice y las alertas son material de transparencia
   y conciencia situacional, no de apoyo a la decisión de fuego.

## Justificación

- **Consistencia con el proyecto:** es el patrón `Pc`-con-asunciones de Orbital
  Sentinel (ADR-0020) aplicado a la actividad de superficie/aire/mar. El proyecto
  ya acepta computar números de riesgo *si son transparentes*.
- **Más útil y más creíble:** un índice con desglose es publicable, auditable y
  defendible; un "nivel de amenaza" opaco es ruido que nadie puede verificar.
- **Cumple la petición del usuario** (un TGTI 0-100 y alertas) sin convertir el
  proyecto en un oráculo de amenaza.

## Consecuencias

**Positivas** — capa de inteligencia operativa, transparente y reproducible.
**Negativas** — el índice es sensible a los pesos elegidos; por eso los pesos son
un dato declarado y editable, no una constante oculta. La normalización saturante
es una elección de modelo declarada (`model_name`).
**Neutras** — el índice es Derived on-demand; no se persiste (es recomputable).

## Alternativas consideradas

### A. "Nivel de amenaza" categórico (verde/ámbar/rojo) sin metodología
**Razón de rechazo:** es una afirmación de autoridad no falsable; viola P2 y el
espíritu de ADR-0000. La versión transparente da el mismo valor de UX sin la mentira.

### B. Índice predictivo (probabilidad de escalada)
**Razón de rechazo:** los datos públicos no soportan inferencia de intención
(ADR-0003). Predecir escalada sería inventar precisión. El índice mide actividad
observada, no futuro.

## Alineación con ADR-0000

- **Implementa P2/P9** (desglose + metodología + etiqueta epistémica más débil),
  reusando el patrón `Pc`-con-asunciones (Orbital Sentinel ADR-0020).
- **Respeta ADR-0003:** describe actividad observable, no clasifica intención ni
  predice; las alertas reportan, no profetizan.
- **Mantiene la frontera de No-objetivos:** sin targeting ni apoyo a fuego.

## Referencias

- Orbital Sentinel, ADR-0020 (Pc bajo covarianza declarada con assumption fields).
- ACLED; Institute for Economics & Peace, *Global Peace Index* — índices públicos de actividad/conflicto con metodología declarada.
