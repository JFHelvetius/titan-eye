# ADR-0020: Capa OSINT — noticias y redes sociales geolocalizadas v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P7, P9), ADR-0002, ADR-0003, ADR-0008, ADR-0012

---

## Contexto

La visión pide una capa OSINT: noticias verificadas (Reuters, AP, BBC, medios
gubernamentales/locales) y publicaciones de redes sociales geolocalizadas. Es
información **sobre** eventos, no una observación física de un objeto. Es la capa
donde más fácil es confundir "una fuente lo dice" con "es verdad". Este ADR fija
que Titan Eye registra la **afirmación con su procedencia**, nunca un veredicto de
veracidad.

## Decisión

1. **`OsintItem` (`asserted`).** Cada ítem es la afirmación de una fuente,
   geolocalizada: título, posición, `source` (nombre), `source_url`,
   `published_at`, `source_tier`, resumen. La etiqueta epistémica es siempre
   `asserted`: es lo que una fuente afirma, no lo que Titan Eye verifica.

2. **`source_tier` lo declara el OPERADOR, no lo juzga el sistema.** Es una
   clasificación del *tipo de fuente* (`news_agency`, `government`, `local_media`,
   `social_media`, `other`), no de la veracidad del contenido. "news_agency" no
   significa "verdadero", significa "procede de una agencia de noticias". El
   `social_media` se marca como tier de menor validación, descriptivamente.

3. **Titan Eye NO verifica veracidad ni puntúa credibilidad/desinformación
   (ADR-0003).** No hay detector de fake news, ni score de confianza, ni veredicto
   "verificado por Titan Eye". Lo que el sistema garantiza es la **procedencia**:
   qué fuente lo dijo, cuándo, con qué URL, atado por hash al Raw (ADR-0005).
   Verificar el contenido es trabajo del lector, con la procedencia que se le da.

4. **Capa de contexto, no dominio físico.** Como las instalaciones, el OSINT no es
   uno de los cinco dominios de observación física; es información. Se etiqueta su
   Raw con `Domain.OSINT` (tag, no dominio de actividad) y vive como capa propia
   (`osint`) en el payload del globo, togglable.

5. **Persistencia e integridad** en paridad (Parquet + verify-osint, ADR-0008). El
   filtro por país/tipo (ADR-0018) aplica: `country` del ítem, `kind` = source_tier.

## Justificación

- La única afirmación honesta que un agregador OSINT puede hacer es "esta fuente,
  identificable, dijo esto, y aquí está el enlace": eso es procedencia, no verdad.
  Coincide con P9 (asserted) y con la misión de transparencia de ADR-0000.
- Distinguir el *tier de fuente* sin juzgar veracidad evita el deslizamiento a
  "scoring de credibilidad", que sería un veredicto (ADR-0003).

## Consecuencias

**Positivas** — capa de inteligencia en tiempo real con procedencia auditable;
contexto narrativo sobre los eventos del globo.
**Negativas** — geolocalizar noticias/RRSS es ruidoso y manipulable; se mitiga con
la etiqueta `asserted`, el `source_tier` declarado y la advertencia explícita de
que el sistema no verifica veracidad.
**Neutras** — ingestión desde dataset estructurado (el operador exporta de su
fuente/API OSINT); un adaptador en vivo (API con clave) se difiere a ADR de secretos.

## Alternativas consideradas

### A. Puntuar credibilidad / detectar desinformación
**Razón de rechazo:** es un veredicto de veracidad/intención prohibido (ADR-0003).
El sistema da procedencia; el juicio es del lector.

### B. Marcar ítems como "verificado" (sello de Titan Eye)
**Razón de rechazo:** Titan Eye no verifica contenido. "Verificado" induciría a
error. Solo se declara el *tipo* de fuente, no la verdad del contenido.

## Alineación con ADR-0000

- **Refuerza P7** (fuentes públicas), **P9** (`asserted`; procedencia, no verdad),
  **ADR-0003** (sin score de credibilidad ni detección de desinformación).
- **Sin tensiones con la frontera ética:** registro de afirmaciones públicas con
  su procedencia, para transparencia.

## Referencias

- Bellingcat / OSINT práctica: la procedencia y el enlace original son la unidad de verificación.
- ADR-0012 (superficie, asserted con resolución declarada) — patrón análogo.
