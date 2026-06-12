# ADR-0000: Visión a largo plazo de Titan Eye

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** Titan Eye — autor fundador
**Supersede a:** ninguno
**Relacionado con:** todos los ADR posteriores

---

## Naturaleza de este documento

Los ADR habitualmente capturan decisiones técnicas con consecuencias acotadas: qué base de datos, qué motor de propagación, qué formato de serialización. Este ADR captura algo distinto: la brújula.

Antes de elegir cualquier tecnología, este documento fija qué problema resuelve el proyecto, para quién, y bajo qué propiedades irrenunciables. Sin esa brújula, los ADR técnicos posteriores no pueden evaluarse como buenos o malos; solo como coherentes o incoherentes con un marco. Este ADR construye ese marco.

Cualquier ADR posterior debe declarar explícitamente cómo se alinea con éste. Si un ADR técnico entra en tensión con alguna de las propiedades irrenunciables aquí enumeradas, esa tensión debe declararse y justificarse, no ocultarse.

Este documento toma como referencia arquitectónica el proyecto hermano **Orbital Sentinel** (vigilancia satelital pasiva con datos públicos), del que Titan Eye hereda protocolos de construcción, disciplina de procedencia y honestidad sobre incertidumbre. Hereda los protocolos; **no** hereda el dominio: Titan Eye es un proyecto distinto, con dominios, fuentes y régimen de error propios.

## Contexto

Cuando ocurre un evento de relevancia militar —un lanzamiento balístico, el despliegue de una aeronave de reconocimiento, el cambio de órbita de un satélite de observación, una escalada en una zona de conflicto— el discurso público sobre ese evento es **basado en autoridad**. Unos pocos actores con acceso a sensores clasificados emiten afirmaciones; el resto del mundo elige entre creerlas o callar.

Sin embargo, una fracción creciente de la señal observable es **pública**:

1. **Orbital**: catálogos TLE de la US Space Force / CelesTrak describen la posición de miles de objetos, incluidos satélites militares y dual-use.
2. **Aéreo**: la red ADS-B (OpenSky Network y similares) captura transpondedores de aeronaves, incluidas militares que no apagan el suyo.
3. **Suborbital**: NOTAMs, avisos de zona marítima cerrada, reportes de apogeo/alcance y comunicados oficiales permiten **reconstruir** trayectorias balísticas anunciadas.
4. **Superficie**: datasets abiertos de eventos de conflicto (tipo ACLED), reportes OSINT geolocalizados y comunicados permiten cartografiar la actividad reportada.

Existen herramientas excelentes que explotan una de estas fuentes (FlightRadar24, Liveuamap, los catálogos de CelesTrak, los analistas de Bellingcat). Lo que falta es una herramienta **abierta, rigurosa, mantenida y verificable** que:

- integre los cuatro dominios bajo un único modelo de procedencia,
- distinga sistemáticamente **lo observado** de **lo afirmado** de **lo inferido**,
- y permita a cualquier tercero **auditar** una afirmación contra los bytes públicos que la originaron, sin pedir permiso a nadie.

Titan Eye propone ocupar esa categoría.

## Misión

Hacer accesible al público técnico la capacidad de **registrar, propagar y visualizar** eventos orbitales, suborbitales, aéreos y de superficie de relevancia militar, usando **exclusivamente datos públicos**, con **procedencia verificable** y **honestidad sobre incertidumbre**.

Cada palabra de esa frase es deliberada:

- **Registrar, propagar y visualizar** — tres capacidades, en orden de dificultad. **Razonar sobre intención no está en la lista, y nunca lo estará** (ver No-objetivos).
- **Relevancia militar** — describe el *dominio de interés*, no un *caso de uso operacional*. Titan Eye observa lo que es militarmente relevante; no presta servicio a una parte de un conflicto.
- **Exclusivamente datos públicos** — restricción no negociable. Si una capacidad solo es posible con datos clasificados o de pago, no entra en el proyecto.
- **Procedencia verificable** — toda detección se ata por hash a los bytes públicos que la produjeron.
- **Honestidad sobre incertidumbre** — la propiedad de rigor que separa esta herramienta de un mapa bonito que aparenta certeza que no tiene.

