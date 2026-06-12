"""Propagador SGP4 on-demand para el dominio orbital (ADR-0010).

Envuelve la librería `sgp4` (Vallado/Rhodes). Construye el `Satrec` con
`twoline2rv(line1, line2)` desde las líneas originales del OrbitalElement
—nunca desde campos parseados— para coherencia bit-exacta con la librería.

Devuelve posiciones geodésicas (lat, lon, alt_km) para groundtrack, junto con el
código de error SGP4 sin filtrar (P2: no se esconde un fallo de propagación).
No persiste (ADR-0006): el volumen de efemérides sería enorme.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sgp4.api import Satrec, jday

from titan_eye.analytics.propagation.frames import (
    ecef_to_geodetic_spherical,
    teme_to_ecef,
)
from titan_eye.catalog.orbital import OrbitalElement
from titan_eye.core.errors import PropagationError

SGP4_PROPAGATOR_VERSION = "0.1.0"


@dataclass(frozen=True)
class GeoPoint:
    """Posición geodésica propagada en un instante, con calidad declarada."""

    time: datetime
    latitude: float
    longitude: float
    altitude_km: float
    minutes_from_epoch: float
    sgp4_error_code: int


def _satrec(element: OrbitalElement) -> Satrec:
    # Defensa en profundidad: el hash de las líneas debe coincidir con el sellado.
    actual = hashlib.sha256((element.line1 + "\n" + element.line2).encode("ascii")).hexdigest()
    if actual != element.tle_content_hash:
        raise PropagationError(
            f"tle_content_hash no coincide para NORAD {element.norad_cat_id}: "
            f"esperado {element.tle_content_hash[:12]}…, actual {actual[:12]}…"
        )
    try:
        sat = Satrec.twoline2rv(element.line1, element.line2)
    except Exception as exc:
        raise PropagationError(
            f"twoline2rv falló para NORAD {element.norad_cat_id}: {exc}"
        ) from exc
    if sat.error != 0:
        raise PropagationError(
            f"sgp4init devolvió error {sat.error} para NORAD {element.norad_cat_id}"
        )
    return sat


def propagate_geodetic(element: OrbitalElement, times: Sequence[datetime]) -> list[GeoPoint]:
    """Propaga `element` a `times` (UTC tz-aware) -> posiciones geodésicas."""
    if not times:
        return []
    sat = _satrec(element)
    epoch = element.epoch
    out: list[GeoPoint] = []
    for t in times:
        if t.tzinfo is None:
            raise PropagationError("Todos los instantes deben ser timezone-aware (UTC).")
        t_utc = t.astimezone(UTC)
        jd, fr = jday(
            t_utc.year, t_utc.month, t_utc.day,
            t_utc.hour, t_utc.minute, t_utc.second + t_utc.microsecond * 1e-6,
        )
        err, r, _v = sat.sgp4(jd, fr)
        ex, ey, ez = teme_to_ecef(r[0], r[1], r[2], t_utc)
        lat, lon, alt = ecef_to_geodetic_spherical(ex, ey, ez)
        out.append(GeoPoint(
            time=t_utc, latitude=lat, longitude=lon, altitude_km=alt,
            minutes_from_epoch=(t_utc - epoch).total_seconds() / 60.0,
            sgp4_error_code=int(err),
        ))
    return out


def groundtrack(
    element: OrbitalElement, *, start: datetime, span_min: float, step_min: float
) -> list[GeoPoint]:
    """Groundtrack desde `start` durante `span_min`, muestreado cada `step_min`."""
    if step_min <= 0 or span_min <= 0:
        raise PropagationError("span_min y step_min deben ser > 0.")
    from datetime import timedelta

    n = int(span_min / step_min) + 1
    times = [start + timedelta(minutes=step_min * i) for i in range(n)]
    return propagate_geodetic(element, times)
