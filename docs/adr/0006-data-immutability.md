# ADR-0006: Inmutabilidad y versionado de las capas de datos

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P1, P4), ADR-0005, ADR-0001

---

## Contexto

Un registro histórico citable por hash (visión de ADR-0000) es incompatible con datos mutables. Si una fila se puede sobrescribir, el hash que alguien citó ayer deja de reproducirse hoy.

## Decisión

- **Append-only.** Las capas Raw y Normalized son inmutables: se insertan, nunca se hacen UPDATE ni DELETE. Una corrección es un **nuevo** artefacto con nuevo hash, no una mutación del anterior.
- **Idempotencia por contenido.** Insertar dos veces los mismos bytes/el mismo modelo canónico es un no-op: la identidad por hash (ADR-0005) ya garantiza que no hay duplicados.
- **Versionado explícito en cada fila.** Cada registro persistido lleva las versiones que lo produjeron, independientes entre sí:
  - `schema_version` — versión del esquema de la fila.
  - `engine_version` — versión del motor que la calculó (normalizador, propagador, agregador).
  - `dataset_version` / `source_id` — identidad de la fuente y su snapshot.
  Múltiples `engine_version` coexisten sobre el mismo dato crudo: recalcular con un motor nuevo **añade** filas, no reemplaza las viejas. Así una detección histórica sigue reproduciéndose con su motor original.
- **Datos Derived: on-demand por defecto, persistido por excepción justificada.** Igual que en Orbital Sentinel, la propagación masiva (millones de muestras) se calcula bajo demanda y no se materializa. Solo se persisten los Derived raros y valiosos cuya pérdida rompería la auditoría histórica (p. ej. un registro de detección de proximidad, un evento balístico reconstruido), con justificación en su propio ADR.

## Justificación

- **P1/P4:** un hash citado se reproduce siempre porque el dato nunca cambia bajo los pies del lector.
- **Coste (P3):** materializar toda la propagación de todos los dominios reventaría un portátil. El patrón on-demand mantiene el lago de datos pequeño; lo que se persiste es la conclusión rara, no el cálculo masivo.
- **Versionado independiente** permite mejorar un motor sin invalidar la historia.

## Consecuencias

**Positivas** — historia reproducible, idempotencia, coexistencia de versiones.
**Negativas** — el lago crece monótonamente (solo añade). Mitigación: la mayoría del volumen (propagación) no se persiste; las correcciones son raras. Si en 5 años el crecimiento degrada el reader, se abre un ADR de compactación con tombstones, nunca con borrado in-place.
**Neutras** — formato concreto (Parquet particionado) lo fija ADR-0008 (planificado).

## Alternativas consideradas

### A. Mutable con tabla de auditoría
**Razón de rechazo:** la reproducibilidad pasa a depender de la auditoría en vez del dato. Frágil y no verificable por terceros.

### B. Materializar toda la propagación
**Razón de rechazo:** viola P3 a escala de cuatro dominios. El red-team de Orbital Sentinel ya estimó terabytes para un solo dominio.

## Alineación con ADR-0000

- **Implementa P1 y P4**; **refuerza P3** vía on-demand.
- **Sin tensiones.** Es disciplina de almacenamiento.

## Referencias

- Orbital Sentinel, ADR-0006 (Data Immutability) y ADR-0019 (primera tabla Derived persistente con justificación).
- Kleppmann, M. (2017). *Designing Data-Intensive Applications* — logs append-only.
