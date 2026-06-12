# ADR-0007: Licencia Apache-2.0

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P5)

---

## Contexto

P5 fija una licencia permisiva. Este ADR la concreta y explica por qué la permisividad de la licencia convive con un diseño de producto deliberadamente orientado a la transparencia (ADR-0000, sección de alcance).

## Decisión

La licencia del proyecto es **Apache-2.0**. Permite uso comercial, derivado y sublicensing, e incluye concesión expresa de patentes y cláusula de defensa de patentes.

## Justificación

- **Permisividad alineada con la misión de transparencia:** queremos que periodistas, investigadores y ONGs construyan sobre Titan Eye sin fricción legal.
- **Concesión de patentes:** Apache-2.0 protege a los usuarios frente a reclamaciones de patentes de contribuyentes, algo que MIT/BSD no cubren.
- **Neutralidad de licencia ≠ neutralidad de diseño.** La licencia no filtra usuarios ni casos de uso (sería inejecutable y contrario al espíritu open source). Pero la licencia no obliga al proyecto a *construir* funciones de targeting: lo que el proyecto decide construir lo gobierna ADR-0000, no la licencia. Un tercero puede forkear y añadir lo que quiera; ese fork ya no es Titan Eye.

## Consecuencias

**Positivas** — adopción sin fricción; protección de patentes; compatibilidad con el ecosistema científico Python.
**Negativas** — un fork podría añadir capacidades que ADR-0000 prohíbe. Aceptado: es el precio de la permisividad, y la responsabilidad recae en el fork, no en el proyecto.
**Neutras** — coincide con la licencia del proyecto hermano Orbital Sentinel.

## Alternativas consideradas

### A. MIT/BSD
**Razón de rechazo:** sin concesión de patentes.

### B. Licencia con cláusula ética (p. ej. prohibición de uso militar)
**Razón de rechazo:** no es open source (viola la Open Source Definition), es inejecutable en la práctica, y desplaza la responsabilidad de diseño —que ADR-0000 ya asume explícitamente— a un texto legal que nadie podría hacer cumplir. La frontera ética se mantiene en el *diseño del producto*, no en la licencia.

## Alineación con ADR-0000

- **Implementa P5.**
- **Coherente con la sección de alcance:** la neutralidad legal y la orientación de diseño hacia la transparencia son compatibles y están explicadas.
- **Sin tensiones.**

## Referencias

- Apache Software Foundation. *Apache License, Version 2.0.*
- Open Source Initiative. *The Open Source Definition.*
