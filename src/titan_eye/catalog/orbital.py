"""Modelo Normalized del dominio orbital: OrbitalElement (ADR-0010).

Capa Normalized (ADR-0001/0006): inmutable, versionada, con FK por hash al Raw
(`content_hash_source`) y al TLE individual (`tle_content_hash`). Conserva las
DOS líneas TLE originales para que la propagación SGP4 sea bit-exacta con la
librería (`twoline2rv`), sin acoplar precisión a la fidelidad del parser.

Incertidumbre como dato (P2): el error característico del régimen TLE+SGP4 se
expone como constantes declaradas; la antigüedad del TLE respecto al instante de
evaluación es parte de la honestidad del output.
"""

from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from titan_eye.core.epistemics import EpistemicLabel

ORBITAL_ELEMENT_SCHEMA_VERSION = "0.1.0"

# Régimen de incertidumbre declarado del dominio orbital (ADR-0003/0010).
SGP4_BASELINE_KM = 2.0
SGP4_GROWTH_KM_PER_DAY = 2.0
# Constante gravitacional terrestre (km^3/s^2), para derivar semieje/altitud.
GM_EARTH = 398600.4418
EARTH_RADIUS_KM = 6371.0


class OrbitalElement(BaseModel):
    """Elemento orbital normalizado a partir de un TLE individual."""

    model_config = ConfigDict(frozen=True)

    norad_cat_id: int
    object_name: str | None = None
    intl_designator: str | None = None

    # Líneas TLE originales (fuente de verdad para SGP4)
    line1: str
    line2: str

    # Elementos keplerianos parseados
    epoch: datetime
    inclination_deg: float
    raan_deg: float
    eccentricity: float
    arg_perigee_deg: float
    mean_anomaly_deg: float
    mean_motion_rev_per_day: float

    # Procedencia y versionado (ADR-0005/0006)
    content_hash_source: str
    tle_content_hash: str
    epistemic_label: EpistemicLabel = EpistemicLabel.OBSERVED
    schema_version: str = ORBITAL_ELEMENT_SCHEMA_VERSION

    @property
    def period_min(self) -> float:
        """Período orbital en minutos desde el movimiento medio."""
        if self.mean_motion_rev_per_day <= 0:
            return 0.0
        return 1440.0 / self.mean_motion_rev_per_day

    @property
    def semi_major_axis_km(self) -> float:
        """Semieje mayor desde el movimiento medio: a = (GM/n²)^(1/3)."""
        n_rad_s = self.mean_motion_rev_per_day * 2.0 * math.pi / 86400.0
        if n_rad_s <= 0:
            return 0.0
        return (GM_EARTH / (n_rad_s * n_rad_s)) ** (1.0 / 3.0)

    @property
    def mean_altitude_km(self) -> float:
        """Altitud media aproximada (semieje - radio terrestre)."""
        return self.semi_major_axis_km - EARTH_RADIUS_KM
