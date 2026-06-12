"""Reconstrucción balística Kepleriana de vacío (ADR-0011).

Modelo físico v0.1: elipse Kepleriana, masa puntual, foco en el centro de la
Tierra, **Tierra esférica sin rotación, sin arrastre**. Dado el punto de
lanzamiento, el de impacto (→ ángulo central Φ por gran círculo) y el apogeo
r_a = R + h_a, la geometría tiene solución cerrada:

    ρ = r_a / R ;  c = cos(Φ/2)
    e = (ρ − 1) / (ρ − c)
    a = r_a / (1 + e)

La trayectoria es simétrica con el apogeo en el punto medio del gran círculo.
Se muestrea r(θ) = a(1−e²)/(1 − e·cos θ) para θ ∈ [−Φ/2, +Φ/2] y se mapea sobre
el gran círculo lanzamiento→impacto (slerp), con altitud = r − R.

Honestidad (P2/ADR-0003): la banda de incertidumbre se declara linealizada desde
las tolerancias del reporte MÁS un suelo de error del modelo (física omitida).
No se fabrica un Monte Carlo que aparente precisión de vacío.
"""

from __future__ import annotations

import math

from titan_eye.catalog.ballistic import (
    BALLISTIC_TRAJECTORY_SCHEMA_VERSION,
    BallisticReport,
    BallisticTrajectory,
)
from titan_eye.core.errors import AnalyticsError

EARTH_RADIUS_KM = 6371.0
BALLISTIC_MODEL_NAME = "keplerian_vacuum_spherical_nonrotating_v1"
BALLISTIC_ENGINE_VERSION = "0.1.0"
# Suelo de error del modelo: representa explícitamente la física omitida
# (rotación terrestre, arrastre, achatamiento). Declarado, no medido (ADR-0011).
MODEL_UNCERTAINTY_KM = 30.0


def _unit(lat_deg: float, lon_deg: float) -> tuple[float, float, float]:
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))


def _to_latlon(x: float, y: float, z: float) -> tuple[float, float]:
    hyp = math.hypot(x, y)
    return math.degrees(math.atan2(z, hyp)), math.degrees(math.atan2(y, x))


def central_angle(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Ángulo central (radianes) entre dos puntos en la esfera (gran círculo)."""
    a = _unit(lat1, lon1)
    b = _unit(lat2, lon2)
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    return math.acos(dot)


def reconstruct(report: BallisticReport, *, n_points: int = 60) -> BallisticTrajectory:
    """Reconstruye la trayectoria balística desde un reporte (asserted → inferred)."""
    R = EARTH_RADIUS_KM
    if report.apogee_km <= 0:
        raise AnalyticsError("El apogeo reportado debe ser > 0.")

    phi = central_angle(report.launch_lat, report.launch_lon,
                        report.impact_lat, report.impact_lon)
    if phi <= 1e-9:
        raise AnalyticsError("Lanzamiento e impacto coinciden; trayectoria degenerada.")

    r_a = R + report.apogee_km
    rho = r_a / R
    c = math.cos(phi / 2.0)
    denom = rho - c
    if denom <= 1e-12:
        raise AnalyticsError("Geometría no física: apogeo demasiado bajo para el alcance.")
    e = (rho - 1.0) / denom
    if not (0.0 <= e < 1.0):
        raise AnalyticsError(
            f"Excentricidad fuera de rango ({e:.4f}); apogeo/alcance inconsistentes."
        )
    a = r_a / (1.0 + e)
    p = a * (1.0 - e * e)  # semi-latus rectum

    # Vectores unitarios de lanzamiento e impacto para slerp sobre el gran círculo
    u0 = _unit(report.launch_lat, report.launch_lon)
    u1 = _unit(report.impact_lat, report.impact_lon)
    sin_phi = math.sin(phi)

    arc: list[list[float]] = []
    for i in range(n_points + 1):
        theta = -phi / 2.0 + phi * (i / n_points)   # de -Φ/2 (lanzamiento) a +Φ/2 (impacto)
        r = p / (1.0 - e * math.cos(theta))
        alt = r - R
        f = (theta + phi / 2.0) / phi               # fracción 0..1 a lo largo del gran círculo
        s0 = math.sin((1.0 - f) * phi) / sin_phi
        s1 = math.sin(f * phi) / sin_phi
        x = s0 * u0[0] + s1 * u1[0]
        y = s0 * u0[1] + s1 * u1[1]
        z = s0 * u0[2] + s1 * u1[2]
        lat, lon = _to_latlon(x, y, z)
        arc.append([round(lon, 4), round(lat, 4), round(max(alt, 0.0), 2)])

    # Banda de incertidumbre declarada (linealizada + suelo de modelo)
    band_km = math.hypot(report.apogee_sigma_km, MODEL_UNCERTAINTY_KM)
    impact_dispersion_km = math.hypot(report.geoloc_sigma_km, MODEL_UNCERTAINTY_KM)

    return BallisticTrajectory(
        event_id=report.event_id,
        arc=arc,
        launch=[round(report.launch_lon, 4), round(report.launch_lat, 4)],
        impact=[round(report.impact_lon, 4), round(report.impact_lat, 4)],
        apogee_km=round(report.apogee_km, 2),
        range_km=round(phi * R, 2),
        semi_major_axis_km=round(a, 3),
        eccentricity=round(e, 6),
        band_km=round(band_km, 2),
        impact_dispersion_km=round(impact_dispersion_km, 2),
        model_name=BALLISTIC_MODEL_NAME,
        model_uncertainty_km=MODEL_UNCERTAINTY_KM,
        content_hash_source=report.content_hash_source,  # ancla de procedencia (ADR-0005)
        schema_version=BALLISTIC_TRAJECTORY_SCHEMA_VERSION,
    )
