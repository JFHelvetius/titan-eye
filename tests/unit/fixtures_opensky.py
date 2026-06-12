"""Fixture canónica de respuesta OpenSky `/api/states/all`.

Tres aeronaves: dos con posición completa (ADS-B y MLAT) y una sin posición
(lat/lon nulas) para ejercitar la conservación honesta de filas sin geometría.
Datos SINTÉTICOS, no reales.
"""

from __future__ import annotations

import json

# time = 2026-06-11T12:00:00Z
OPENSKY_TIME = 1781179200

OPENSKY_FIXTURE: dict = {
    "time": OPENSKY_TIME,
    "states": [
        # icao24, callsign, country, time_pos, last_contact, lon, lat, baro_alt,
        # on_ground, velocity, true_track, vrate, sensors, geo_alt, squawk, spi, pos_source
        ["abc123", "DEMO01  ", "Testland", OPENSKY_TIME - 4, OPENSKY_TIME - 1,
         33.0, 49.5, 10363.2, False, 221.3, 95.0, 0.0, None, 10500.0, "7421", False, 0],
        ["def456", "DEMO02  ", "Testland", OPENSKY_TIME - 40, OPENSKY_TIME - 2,
         36.2, 50.1, 8839.2, False, 200.5, 270.0, -1.5, None, 8900.0, None, False, 2],
        # Sin posición (lat/lon nulas): se conserva como AircraftState sin geometría.
        ["ghi789", None, "Testland", None, OPENSKY_TIME - 3,
         None, None, None, True, None, None, None, None, None, None, False, 0],
    ],
}


def opensky_payload() -> bytes:
    return json.dumps(OPENSKY_FIXTURE).encode("utf-8")