## Posición ética y de alcance (parte del contrato, no un disclaimer)

Esta sección es vinculante para todo ADR y todo código posterior. No es un descargo legal: es una restricción de diseño que define qué es y qué no es Titan Eye.

1. **Es un registro de detección y un instrumento de transparencia, no un sistema de targeting.** Titan Eye observa, registra y muestra lo públicamente observable. **No** calcula soluciones de tiro, guiado de intercepción, ni ningún output cuyo propósito sea conferir ventaja operacional a una parte beligerante. Cualquier PR que mueva el proyecto en esa dirección se rechaza por violar ADR-0000.
2. **No clasifica intención ni amenaza.** El sistema no emite "esto es un ataque", "este actor es hostil", ni probabilidades de intención. Produce **geometría con error declarado** y **procedencia**, igual que el proyecto hermano produce geometría orbital sin veredictos. La clasificación de intención es un No-objetivo permanente (ADR-0003).
3. **Distingue observado / afirmado / inferido.** Una posición ADS-B es *declarada por la propia aeronave*. Un evento de conflicto es *afirmado por un tercero*. Una trayectoria balística es *reconstruida por Titan Eye*. El sistema nunca colapsa estas tres categorías en "un hecho".
4. **Audiencia y no-audiencia (abajo) delimitan el público técnico**, no autorizan ni desautorizan a nadie: la licencia Apache-2.0 es neutra. Pero el *diseño* del producto sirve a la transparencia y la verificación, no a la operación de combate.

## Horizonte de mantenimiento como heurística de diseño

Las decisiones arquitectónicas de este proyecto deberán evaluarse asumiendo un horizonte mínimo de 5 años de mantenimiento potencial.

Esto no es un compromiso del autor con un calendario, sino una regla para evaluar trade-offs: una decisión cuyo coste agregado en una ventana de cinco años supera el de una alternativa razonable no debe adoptarse aunque sea atractiva a corto plazo. El horizonte es la lente, no la promesa.

## Visión de estado deseado

Estado del proyecto cuando esté maduro, descrito sin referencias temporales:

- Es una **herramienta de referencia** para periodistas, investigadores y analistas OSINT que necesitan verificar afirmaciones sobre actividad militar observable con datos públicos.
- Mantiene un **registro histórico continuo** de detecciones en los cuatro dominios, consultable, reproducible y citable por hash.
- Su **reconstrucción de trayectorias balísticas** ha sido validada contra eventos públicos documentados, con su error declarado.
- Su **mapa de actividad de conflicto** distingue siempre densidad de *reportes* de densidad de *eventos*, sin confundir cobertura mediática con realidad.
- Sigue **ejecutándose en un portátil moderno** como producto principal. Cualquier desviación exige ADR explícito.

"Maduro" no es una fecha. Es un estado verificable.

## Audiencias

### Audiencia primaria
- Periodistas de investigación y analistas OSINT (estilo Bellingcat, conflict monitors).
- Investigadores en seguridad internacional, estudios de defensa y política espacial.
- ONGs de monitorización de conflictos y derechos humanos.
- Educadores en relaciones internacionales, astrodinámica e ingeniería aeroespacial.
- Hobbyistas técnicos con base científica.

### Audiencia secundaria
- Cualquier proyecto o entidad que construya productos derivados sobre Titan Eye. La licencia permisiva (ADR-0007) habilita este uso.

### No-audiencia
- Usuarios que esperen un producto consumer-grade sin formación técnica.
- Cualquier uso que requiera certeza operacional o garantías formales de precisión: el régimen de datos públicos (TLE, ADS-B, reportes OSINT) no soporta ese requisito como propiedad del propio dato.
- **Operaciones de combate.** No por filtro legal —la licencia es neutra— sino porque el producto no se diseña para conferir ventaja de tiro y declara explícitamente su error: usarlo para eso sería usarlo contra su diseño.

