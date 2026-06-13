"""Fixture de instalaciones de referencia SINTÉTICAS (ADR-0017). No son reales.

Mezcla militar e infraestructura crítica, una sin tipo explícito (-> other) y una
sin categoría explícita (se deriva del tipo)."""

from __future__ import annotations

import json

INSTALLATIONS = [
    {"installation_id": "B1", "name": "Base aérea demo", "latitude": 49.0, "longitude": 34.0,
     "installation_type": "air_base", "category": "military", "country": "TL",
     "source": "(OSM sintético)"},
    {"installation_id": "B2", "name": "Base naval demo", "latitude": 44.6, "longitude": 33.5,
     "installation_type": "naval_base", "country": "TL", "source": "(OSM sintético)"},
    {"installation_id": "I1", "name": "Central nuclear demo", "latitude": 51.4, "longitude": 30.1,
     "installation_type": "nuclear_plant", "country": "TL", "source": "(Wikipedia sintético)"},
    {"installation_id": "I2", "name": "Puerto demo", "latitude": 46.5, "longitude": 30.7,
     "source": "(OSM sintético)"},   # sin tipo -> other -> critical_infrastructure
]


def installations_payload() -> bytes:
    return json.dumps({"installations": INSTALLATIONS}).encode("utf-8")
