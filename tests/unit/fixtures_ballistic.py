"""Fixture de reporte balístico SINTÉTICO (ADR-0011). No es un evento real.

Lanzamiento y zona de impacto separados ~1100 km de gran círculo, apogeo 480 km:
una trayectoria lofted plausible para ejercitar la reconstrucción de vacío."""

from __future__ import annotations

import json

BALLISTIC_REPORT = {
    "event_id": "BAL-TEST-1",
    "launch_lat": 39.0,
    "launch_lon": 127.5,
    "impact_lat": 40.5,
    "impact_lon": 139.0,
    "apogee_km": 480.0,
    "apogee_sigma_km": 25.0,
    "geoloc_sigma_km": 10.0,
    "event_time": "2026-06-10T03:00:00Z",
    "source": "(reporte sintético de prueba)",
    "source_url": "https://example.org/notam/synthetic",
}


def report_payload() -> bytes:
    return json.dumps(BALLISTIC_REPORT).encode("utf-8")
