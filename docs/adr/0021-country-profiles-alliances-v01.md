# ADR-0021: Fichas país y alianzas (referencia pública) v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-13
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P2, P7, P9, No-objetivos), ADR-0003, ADR-0017

---

## Contexto

La visión pide, al hacer clic en un país: presupuesto militar, personal activo/
reservas, ramas (aérea/naval/terrestre), alianzas y "amenazas activas". Es
contexto estratégico de referencia, análogo a las instalaciones (ADR-0017):
información pública estática, no observación de actividad.

## Decisión

1. **`CountryProfile` (`asserted`, referencia).** Cifras de fuentes públicas
   (SIPRI, IISS Military Balance, presupuestos oficiales): `military_budget_usd`,
   `budget_year`, `active_personnel`, `reserve_personnel`, `alliances` (lista), con
   `source`/`source_url`. Son **estimaciones públicas con su año y fuente**, no
   datos de Titan Eye. Etiqueta `asserted`.

2. **Alianzas como agrupación declarada.** Cada país lista sus `alliances`
   (NATO/CSTO/EU/UN…). La vista de alianzas se deriva agrupando países por
   pertenencia declarada. No se infiere afiliación: si el dato no lo dice, no está.

3. **NO "amenazas activas" ni ranking de poder militar (ADR-0003, No-objetivos).**
   El ítem de la lista "amenazas activas" se rechaza: sería atribución de
   hostilidad/intención. Tampoco hay "índice de poder" que ordene países por
   fuerza: eso es un veredicto comparativo. Se muestran **las cifras públicas con
   su fuente**, y el lector compara si quiere. Titan Eye no rankea ni juzga.

4. **Capa de referencia, no dominio ni globo.** Como exige polígonos de país que
   no tenemos, las fichas viven en una **pestaña del dashboard** (seleccionar país
   → ficha + alianzas), no como capa del globo. `Domain.REFERENCE` etiqueta el Raw.
   Persistencia e integridad (I1/I2) en paridad (ADR-0008).

## Justificación

- Mostrar cifras públicas con procedencia es contexto honesto (P7/P9). Convertirlas
  en un ranking o en "amenazas" sería el veredicto que ADR-0000/0003 prohíben.
- Las alianzas declaradas por el dato (no inferidas) respetan P2.

## Consecuencias

**Positivas** — contexto estratégico al seleccionar un país; agrupación por alianza.
**Negativas** — las cifras militares públicas varían entre fuentes y años; se
mitiga con `budget_year` + `source` obligatorios en la práctica y etiqueta `asserted`.
**Neutras** — sin integración en el globo (no hay polígonos de país en v0.1).

## Alternativas consideradas

### A. "Amenazas activas" por país / índice de poder militar
**Razón de rechazo:** atribución de hostilidad / veredicto comparativo, prohibido
(ADR-0003, No-objetivos de ADR-0000). Solo cifras con fuente.

### B. Inferir alianzas o afiliación de bando
**Razón de rechazo:** inventar afiliación viola P2. Solo alianzas declaradas por el dato.

## Alineación con ADR-0000

- **Refuerza P7** (fuentes públicas SIPRI/IISS con año), **P9** (`asserted`),
  **ADR-0003** (sin amenazas/ranking; cifras con procedencia, no veredicto).
- **Sin tensiones con la frontera ética:** contexto público, no juicio.

## Referencias

- SIPRI Military Expenditure Database; IISS, *The Military Balance* — cifras públicas con metodología.
