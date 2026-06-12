"""Marcos de referencia para el dominio orbital (ADR-0010).

Primitivas geométricas para convertir la salida nativa de SGP4 (TEME) a
coordenadas geodésicas para groundtrack. Reutiliza las fórmulas validadas en
Orbital Sentinel (`propagation/frames.py`).

Modelo GMST: IAU 1982 simplificado, UT1 ≈ UTC. El error angular (|DUT1| ≤ 0.9 s
→ ~13.5 arcsec) es muy inferior al régimen SGP4 dominante (~km). La Tierra
esférica para la geodésica introduce error sub-km vs WGS84, también por debajo
del régimen SGP4 (P2: se declara, no se esconde).
"""

from __future__ import annotations

import math
from datetime import datetime

from sgp4.api import jday

GMST_MODEL_NAME = "iau_1982_ut1_equals_utc_v1"
GEODETIC_MODEL_NAME = "spherical_earth_r6371_v1"
EARTH_RADIUS_KM = 6371.0


def gmst_iau_1982(when: datetime) -> float:
    """GMST en radianes para un datetime UTC tz-aware (IAU 1982 simplificado)."""
    if when.tzinfo is None:
        raise ValueError("when debe ser timezone-aware (UTC esperado).")
    jd_int, jd_frac = jday(
        when.year, when.month, when.day,
        when.hour, when.minute, when.second + when.microsecond * 1e-6,
    )
    jd = jd_int + jd_frac
    t = (jd - 2451545.0) / 36525.0
    gmst_deg = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * t * t
        - t * t * t / 38710000.0
    )
    return math.radians(gmst_deg % 360.0)


def teme_to_ecef(
    x_km: float, y_km: float, z_km: float, when: datetime
) -> tuple[float, float, float]:
    """Rotación TEME → ECEF usando GMST. Sin polar motion."""
    theta = gmst_iau_1982(when)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    return (x_km * cos_t + y_km * sin_t, -x_km * sin_t + y_km * cos_t, z_km)


def ecef_to_geodetic_spherical(x_km: float, y_km: float, z_km: float) -> tuple[float, float, float]:
    """ECEF → (lat_deg, lon_deg, alt_km) sobre Tierra esférica.

    Error sub-km vs WGS84 (ADR-0010), por debajo del régimen SGP4. Devuelve
    longitud en [-180, 180]."""
    hyp = math.hypot(x_km, y_km)
    lat = math.degrees(math.atan2(z_km, hyp))
    lon = math.degrees(math.atan2(y_km, x_km))
    r = math.sqrt(x_km * x_km + y_km * y_km + z_km * z_km)
    alt = r - EARTH_RADIUS_KM
    # Normaliza longitud a [-180, 180]
    lon = ((lon + 180.0) % 360.0) - 180.0
    return lat, lon, alt
