# ADR-0004: Visualización geoespacial con Cesium embebido

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye
**Supersede a:** ninguno
**Relacionado con:** ADR-0000 (P2, P3, P8, P9), ADR-0003

---

## Contexto

Titan Eye necesita un globo 3D capaz de representar simultáneamente los cuatro dominios sobre la Tierra: objetos en órbita, trayectorias balísticas suborbitales, aeronaves en vuelo y eventos de superficie. Debe hacerlo sin coste recurrente (P3), sin depender de servicios obligatorios (P8) y **representando la incertidumbre y la etiqueta epistémica** de cada dato (P2, P9, ADR-0003).

El proyecto hermano Orbital Sentinel resolvió la visualización 3D con **CesiumJS** embebido y validó la arquitectura concreta de integración (iframe servido desde GitHub Pages + puente `postMessage`) tras descubrir que el `srcdoc` de los componentes de Streamlit bloquea Workers cross-origin. Titan Eye **reutiliza esa arquitectura de integración** y traduce el sistema de capas y entidades al contexto multidominio.

## Decisión

- **Motor 3D: CesiumJS** (Apache-2.0). Es el estado del arte libre para Earth 3D web; produce calidad no replicable con Python puro a escala de miles de objetos.
- **Proveedores de imagery públicos sin token** como baseline (Esri World Imagery, NASA Blue Marble, Esri Topo/Ocean, OpenStreetMap, National Geographic). Cesium Ion / Bing solo como opt-in. Esto satisface P3/P8 sin compromiso.
- **Arquitectura de embebido heredada de Orbital Sentinel:** el HTML real del globo vive en `docs/cesium/index.html` (servible por GitHub Pages); un wrapper Streamlit (`app/cesium_globe.py`) lo carga en un `<iframe>` con origin real y le pasa los datos por `window.postMessage` (evita el bloqueo de Workers del `srcdoc` y los límites de longitud de URL).
- **Sistema de capas multidominio** (panel HUD dentro del iframe, sin re-render del wrapper para preservar cámara/zoom):
  - Capas de base del globo: etiquetas (fronteras/ciudades), atmósfera, iluminación día/noche, terminador solar.
  - Capas de dominio togglables: **satélites** (orbital), **aeronaves** (aéreo), **trayectorias balísticas** (suborbital), **eventos de conflicto** (superficie), **mapa de calor** de densidad de eventos reportados, **anillos de alcance/horizonte** (footprint geométrico).
- **Representación honesta por etiqueta epistémica (P9, obligatorio):**
  - `observed` (posición ADS-B, satélite catalogado): punto nítido con su error nominal.
  - `inferred` (trayectoria balística reconstruida): **banda/tubo de incertidumbre**, nunca línea fina. Opacidad y grosor proporcionales al error declarado.
  - `asserted` (evento de conflicto reportado): marcador con halo cuyo radio refleja la **resolución de geolocalización** declarada por la fuente (exacta/ciudad/región). Nunca un punto nítido sobre una geolocalización aproximada.
- **El mapa de calor mide reportes, no amenaza** (ADR-0003). Su leyenda lo dice explícitamente.
- **Time-slider** con `SampledPositionProperty` de Cesium para animar trayectorias y posiciones en una ventana temporal (reloj del viewer inicializado desde el payload).

## Justificación

- **Reutilización validada:** la arquitectura iframe+postMessage ya está depurada en Orbital Sentinel; reescribirla sería desperdiciar conocimiento ganado.
- **P2/P9 por diseño:** la etiqueta epistémica gobierna el render (ADR-0003). La prohibición de "línea fina como trayectoria" se traslada al dominio suborbital, donde es aún más crítica.
- **P3/P8:** proveedores sin token como default; Ion solo opt-in para el escaparate web.

## Consecuencias

**Positivas** — calidad visual de referencia; honestidad gráfica estructural; funciona con tiles abiertas.
**Negativas** — JS embebido y puente Streamlit↔Cesium que mantener; deuda de incertidumbre inicial igual que en Orbital Sentinel (el MVP puede empezar con marcadores simples y endurecer las bandas/tubos en iteraciones siguientes, declarándolo como deuda explícita).
**Neutras** — backend de viz aislado tras el plano `viz/` (ADR-0001); swap futuro posible.

## Alternativas consideradas

### A. Solo Plotly/Deck.gl 2D
**Razón de rechazo:** insuficiente para órbitas 3D y trayectorias balísticas suborbitales simultáneas.

### B. Reescribir el bridge desde cero
**Razón de rechazo:** Orbital Sentinel ya pagó el coste de depurar el bloqueo de Workers del `srcdoc`. Reutilizar es la decisión racional.

### C. Cesium Ion / Bing como default
**Razón de rechazo:** viola P8 (servicio obligatorio + token). Aceptable solo como opt-in para el deploy público.

## Alineación con ADR-0000

- **Implementa P2 y P9 visualmente** (la etiqueta epistémica gobierna el dibujo; bandas de error obligatorias para `inferred`).
- **Refuerza P3, P8** (tiles abiertas sin token).
- **Hace cumplir ADR-0003:** sin scores de amenaza en el globo; el heatmap mide reportes.
- **Tensión menor:** el MVP puede heredar deuda de incertidumbre (marcadores antes que bandas). Mitigación: declararla como issue y cerrarla en iteración v0.2/v0.3, igual que hizo Orbital Sentinel.

## Referencias

- CesiumJS. *Documentation and asset licensing (Apache-2.0).*
- Orbital Sentinel, ADR-0008 enmienda 1 (bridge Streamlit↔Cesium vía iframe+postMessage).
- Munzner, T. (2014). *Visualization Analysis and Design.*
