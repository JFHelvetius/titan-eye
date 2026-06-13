# ADR-0015: Dominio marítimo — buques y flotas (AIS) v0.1

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P2, P7, P9), ADR-0001, ADR-0002, ADR-0003, ADR-0008, ADR-0009

---

## Contexto

Quinto dominio. Las flotas (portaaviones, destructores, fragatas, submarinos,
buques anfibios, patrulleros) son una capa de actividad militar observable que se
suele olvidar. Una fracción es pública vía **AIS** (Automatic Identification
System): los buques que transmiten transpondedor aparecen en redes públicas
(AISHub, AISStream y similares), igual que las aeronaves vía ADS-B. Este ADR
incorpora el dominio marítimo reutilizando exactamente el patrón del dominio aéreo
(ADR-0009): es `observed`, de cadencia alta, y con un régimen de incertidumbre
fuerte y declarado.

## Decisión

1. **`Domain.MARITIME`** añadido al enum de dominios (ADR-0001), con su nota de
   incertidumbre. Adición puramente aditiva: no altera los cuatro dominios previos.

2. **`VesselPosition` (`observed`)** Normalized: `mmsi` (identidad AIS), `name`,
   `vessel_type` (clase declarada), posición, rumbo (`course`), velocidad
   (`speed_knots`), estado de navegación, antigüedad del último mensaje. FK por
   hash al Raw (ADR-0005), etiqueta `observed` sellada (P9).

3. **Clases de buque** (`VesselType`) descriptivas, NO acusatorias (ADR-0003):
   `carrier`, `destroyer`, `frigate`, `submarine`, `amphibious`, `patrol`,
   `auxiliary`, `other`. Provienen del dato público (campo del dataset o tipo AIS).

4. **Honestidad reforzada (P2) — el caso más delicado de "observed":**
   - El AIS es **autodeclarado** y trivialmente falsificable; los buques de guerra
     **apagan o falsean el AIS con frecuencia**. Por tanto la *ausencia* de un buque
     en AIS no significa nada, y su *presencia* es una afirmación del propio buque.
   - **Los submarinos sumergidos no transmiten AIS.** Un buque etiquetado
     `submarine` en un dataset es una afirmación de la fuente sobre un objeto que,
     por definición, no se observa por AIS bajo el agua. Se conserva el dato con su
     etiqueta, declarando esta limitación; nunca se presenta como un track de sonar.
   - Estas advertencias viajan en la `note` del dominio y en el render.

5. **Ingestión desde dataset estructurado** (JSON), sellada como `RawArtifact`
   (dominio MARITIME, `observed`), igual que el resto. Un adaptador AIS en vivo
   (requiere clave en la mayoría de proveedores) se difiere a ADR-0016 (secretos),
   para no acoplar el núcleo a una credencial (P3/P7).

6. **Persistencia e integridad en paridad** con los demás dominios:
   `VesselPositionsRepository` (Parquet/DuckDB, ADR-0008) + verificador I1/I2
   (`verify-maritime`). Render en el globo como capa naval togglable; el dominio
   entra también en la proximidad geométrica (ADR-0014) **sin veredictos**.

## Justificación

- AIS↔ADS-B es una analogía casi exacta; reutilizar el patrón del dominio aéreo
  minimiza riesgo y código nuevo.
- Declarar el régimen de spoofing/AIS-off y la limitación de submarinos es la
  aplicación honesta de P2 en el dominio donde el "observed" es más frágil.

## Consecuencias

**Positivas** — quinto dominio operativo; las flotas dejan de ser el punto ciego.
**Negativas** — sin AIS en vivo (clave) en v0.1; el operador aporta el dataset.
Aceptado: mantiene P3/P7 y la testabilidad sin red.
**Neutras** — el enum de dominio crece a cinco; el catálogo/analytics se
particionan igual por dominio.

## Alternativas consideradas

### A. Inferir posición de buques sin AIS desde imágenes satelitales (SAR/ópticas)
**Razón de rechazo (v0.1):** requiere fuentes y modelos pesados; sería `inferred`
con incertidumbre enorme. Posible dominio futuro, declarado como tal, no v0.1.

### B. Etiquetar "amenaza naval" o "grupo de combate hostil"
**Razón de rechazo:** prohibido por ADR-0000/0003. Se muestran clases de buque
descriptivas y proximidad geométrica con error, nunca un veredicto.

## Alineación con ADR-0000

- **Refuerza P2** (régimen de spoofing/AIS-off y limitación de submarinos
  declarados), **P7** (AIS público; clave opcional diferida), **P9** (`observed`
  sellado con la advertencia de autodeclaración).
- **Hace cumplir ADR-0003:** clases de buque descriptivas; sin clasificación de
  amenaza ni de intención.

## Referencias

- IMO. *AIS — Automatic Identification System, SOLAS Cap. V.*
- Orbital Sentinel / Titan Eye, patrón del dominio aéreo (ADR-0009).
