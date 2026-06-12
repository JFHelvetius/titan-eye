# ADR-0001: Arquitectura de planos por contratos de datos

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P1, P6, P8), ADR-0002, ADR-0005, ADR-0006

---

## Contexto

Titan Eye integra cuatro dominios heterogéneos (orbital, suborbital, aéreo, superficie), cada uno con su fuente, su modelo y su error. Sin una estructura disciplinada, esa heterogeneidad degenera en acoplamiento: un cambio en el parser de ADS-B rompería la visualización orbital, y la procedencia se volvería intrazable.

El proyecto hermano Orbital Sentinel resolvió un problema análogo con una **arquitectura de planos desacoplados por contratos de datos** (no microservicios). Titan Eye adopta el mismo patrón, ampliado al eje de dominio.

## Decisión

El sistema se organiza en **siete planos**, con una regla de dependencias estricta: cada plano solo puede importar de planos **inferiores**. La excepción son los *workflows* de composición en `orchestration/` (sufijo `Pipeline`/`Workflow`), que pueden importar de cualquier plano.

```
┌─────────────────────────────────────────────────────────┐
│ 7. orchestration   pipelines de composición + CLI        │  → puede importar de todos
├─────────────────────────────────────────────────────────┤
│ 6. viz             globo Cesium + dashboards (app/)       │
├─────────────────────────────────────────────────────────┤
│ 5. provenance      cadena content-addressable, integridad │
├─────────────────────────────────────────────────────────┤
│ 4. analytics       Derived: propagación, agregación       │
├─────────────────────────────────────────────────────────┤
│ 3. catalog         Raw → Normalized inmutable, versionado │
├─────────────────────────────────────────────────────────┤
│ 2. ingestion       adaptadores de fuente, transporte, CAS │
├─────────────────────────────────────────────────────────┤
│ 1. core            tipos, errores, tiempo, geodesia, hash │  → no importa de nadie
└─────────────────────────────────────────────────────────┘
```

**Eje ortogonal — dominio.** Cada plano de datos (catalog, analytics) está particionado por `Domain` (ADR-0000: orbital/suborbital/aerial/surface). Una detección pertenece siempre a exactamente un dominio. La separación por dominio es de primer nivel porque el régimen de incertidumbre de cada uno es radicalmente distinto (P2).

**Contratos de datos, no llamadas.** Los planos se comunican por modelos Pydantic frozen inmutables, no por invocaciones acopladas. Un plano superior consume el modelo de salida del inferior; nunca conoce su implementación.

## Justificación

- **Trazabilidad (P1):** la dirección única de dependencias hace que la procedencia fluya hacia arriba sin ciclos. Raw → Normalized → Derived → Provenance es un DAG.
- **Reemplazabilidad:** cualquier plano puede reescribirse detrás de su contrato sin tocar los demás. Como en Orbital Sentinel, cada capa debe poder borrarse sin romper las inferiores —prueba de fronteras limpias.
- **Local-first (P8):** ningún plano es un servicio; todo es librería. El sistema es un proceso, no una constelación de daemons.

## Consecuencias

**Positivas** — desacoplamiento real, procedencia sin ciclos, testabilidad por plano.
**Negativas** — más ceremonia de modelos/contratos que un monolito acoplado. Aceptado: es la condición de un horizonte de 5 años.
**Neutras** — el eje de dominio multiplica los módulos de catálogo/analytics por 4, pero cada uno es pequeño y aislado.

## Alternativas consideradas

### A. Monolito por capas sin contratos frozen
**Razón de rechazo:** el acoplamiento implícito rompe P1 en cuanto crece el número de dominios.

### B. Microservicios por dominio
**Razón de rechazo:** viola P8 (local-first) y P3 (coste cero). Cuatro servicios + orquestador es infraestructura, no una librería ejecutable en un portátil.

## Alineación con ADR-0000

- **Refuerza P1** (procedencia como DAG sin ciclos), **P8** (todo librería), **P6** (la arquitectura es documentable plano a plano).
- **Neutral** ante P5, P7.
- **Sin tensiones.** No roza la frontera ética: es estructura de datos.

## Referencias

- Orbital Sentinel, ADR-0002 "Planes architecture" (proyecto hermano).
- Evans, E. (2003). *Domain-Driven Design* — capas y contextos delimitados.
