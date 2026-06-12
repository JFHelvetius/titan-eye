# ADR-0013: Caso de situación portable y verificable v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P1, P4, P9), ADR-0005, ADR-0006, ADR-0003

---

## Contexto

Fase 5. El proyecto ya produce detecciones en cuatro dominios con procedencia por
hash, pero esas detecciones viven en el catálogo local del productor. Para cumplir
la misión —que *cualquiera* pueda **auditar** una afirmación sobre actividad
militar observable— hace falta un artefacto **portable** que empaquete una
instantánea situacional y permita a un tercero verificarla sin acceso a la base de
datos del productor. Es el análogo del `InvestigationCase` de Orbital Sentinel.

## Decisión

- **`SituationCase`**: artefacto JSON autocontenido que empaqueta una instantánea
  de detecciones a través de dominios, con su procedencia y un **hash de caso**
  content-addressable sobre todo su contenido.
- **Una entrada por (dominio, snapshot de origen)** (`SituationCaseEntry`):
  registra el `domain`, el `source_id`, el `content_hash_source` (ancla Raw,
  ADR-0005), la `epistemic_label` (P9), el conteo de detecciones y un
  **`detections_digest`** = hash content-addressable, **invariante al orden**,
  sobre el contenido semántico de las detecciones de ese snapshot.
- **`case_hash`** = SHA-256 sobre la forma JSON canónica del caso **excluyendo el
  propio `case_hash`**. Determinista (P1): el mismo contenido produce el mismo
  hash en cualquier máquina.
- **Verificación en dos niveles:**
  1. **Auto-consistencia (pura, sin red, sin base de datos):**
     `verify_situation_case(case)` recomputa el `case_hash` y comprueba que
     coincide. Detecta cualquier manipulación del caso.
  2. **Procedencia profunda (opcional, contra la cache CAS del verificador):** un
     tercero que reingiere la misma fuente pública obtiene los mismos bytes →
     mismo `content_hash_source`, y re-normalizando reproduce el
     `detections_digest`. Sin asimetría productor/revisor.
- **Honestidad preservada (P9, ADR-0003):** cada entrada conserva su
  `epistemic_label`. Un caso nunca presenta un `inferred` (trayectoria balística)
  o un `asserted` (evento) como un `observed`. El caso **no** contiene scores de
  amenaza ni veredictos de intención: solo detecciones con procedencia.

## Justificación

- **P1/P4:** el caso es reproducible por hash; la verificación es recomputación,
  no confianza.
- **Auditoría sin autoridad:** el revisor recalcula los hashes contra fuentes
  públicas. Igual que en Orbital Sentinel, productor y revisor tienen garantías
  criptográficas idénticas.
- **Digest invariante al orden:** las lecturas de Parquet no garantizan orden; el
  digest se computa sobre el conjunto ordenado de hashes por detección, de modo
  que dos reconstrucciones del mismo dato producen el mismo digest.

## Consecuencias

**Positivas** — artefacto portable y auditable; cierra el bucle de verificabilidad
de la misión; cero dependencias nuevas (stdlib + Pydantic).
**Negativas** — el caso v0.1 guarda *digests* de las detecciones, no las
detecciones completas (para mantenerlo compacto). La verificación profunda exige
reingerir la fuente. Un caso "autocontenido con payloads embebidos" es una
extensión futura (v0.2) si se justifica.
**Neutras** — el formato es JSON canónico; versionado por `schema_version`.

## Alternativas consideradas

### A. Embeber todas las detecciones crudas en el caso
**Razón de rechazo (v0.1):** infla el artefacto. El digest + el `content_hash_source`
ya permiten verificar contra la fuente pública. Embeber payloads es opt-in futuro.

### B. Firmar el caso con clave del productor
**Razón de rechazo:** introduce gestión de claves y una autoridad. El
content-addressing da integridad sin jerarquía (ADR-0005). Las firmas pueden
añadirse *sobre* el hash, nunca en su lugar.

## Alineación con ADR-0000

- **Implementa P1/P4** (caso reproducible y verificable por recomputación),
  **P9** (etiqueta epistémica preservada por entrada), **P5/P7** (verificable
  contra fuentes públicas).
- **Hace cumplir ADR-0003:** el caso no lleva scores de amenaza ni veredictos.
- **Sin tensiones con la frontera ética:** es un contenedor de procedencia.

## Referencias

- Orbital Sentinel, ADR-0038 (Investigation Case Layer) y capa de evidencia verificable.
- Merkle, R. (1987). *A Digital Signature Based on a Conventional Encryption Function.*
