"""Modelos del dominio suborbital (ADR-0011).

Dos modelos con DOS etiquetas epistémicas distintas (P9), que nunca se colapsan:

- `BallisticReport` (`asserted`): el reporte público estructurado. Es la afirmación
  de un tercero (NOTAM, aviso, comunicado, prensa) sobre un lanzamiento, con sus
  tolerancias declaradas y su procedencia.
- `BallisticTrajectory` (`inferred`): la trayectoria que Titan Eye reconstruye a
  partir del reporte, con un modelo físico declarado y su banda de incertidumbre.

La trayectoria referencia al reporte por hash (`content_hash_source`, ADR-0005).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from titan_eye.core.epistemics import EpistemicLabel

BALLISTIC_REPORT_SCHEMA_VERSION = "0.1.0"
BALLISTIC_TRAJECTORY_SCHEMA_VERSION = "0.1.0"


class BallisticReport(BaseModel):
    """Reporte público de un lanzamiento balístico (`asserted`).

    Geometría declarada por el reporte, no medida por Titan Eye. Las tolerancias
    (`*_sigma_km`) son la incertidumbre declarada de la propia fuente."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    launch_lat: float
    launch_lon: float
    impact_lat: float
    impact_lon: float
    apogee_km: float

    # Incertidumbre declarada por la fuente (P2)
    apogee_sigma_km: float = 0.0
    geoloc_sigma_km: float = 0.0

    # Procedencia del reporte
    event_time: datetime | None = None
    source: str = ""
    source_url: str = ""

    # FK por hash al RawArtifact del reporte (ADR-0005). Vacío si aún no sellado.
    content_hash_source: str = ""
    epistemic_label: EpistemicLabel = EpistemicLabel.ASSERTED
    schema_version: str = BALLISTIC_REPORT_SCHEMA_VERSION


class BallisticTrajectory(BaseModel):
    """Trayectoria reconstruida por Titan Eye (`inferred`).

    NO es un track de sensor. Es el resultado de aplicar el modelo físico
    declarado (`model_name`) al `BallisticReport`. Lleva su banda de
    incertidumbre (`band_km`) y la dispersión de impacto, ambas declaradas."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    # Puntos de la trayectoria: [lon, lat, alt_km] (orden listo para el globo)
    arc: list[list[float]]
    launch: list[float]   # [lon, lat]
    impact: list[float]   # [lon, lat]

    # Elementos derivados
    apogee_km: float
    range_km: float
    semi_major_axis_km: float
    eccentricity: float

    # Incertidumbre declarada (P2, ADR-0003)
    band_km: float
    impact_dispersion_km: float
    model_name: str
    model_uncertainty_km: float

    # Procedencia y versionado
    content_hash_source: str   # FK al BallisticReport (hash de su Raw)
    epistemic_label: EpistemicLabel = EpistemicLabel.INFERRED
    schema_version: str = BALLISTIC_TRAJECTORY_SCHEMA_VERSION