Reconocer la no-audiencia es una declaración de límites técnicos y de propósito de diseño, no un juicio sobre quién está autorizado a ejecutar código abierto.

## Propiedades irrenunciables

Invariantes del sistema. Ningún ADR posterior puede violarlas sin superseder explícitamente a este ADR-0000.

### P1. Reproducibilidad bajo entorno declarado
Cualquier detección, hoy o en el pasado, debe poder reproducirse a partir de cuatro coordenadas declaradas: **código** (commit), **configuración** (hash del config del run), **datos crudos** (`content_hash` de los bytes públicos), y **entorno** (lockfile, SO, arquitectura). La reproducción es bit-exacta dentro del mismo entorno y funcionalmente equivalente entre entornos compatibles. No se garantiza identidad bit a bit entre arquitecturas distintas: declararlo sería deshonesto.

### P2. Honestidad sobre incertidumbre
Cada dominio tiene un error característico y declarado (ADR-0003). Toda visualización, API y reporte debe representar esa incertidumbre, no esconderla. **Una línea fina dibujada como trayectoria balística, o un punto nítido sobre un evento geolocalizado por aproximación, son mentiras.** El error es un dato de primera clase, no una nota al pie.

### P3. Coste de operación cercano a cero
El proyecto debe poder ejecutarse, en su totalidad, en un portátil doméstico moderno sin servicios de pago. Las APIs externas de pago son siempre opcionales y nunca caminos críticos.

### P4. Validación operacional de reproducibilidad
P1 no se sostiene por declaración: se verifica con tests de regresión que reejecutan detecciones pasadas en el entorno declarado y comparan contra outputs canónicos almacenados. Cualquier release publica el estado de esta verificación. Si falla sin causa declarada, el release no sale.

### P5. Licencia permisiva
La licencia es Apache-2.0. Permite uso comercial, derivado y sublicensing sin filtros. La neutralidad de la licencia convive con un *diseño* orientado a transparencia: la licencia no filtra usuarios; el diseño elige qué construir y qué no (sección de alcance).

### P6. Documentación en pie de igualdad con el código
Una funcionalidad sin documentación de usuario no se considera entregada. Una decisión sin ADR no se considera tomada.

### P7. Fuentes públicas y reproducibles como primarias
Cualquier capacidad del sistema debe ser obtenible con fuentes públicas y reproducibles. Datos de pago o cerrados pueden ser **complemento opcional**, nunca **dependencia**. Si un nuevo usuario no puede reproducir un resultado sin firmar contratos ni pagar suscripciones, ese resultado no pertenece al núcleo. **Corolario duro de Titan Eye: ninguna fuente clasificada, filtrada o de inteligencia restringida entra jamás en el proyecto, ni siquiera como opción.**

### P8. Local-first
Toda funcionalidad fundamental debe poder ejecutarse localmente. Los servicios externos amplían capacidades pero no son dependencias obligatorias para la operación básica.

### P9. Separación observado / afirmado / inferido
Toda detección persistida lleva una **etiqueta de epistemología** declarada: `observed` (medición directa de un transpondedor/catálogo público), `asserted` (afirmación de un tercero con procedencia), o `inferred` (reconstruido por Titan Eye con un modelo declarado). El sistema nunca presenta un `asserted` o un `inferred` como si fuera un `observed`. Esta propiedad es la implementación estructural de la posición de alcance.

## No-objetivos explícitos

Lo que este proyecto **nunca** será mientras ADR-0000 esté vigente:

- **No será un sistema de targeting ni de apoyo a la decisión de fuego.** Ver sección de alcance.
- **No clasificará intención ni amenaza.** No emite veredictos del tipo "ataque inminente", "actor hostil", ni scores de intención. ADR-0003.
- **No usará datos clasificados, filtrados ni de pago como fuentes primarias.** P7.
- **No publicará posiciones que no estén ya en fuentes públicas.** No es un canal de descubrimiento independiente; razona sobre lo público.
- **No competirá con sistemas operacionales clasificados** en alcance, precisión ni latencia.
- **No proporcionará outputs aplicables en operaciones sin verificación independiente.** Es una declaración sobre el régimen de precisión de datos públicos.

