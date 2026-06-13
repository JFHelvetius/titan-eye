# ADR-0019: Línea temporal histórica (replay sobre el store append-only) v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P1, P4), ADR-0006, ADR-0008, ADR-0004

---

## Contexto

La visión pide una capa histórica: conflictos activos y pasados, evolución día a
día, reproducción histórica. Titan Eye ya tiene la base perfecta para esto **por
diseño**: el almacenamiento es **append-only e inmutable** (ADR-0006), cada
snapshot Normalized lleva su tiempo y se particiona por fecha (ADR-0008). La línea
temporal no necesita infraestructura nueva: es una **lectura/replay** del store
que ya acumula historia.

## Decisión

1. **La línea temporal es una vista de lo persistido, no un nuevo almacén.** Lee
   las capas Normalized del `data-root` (lo generado con `--persist`) y las indexa
   por día según el tiempo natural de cada dominio:
   - **superficie** → `event_date` (cuándo ocurrió/se reportó el evento; es el eje
     histórico por excelencia — ACLED es dato diario);
   - **aéreo / marítimo** → día de `snapshot_time` (cuándo se capturó el snapshot).
   - **orbital, suborbital, instalaciones** quedan fuera de v0.1: orbital exige
     propagar a la fecha (no es un snapshot por día), el balístico no persiste una
     fecha de evento, y las instalaciones son geografía estática (atemporal).

2. **Dos operaciones puras** (`analytics/timeline.py`):
   - `daily_activity(items)` → serie temporal: conteo por dominio por día. Es la
     "evolución día a día".
   - `payload_for_day(items, day)` → reconstruye el payload del globo con las
     entradas de ese día (replay histórico de la situación).

3. **Honestidad (P1/P4, P2):** el replay muestra **exactamente lo que se observó/
   reportó y se persistió** ese día, atado por hash a su Raw (ADR-0005). No
   interpola entre días, no rellena huecos, no "predice" la evolución: si un día
   no tiene datos, el día está vacío, y eso se ve. Un día sin snapshot aéreo no
   significa "no había aeronaves", significa "no se capturó" (igual que la
   ausencia en AIS, ADR-0015).

4. **No recalcula agregados derivados.** El mapa de calor y el índice de tensión
   son recomputables a partir del payload del día si se desea, pero el replay v0.1
   entrega las detecciones del día; la analítica se aplica encima como en el panel
   en vivo.

## Justificación

- Es la consecuencia natural de ADR-0006: si nada se sobrescribe, la historia ya
  está ahí; solo hay que leerla por fecha. Cero almacenamiento nuevo.
- Anclar superficie a `event_date` da una línea temporal de conflicto real y
  honesta (la fecha del evento, no la de captura).

## Consecuencias

**Positivas** — "máquina del tiempo" sobre datos reales; evolución día a día;
reproduce situaciones pasadas por fecha, todo auditable por hash.
**Negativas** — orbital/suborbital fuera de v0.1 (propagación / sin fecha de
evento); declarado. Los dominios de alta cadencia (aéreo/marítimo) solo tienen
datos en los días en que se ingirió: la línea es densa donde hubo captura, vacía
donde no — y se ve, no se disimula.
**Neutras** — la serie es Derived on-demand; no se persiste (recomputable).

## Alternativas consideradas

### A. Interpolar/animar posiciones entre snapshots
**Razón de rechazo:** inventaría datos entre observaciones (viola P2). El replay
muestra observaciones reales; la animación intra-órbita ya existe para orbital vía
SampledPositionProperty cuando hay serie, pero no se inventan posiciones de
aeronaves/eventos entre días.

### B. Un almacén temporal separado (time-series DB)
**Razón de rechazo:** el store append-only particionado por fecha ya ES la serie
temporal (ADR-0006/0008). Duplicarlo sería redundante y rompería la única fuente.

## Alineación con ADR-0000

- **Refuerza P1/P4** (replay reproducible por fecha desde el store inmutable),
  **P2** (huecos visibles, sin interpolar ni rellenar).
- **Sin tensiones con la frontera ética:** es lectura histórica de lo observado.

## Referencias

- ADR-0006 (inmutabilidad append-only) y ADR-0008 (partición por fecha).
- ACLED — dataset de eventos con fecha diaria.
