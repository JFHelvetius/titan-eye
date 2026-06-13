"""Dominios de observación de Titan Eye.

Titan Eye integra cuatro dominios físicos distintos, cada uno con su propia
fuente pública, su propio modelo de propagación y su propio régimen de
incertidumbre (ADR-0002, ADR-0003). El dominio es un eje de primer nivel del
catálogo: una detección SIEMPRE pertenece a exactamente un dominio.

La separación por dominio no es cosmética: el error típico, el modelo
matemático y la falsabilidad de cada dominio son radicalmente distintos, y
mezclarlos sin declararlo violaría P2 (honestidad sobre incertidumbre).
"""

from __future__ import annotations

from enum import Enum


class Domain(str, Enum):
    """Los cuatro dominios de observación.

    - ORBITAL:    objetos en órbita terrestre (satélites militares/dual-use).
                  Fuente: TLEs públicos. Propagación: SGP4. Error ~1–3 km/época.
    - SUBORBITAL: trayectorias balísticas reconstruidas a partir de reportes
                  públicos (apogeo/alcance anunciados, NOTAMs, avisos de
                  lanzamiento). NO son tracks de sensor: son RECONSTRUCCIONES.
                  Error grande y declarado.
    - AERIAL:     aeronaves en vuelo con transpondedor público (ADS-B).
                  Fuente: OpenSky Network. Sujeto a spoofing y cobertura parcial.
    - SURFACE:    eventos de conflicto y movimientos reportados públicamente
                  (datasets abiertos tipo ACLED, OSINT geolocalizado). Son
                  AFIRMACIONES de terceros, no hechos verificados por Titan Eye.
    """

    ORBITAL = "orbital"
    SUBORBITAL = "suborbital"
    AERIAL = "aerial"
    SURFACE = "surface"
    MARITIME = "maritime"
    # REFERENCE no es un dominio de ACTIVIDAD observable: es un tag para geografía
    # estática pública (bases, infraestructura — ADR-0017). Se incluye aquí solo
    # para etiquetar su RawArtifact; no participa de la analítica de actividad.
    REFERENCE = "reference"
    # OSINT tampoco es un dominio físico: es un tag para información (noticias/RRSS
    # geolocalizadas, ADR-0020). Afirmaciones de fuentes, no observación física.
    OSINT = "osint"


# Régimen de incertidumbre cualitativo por dominio. Es un recordatorio de
# diseño, no un número operativo: cada modelo declara su error cuantitativo
# en su propia capa Derived.
DOMAIN_UNCERTAINTY_NOTE: dict[Domain, str] = {
    Domain.ORBITAL: (
        "SGP4 sobre TLE: ~1–3 km en época, crecimiento ~1–3 km/día. "
        "El TLE puede tener horas/días de antigüedad."
    ),
    Domain.SUBORBITAL: (
        "Reconstrucción balística desde reportes públicos. NO es track de "
        "sensor. Incertidumbre dominada por la calidad del reporte de origen."
    ),
    Domain.AERIAL: (
        "ADS-B público: posición declarada por la propia aeronave. Sujeto a "
        "spoofing, apagado de transpondedor y cobertura parcial de receptores."
    ),
    Domain.SURFACE: (
        "Evento reportado por terceros. Es una afirmación con procedencia, no "
        "un hecho verificado. La geolocalización puede ser aproximada."
    ),
    Domain.MARITIME: (
        "AIS autodeclarado por el buque. Trivialmente falsificable; los buques de "
        "guerra apagan o falsean el AIS con frecuencia. Los submarinos sumergidos "
        "no transmiten. Ausencia ≠ inexistencia; presencia = afirmación del buque."
    ),
    Domain.REFERENCE: (
        "Geografía de referencia pública y estática (bases, infraestructura). "
        "Ubicación afirmada por fuentes abiertas; puede estar desactualizada o ser "
        "aproximada. No es actividad observable ni se usa para cómputo operacional."
    ),
    Domain.OSINT: (
        "Noticias/RRSS geolocalizadas: afirmación de una fuente, no verdad "
        "verificada por Titan Eye. El tier de fuente describe el TIPO de fuente, no "
        "su veracidad. La geolocalización de noticias/RRSS es ruidosa y manipulable."
    ),
}