## Disclaimer operacional

Titan Eye no proporciona garantías operacionales para ningún uso. Los outputs son material analítico y de transparencia, no recomendaciones aplicables sin verificación independiente. Toda detección incluye su procedencia y su incertidumbre declarada precisamente para que el usuario pueda juzgar su fiabilidad. Cualquier uso aplicado es responsabilidad exclusiva del usuario.

## Cumplimiento legal de fuentes

Los proveedores de datos públicos (CelesTrak, OpenSky, ACLED, Space-Track y similares) establecen términos de uso como condición de acceso. El proyecto los respeta porque son la contrapartida contractual del acceso. Algunas fuentes (p. ej. ACLED, OpenSky) imponen condiciones de atribución o de uso no comercial: esas condiciones se documentan por fuente (ADR-0002) y se cumplen. Si un término cambia y limita una capacidad, el proyecto se adapta o documenta la limitación.

## Modelo de sostenibilidad

El proyecto debe sobrevivir sin presupuesto y sin equipo dedicado. Maintainer único inicial; trabajo part-time sin compromiso de cadencia; aceptación de PRs reactiva. Posibles co-maintainers si emerge contribución sostenida. Ningún modelo de monetización es objetivo. Cualquier momento en que sostener el proyecto requiera una promesa incumplible es un momento para reducir alcance, no para acelerar.

## Condiciones de archivo digno

Titan Eye se archivará —con notificación pública, último release estable y `ARCHIVED.md` explicando el estado final— si se cumple alguna de:

1. **Inviabilidad técnica demostrada**: si se demuestra que las fuentes públicas son insuficientes para los casos de uso centrales y no existe alternativa compatible con P3 y P7.
2. **Colapso de fuentes**: si las fuentes públicas centrales desaparecen o pasan a régimen cerrado durante más de doce meses sin alternativa equivalente.
3. **Insostenibilidad de mantenimiento**: doce meses sin capacidad de respuesta a issues críticos ni reemplazo del mantenedor.
4. **Captura por intereses incompatibles**: si el control del proyecto pasa a un actor cuyo uso viole P1–P9 o la posición de alcance.

## Cómo evaluamos salud del proyecto

Sin métricas numéricas dogmáticas atadas a calendario. Cada release publica una evaluación cualitativa sobre cuatro ejes: **cobertura de datos** (qué fracción de cada dominio es accesible y con qué fuentes), **calidad de inferencia** (error de reconstrucción contra eventos públicos conocidos; distribuciones, no promedios), **reproducibilidad operativa** (capacidad de regenerar cualquier detección histórica por hash), y **salud de mantenimiento** (tendencia, no objetivos rígidos).

## Cómo este ADR limita a los siguientes

Todo ADR técnico posterior debe incluir una sección **"Alineación con ADR-0000"** que conteste: ¿qué propiedades P1–P9 afecta? ¿las refuerza, las mantiene neutras o introduce tensión? Si hay tensión, ¿cuál es la mitigación o por qué es aceptable? Una PR con un ADR que la omita no se mergea.

## Alineación con ADR-0000

Este ADR define las propiedades de referencia. No se alinea con nadie; los demás se alinean con él.

## Referencias

- Vallado, D. A. (2013). *Fundamentals of Astrodynamics and Applications*, 4ª ed.
- Hoots, F. R., & Roehrich, R. L. (1980). *Spacetrack Report No. 3*.
- Raleigh, C. et al. (2010). *Introducing ACLED: An Armed Conflict Location and Event Dataset.* J. Peace Research.
- Schäfer, M. et al. (2014). *Bringing up OpenSky: A large-scale ADS-B sensor network for research.*
- Nygard, M. (2011). *Documenting Architecture Decisions.*
- Apache Software Foundation. *Apache License, Version 2.0*.
