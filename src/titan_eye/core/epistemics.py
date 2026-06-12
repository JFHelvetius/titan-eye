"""Etiqueta epistémica (P9 de ADR-0000).

Toda detección persistida declara si es una medición directa, una afirmación
de un tercero, o una reconstrucción de Titan Eye. El sistema nunca presenta una
como otra; la etiqueta viaja sellada en la cadena de procedencia (ADR-0005) y
gobierna la representación visual (ADR-0004).
"""

from __future__ import annotations

from enum import Enum


class EpistemicLabel(str, Enum):
    """Naturaleza epistémica de un dato.

    - OBSERVED: medición directa de una fuente pública (TLE catalogado, mensaje
      ADS-B emitido por la propia aeronave). Es lo más cercano a un "hecho", con
      su error de medición.
    - ASSERTED: afirmación de un tercero con procedencia (evento de conflicto
      reportado por ACLED). Es una afirmación, no un hecho verificado por Titan Eye.
    - INFERRED: reconstruido por Titan Eye con un modelo declarado (trayectoria
      balística estimada desde parámetros reportados). Lleva su banda de error.
    """

    OBSERVED = "observed"
    ASSERTED = "asserted"
    INFERRED = "inferred"
