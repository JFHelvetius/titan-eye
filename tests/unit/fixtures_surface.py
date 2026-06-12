"""Fixture de eventos de conflicto SINTÉTICOS (ADR-0012). No son eventos reales.

Dos clústeres geográficos para ejercitar el KDE: 4 eventos cerca de (48.0, 37.6)
y 2 cerca de (50.4, 30.5), con resoluciones de geolocalización mixtas."""

from __future__ import annotations

import json

CONFLICT_EVENTS = [
    {"event_id": "E1", "event_date": "2026-06-10", "latitude": 48.00, "longitude": 37.60,
     "geoloc_resolution": "city", "event_type": "Armed clash", "location_name": "Sintética A",
     "reported_fatalities": 3, "source": "(ACLED sintético)"},
    {"event_id": "E2", "event_date": "2026-06-10", "latitude": 48.05, "longitude": 37.65,
     "geo_precision": 1, "event_type": "Shelling", "location_name": "Sintética A2",
     "reported_fatalities": 0, "source": "(ACLED sintético)"},
    {"event_id": "E3", "event_date": "2026-06-09", "latitude": 47.95, "longitude": 37.55,
     "geoloc_resolution": "region", "event_type": "Armed clash", "location_name": "Sintética A3",
     "source": "(ACLED sintético)"},
    {"event_id": "E4", "event_date": "2026-06-09", "latitude": 48.02, "longitude": 37.58,
     "geoloc_resolution": "city", "event_type": "Drone strike", "location_name": "Sintética A4",
     "source": "(GDELT sintético)"},
    {"event_id": "E5", "event_date": "2026-06-08", "latitude": 50.40, "longitude": 30.50,
     "geoloc_resolution": "exact", "event_type": "Explosion", "location_name": "Sintética B",
     "reported_fatalities": 1, "source": "(GDELT sintético)"},
    {"event_id": "E6", "event_date": "2026-06-08", "latitude": 50.42, "longitude": 30.55,
     "geoloc_resolution": "city", "event_type": "Armed clash", "location_name": "Sintética B2",
     "source": "(GDELT sintético)"},
]


def events_payload() -> bytes:
    return json.dumps({"events": CONFLICT_EVENTS}).encode("utf-8")
