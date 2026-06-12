# Contribuir a Titan Eye

Gracias por tu interés. Titan Eye es un **registro de detección verificable** de
eventos militares observables con datos públicos. Antes de contribuir, lee la
brújula del proyecto: [`docs/adr/0000-long-term-vision.md`](docs/adr/0000-long-term-vision.md).

## Frontera de alcance (no negociable)

El proyecto **nunca** acepta cambios que lo muevan hacia:

- **targeting** o apoyo a decisión de fuego,
- **clasificación de intención o amenaza** (scores de "ataque", "actor hostil", riesgo de intercepción),
- **fuentes clasificadas, filtradas o de pago** como dependencia.

Producimos **geometría con incertidumbre declarada y procedencia**, nunca
veredictos (ADR-0003, ADR-0014). El mapa de calor mide densidad de eventos
*reportados*, no intensidad de conflicto. Una PR que cruce esta frontera se cierra
sin merge, por mucho que el código sea bueno.

## Requisitos de toda PR

1. **Tests sin red en verde.** La suite no toca Internet: usa `FakeTransport` y
   reportes/datasets locales. Cualquier escape a red en un test es un bug.
   ```bash
   pip install -e ".[dev,app]"
   pytest -q
   ```
2. **Lint limpio.** `ruff check src app tests` sin errores.
3. **Honestidad sobre incertidumbre (P2).** Toda detección lleva su error
   declarado; toda visualización lo representa (nada de líneas finas para `inferred`).
4. **Procedencia (P9).** La etiqueta epistémica (`observed`/`asserted`/`inferred`)
   nace en la ingestión y viaja sellada; nunca se "asciende" en silencio.
5. **ADR para decisiones.** Una decisión arquitectónica sin ADR no se considera
   tomada (P6). Usa [`docs/adr/template.md`](docs/adr/template.md); incluye la
   sección obligatoria "Alineación con ADR-0000".

## Arquitectura

Siete planos con dependencias hacia abajo (ADR-0001) × cuatro dominios
(orbital/suborbital/aéreo/superficie). Ver [`docs/architecture/planes.md`](docs/architecture/planes.md).
Cada plano debe poder borrarse sin romper los inferiores.

## Cómo contribuir

- **Datos:** publica casos de situación (`titan-eye build-case`) sobre eventos
  reales y compártelos; cualquiera puede verificarlos con `verify-case`.
- **Código:** abre una issue describiendo el cambio antes de una PR grande.
- **Auditoría:** coge un caso publicado, córrele los verificadores y publica tu
  reporte. Productor y revisor tienen garantías criptográficas idénticas.

## Licencia

Al contribuir, aceptas que tu aportación se licencie bajo [Apache-2.0](LICENSE).
