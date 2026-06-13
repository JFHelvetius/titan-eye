"""Fixture de dataset AIS SINTÉTICO (ADR-0015). No son buques reales.

Cuatro buques de clases distintas, uno sin clase explícita (-> other) y uno con
mensaje antiguo, para ejercitar el normalizador y la honestidad sobre antigüedad."""

from __future__ import annotations

import json

# time = 2026-06-12T00:00:00Z
AIS_TIME = 1781568000

AIS_FIXTURE = {
    "time": AIS_TIME,
    "vessels": [
        {"mmsi": "273000001", "name": "DEMO CARRIER ", "vessel_type": "carrier",
         "flag": "TL", "latitude": 44.2, "longitude": 31.5, "course": 95.0,
         "speed": 18.0, "nav_status": "under way", "last_contact": AIS_TIME - 30},
        {"mmsi": "273000002", "name": "DEMO DESTROYER", "vessel_type": "destroyer",
         "latitude": 44.0, "longitude": 32.1, "course": 100.0, "speed": 22.0,
         "last_contact": AIS_TIME - 600},
        {"mmsi": "273000003", "name": "DEMO SUB", "vessel_type": "submarine",
         "latitude": 43.8, "longitude": 30.9, "speed": 0.0, "last_contact": AIS_TIME - 60},
        # Sin vessel_type -> debe caer a "other".
        {"mmsi": "273000004", "name": "DEMO UNKNOWN",
         "latitude": 43.5, "longitude": 31.0, "last_contact": AIS_TIME - 10},
    ],
}


def ais_payload() -> bytes:
    return json.dumps(AIS_FIXTURE).encode("utf-8")
