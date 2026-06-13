"""Datos de DEMOSTRACIÓN para el globo de Titan Eye.

ATENCIÓN (P2, honestidad): estos datos son SINTÉTICOS e ilustrativos. No
provienen de ninguna fuente real ni representan eventos reales. Existen solo
para ejercitar el contrato de render del globo (ADR-0004) antes de que los
pipelines de ingestión (Fase 1+) alimenten datos públicos reales.

Cuando los planos de ingestión estén operativos, esta función se sustituye por
la traducción de modelos Normalized/Derived reales a payload de render.
"""

from __future__ import annotations

import math
from typing import Any


def _ballistic_arc(lon0: float, lat0: float, lon1: float, lat1: float,
                   apogee_km: float, n: int = 40) -> list[list[float]]:
    """Arco parabólico simple (gran círculo + perfil de altura senoidal).

    Es una APROXIMACIÓN ilustrativa para la demo, no el modelo balístico real
    de Fase 3 (que propaga incertidumbre desde los parámetros reportados)."""
    arc = []
    for i in range(n + 1):
        f = i / n
        lon = lon0 + (lon1 - lon0) * f
        lat = lat0 + (lat1 - lat0) * f
        alt = apogee_km * math.sin(math.pi * f)
        arc.append([round(lon, 3), round(lat, 3), round(alt, 1)])
    return arc


def demo_payload() -> dict[str, Any]:
    """Payload multidominio sintético para el globo."""
    return {
        "domains": {
            "orbital": [
                {"id": 25544, "name": "DEMO-RECON-A", "lon": 12.0, "lat": 41.0,
                 "alt_km": 420, "incl": 51.6, "period_min": 92.7, "err_km": 2.3,
                 "owner": "(sintético)", "track": [[12 + k, 41 + 8 * math.sin(k / 6), 420] for k in range(-40, 41, 4)]},
                {"id": 43013, "name": "DEMO-SIGINT-B", "lon": 60.0, "lat": 30.0,
                 "alt_km": 1100, "incl": 63.4, "period_min": 107.2, "err_km": 3.1,
                 "owner": "(sintético)", "track": [[60 + k, 30 + 12 * math.sin(k / 7), 1100] for k in range(-40, 41, 4)]},
            ],
            "aerial": [
                {"id": "DEMO01", "callsign": "DEMO01", "lon": 33.0, "lat": 49.5,
                 "alt_km": 10.4, "heading": 95, "speed_kt": 430, "age_s": 6, "origin": "(sintético)"},
                {"id": "DEMO02", "callsign": "DEMO02", "lon": 36.2, "lat": 50.1,
                 "alt_km": 8.8, "heading": 270, "speed_kt": 390, "age_s": 41, "origin": "(sintético)"},
            ],
            "suborbital": [
                {"id": "BAL-DEMO-1", "name": "DEMO Ballistic 1", "source": "(reporte sintético)",
                 "launch": [127.5, 39.0], "impact": [139.7, 35.7],
                 "arc": _ballistic_arc(127.5, 39.0, 139.7, 35.7, 480),
                 "apogee_km": 480, "range_km": 1100, "band_km": 35, "impact_dispersion_km": 40},
            ],
            "surface": [
                {"id": "EVT-1", "name": "Evento demo (ciudad)", "lon": 37.6, "lat": 48.0,
                 "source": "(ACLED sintético)", "event_type": "Armed clash", "date": "2026-06-10",
                 "events_count": 7, "geoloc_res": "city"},
                {"id": "EVT-2", "name": "Evento demo (región)", "lon": 30.5, "lat": 50.4,
                 "source": "(ACLED sintético)", "event_type": "Shelling", "date": "2026-06-09",
                 "events_count": 3, "geoloc_res": "region"},
            ],
            "maritime": [
                {"id": "273000001", "name": "DEMO-CARRIER", "lon": 31.5, "lat": 44.2,
                 "vessel_type": "carrier", "flag": "(sintético)", "course": 95, "speed_kt": 18,
                 "nav_status": "under way", "age_s": 30},
                {"id": "273000002", "name": "DEMO-DESTROYER", "lon": 32.1, "lat": 44.0,
                 "vessel_type": "destroyer", "flag": "(sintético)", "course": 100, "speed_kt": 22,
                 "nav_status": "under way", "age_s": 45},
                {"id": "273000003", "name": "DEMO-FRIGATE", "lon": 30.9, "lat": 43.8,
                 "vessel_type": "frigate", "flag": "(sintético)", "course": 270, "speed_kt": 14,
                 "nav_status": "under way", "age_s": 120},
            ],
        },
        "heatmap": [
            {"lon": 37.6, "lat": 48.0, "weight": 0.9},
            {"lon": 30.5, "lat": 50.4, "weight": 0.5},
            {"lon": 35.0, "lat": 49.0, "weight": 0.7},
            {"lon": 38.5, "lat": 47.2, "weight": 0.6},
        ],
        "installations": [
            {"id": "INST-1", "name": "Base aérea demo", "lon": 34.0, "lat": 49.0,
             "type": "air_base", "category": "military", "country": "(sintético)",
             "source": "(OSM sintético)"},
            {"id": "INST-2", "name": "Central nuclear demo", "lon": 30.1, "lat": 51.4,
             "type": "nuclear_plant", "category": "critical_infrastructure",
             "country": "(sintético)", "source": "(OSM sintético)"},
        ],
        "layers": {"orbital": True, "aerial": True, "maritime": True, "suborbital": True,
                   "surface": True, "heatmap": False, "range": False, "installations": True},
    }
