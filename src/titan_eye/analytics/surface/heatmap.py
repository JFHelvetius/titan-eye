"""Mapa de calor por estimación de densidad por kernel (KDE) — ADR-0012.

Calcula la **densidad de eventos REPORTADOS** sobre una rejilla lat/lon con un
kernel Gaussiano de **ancho de banda declarado** (`bandwidth_km`) y distancia de
gran círculo. El resultado lleva su bandwidth, su kernel y la semántica explícita.

Honestidad (ADR-0003): el peso es 1 por evento reportado. NO se pondera por
víctimas ni por severidad. El mapa mide cobertura de reportes, no intensidad de
conflicto ni amenaza. La nota de semántica viaja en el resultado para que ningún
consumidor pueda re-etiquetarlo como "intensidad".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from titan_eye.catalog.surface import ConflictEvent
from titan_eye.core.errors import AnalyticsError

KDE_KERNEL_NAME = "gaussian_great_circle_v1"
SEMANTICS_NOTE = (
    "Densidad de eventos REPORTADOS (no intensidad de conflicto ni amenaza). "
    "Peso = 1 por evento; bandwidth declarado (ADR-0003)."
)
EARTH_RADIUS_KM = 6371.0
# Cota dura para no generar rejillas gigantes (P3): nº máx de celdas.
MAX_GRID_CELLS = 20_000


@dataclass(frozen=True)
class HeatmapResult:
    """Rejilla de densidad de reportes con sus parámetros declarados."""

    points: list[list[float]]   # [lon, lat, weight] con weight ∈ (0, 1]
    bandwidth_km: float
    kernel_name: str
    grid_deg: float
    n_events: int
    semantics_note: str = SEMANTICS_NOTE
    # bbox = (lat_min, lat_max, lon_min, lon_max)
    bbox: tuple[float, float, float, float] = field(default=(0, 0, 0, 0))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def compute_heatmap(
    events: list[ConflictEvent],
    *,
    bandwidth_km: float = 50.0,
    grid_deg: float = 0.25,
    margin_deg: float = 1.0,
    threshold: float = 0.05,
) -> HeatmapResult:
    """Densidad de reportes por KDE Gaussiano sobre rejilla lat/lon.

    bandwidth_km: ancho de banda del kernel (declarado en el resultado).
    grid_deg:     resolución de la rejilla en grados.
    threshold:    weight mínimo (normalizado) para emitir una celda."""
    if bandwidth_km <= 0 or grid_deg <= 0:
        raise AnalyticsError("bandwidth_km y grid_deg deben ser > 0.")
    if not events:
        return HeatmapResult(points=[], bandwidth_km=bandwidth_km,
                             kernel_name=KDE_KERNEL_NAME, grid_deg=grid_deg, n_events=0)

    lats = [e.latitude for e in events]
    lons = [e.longitude for e in events]
    lat_min, lat_max = min(lats) - margin_deg, max(lats) + margin_deg
    lon_min, lon_max = min(lons) - margin_deg, max(lons) + margin_deg

    n_lat = int((lat_max - lat_min) / grid_deg) + 1
    n_lon = int((lon_max - lon_min) / grid_deg) + 1
    if n_lat * n_lon > MAX_GRID_CELLS:
        raise AnalyticsError(
            f"Rejilla demasiado grande ({n_lat * n_lon} celdas > {MAX_GRID_CELLS}); "
            "aumenta grid_deg o acota la región."
        )

    raw: list[tuple[float, float, float]] = []
    max_density = 0.0
    for i in range(n_lat):
        glat = lat_min + i * grid_deg
        for j in range(n_lon):
            glon = lon_min + j * grid_deg
            density = 0.0
            for e in events:
                d = _haversine_km(glat, glon, e.latitude, e.longitude)
                u = d / bandwidth_km
                density += math.exp(-0.5 * u * u)   # peso 1 por evento (reporte)
            max_density = max(max_density, density)
            raw.append((glon, glat, density))

    points: list[list[float]] = []
    if max_density > 0:
        for glon, glat, density in raw:
            w = density / max_density
            if w >= threshold:
                points.append([round(glon, 4), round(glat, 4), round(w, 4)])

    return HeatmapResult(
        points=points,
        bandwidth_km=bandwidth_km,
        kernel_name=KDE_KERNEL_NAME,
        grid_deg=grid_deg,
        n_events=len(events),
        bbox=(round(lat_min, 4), round(lat_max, 4), round(lon_min, 4), round(lon_max, 4)),
    )
