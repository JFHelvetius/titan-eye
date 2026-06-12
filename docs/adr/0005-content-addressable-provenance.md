# ADR-0005: Identidad content-addressable y cadena de procedencia

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P1, P4), ADR-0002, ADR-0006

---

## Contexto

La misión exige que cualquier tercero pueda **auditar** una afirmación contra los bytes públicos que la originaron. Esto solo es posible si la identidad de cada artefacto es función de su contenido, no de un id arbitrario. Es la misma propiedad que sostiene la cadena de evidencia de Orbital Sentinel.

## Decisión

- **Identidad por hash.** Todo artefacto crudo (`RawArtifact`) se identifica por `content_hash = SHA-256(payload)` sobre los bytes exactos de la fuente. Toda detección derivada se identifica por el SHA-256 de su forma JSON canónica (`core/identity.py`, `canonical_json`: claves ordenadas, sin espacios, UTF-8, sin NaN).
- **Cadena de procedencia.** Cada modelo Normalized referencia por hash su `RawArtifact` de origen (`content_hash_source`). Cada modelo Derived referencia por hash sus entradas Normalized. El resultado es un DAG content-addressable: desde cualquier detección se llega, por hashes, hasta los bytes públicos originales.
- **Verificación como función pura.** El plano `provenance/` ofrece verificadores que, dado un artefacto y sus dependencias, **siempre devuelven un reporte** (`is_valid`, hashes comprobados, violaciones), nunca lanzan para esconder un fallo. Igual que en Orbital Sentinel: nada detrás de "confía en mí".
- **Canonical ordering para eventos simétricos.** Cuando una detección relaciona dos objetos (p. ej. proximidad geométrica A–B), la identidad se computa sobre los hashes ordenados, de modo que (A,B) y (B,A) son el mismo evento.

## Justificación

- **P1 y P4:** la reproducibilidad se verifica recomputando hashes, no confiando en metadatos. Dos personas con los mismos bytes obtienen la misma identidad.
- **Auditoría sin autoridad:** un tercero recalcula el SHA-256 del payload público y lo compara con el declarado. Si coinciden, la procedencia es válida; si no, la alteración es visible. No requiere confiar en Titan Eye.
- **Deduplicación gratis:** los mismos bytes producen el mismo hash; la cache (ADR-0002) y el catálogo (ADR-0006) son idempotentes por construcción.

## Consecuencias

**Positivas** — auditabilidad de extremo a extremo; idempotencia; detección de alteración.
**Negativas** — exige canonicalización estricta y disciplina de "nunca mutar un artefacto sellado". Cualquier campo no determinista (timestamps de proceso, orden de dict) rompería la reproducibilidad si entrara en el hash; por eso `fetched_at` se sella pero el hash de identidad de un Derived se computa sobre el contenido semántico, no sobre el momento del cálculo.
**Neutras** — SHA-256 es suficiente; no se persigue resistencia adversarial criptográfica más allá de integridad.

## Alternativas consideradas

### A. IDs autoincrementales + tabla de auditoría
**Razón de rechazo:** la identidad deja de ser verificable por un tercero sin acceso a la base de datos del productor. Rompe la auditoría sin autoridad.

### B. Firmas digitales por productor
**Razón de rechazo:** introduce gestión de claves y una autoridad. El content-addressing da integridad sin jerarquía. Las firmas pueden añadirse como capa opcional futura sobre el hash, no en su lugar.

## Alineación con ADR-0000

- **Implementa P1 y P4** (identidad y verificación por contenido).
- **Refuerza P9** (la etiqueta epistémica viaja sellada en la cadena).
- **Sin tensiones.** Es infraestructura de integridad; no roza la frontera ética.

## Referencias

- Orbital Sentinel, capa de evidencia content-addressable (cadena Raw→Normalized→Derived).
- Merkle, R. (1987). *A Digital Signature Based on a Conventional Encryption Function.*
