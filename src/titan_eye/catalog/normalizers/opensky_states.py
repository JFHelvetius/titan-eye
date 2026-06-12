"""Normalizador puro: RawArtifact de OpenSky -> list[AircraftState].

Función determinista, sin red, sin estado. Mapea el vector de estado de OpenSky
(`/api/states/all`) a modelos Normalized, propagando la procedencia por hash
(`content_hash_source`) y la etiqueta epistémica (`observed`).

Decisión de honestidad (P2): las filas SIN posición (lat/lon nulas) se
**conservan** como AircraftState con `has_position=False`, no se inventan
coordenadas. El consumidor decide si filtrarlas; el normalizador no miente.

Formato del vector de estado de OpenSky (índices):
  0 icao24 · 1 callsign · 2 origin_country · 3 time_position · 4 last_contact
  5 longitude · 6 latitude · 7 baro_altitude · 8 on_ground · 9 velocity
  10 true_track · 11 vertical_rate · 12 sensors · 13 geo_altitude · 14 squawk
  15 spi · 16 position_source
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from titan_eye.catalog.aircraft import POSITION_SOURCE, AircraftState
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.core.timebase import from_unix
from titan_eye.ingestion.artifact import RawArtifact

NORMALIZER_VERSION = "0.1.0"


def normalize_states(artifact: RawArtifact) -> list[AircraftState]:
    """Convierte el payload de OpenSky en una lista de AircraftState."""
    try:
        doc: Any = json.loads(artifact.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "Payload de OpenSky no es JSON UTF-8 válido",
            source_hash=artifact.content_hash,
        ) from exc

    if not isinstance(doc, dict) or "states" not in doc:
        raise NormalizationError(
            "Respuesta de OpenSky sin clave 'states'",
            source_hash=artifact.content_hash,
        )

    snapshot_time = _snapshot_time(doc, artifact)
    states = doc.get("states") or []
    out: list[AircraftState] = []
    for i, row in enumerate(states):
        out.append(_row_to_state(row, i, artifact, snapshot_time))
    return out


def _snapshot_time(doc: dict[str, Any], artifact: RawArtifact) -> datetime:
    t = doc.get("time")
    if isinstance(t, (int, float)):
        return from_unix(float(t))
    return artifact.fetched_at.astimezone(UTC)


def _row_to_state(
    row: list[Any], idx: int, artifact: RawArtifact, snapshot_time: datetime
) -> AircraftState:
    if not isinstance(row, list) or len(row) < 17:
        length = len(row) if isinstance(row, list) else "n/a"
        raise NormalizationError(
            f"Vector de estado OpenSky malformado en índice {idx}: longitud {length}",
            source_hash=artifact.content_hash,
            line=idx,
        )

    last_contact = from_unix(float(row[4]))
    time_position = from_unix(float(row[3])) if row[3] is not None else None
    age = None
    if row[3] is not None:
        age = (snapshot_time - from_unix(float(row[3]))).total_seconds()

    return AircraftState(
        icao24=str(row[0]).strip(),
        callsign=(str(row[1]).strip() or None) if row[1] else None,
        origin_country=row[2] or None,
        longitude=_f(row[5]),
        latitude=_f(row[6]),
        baro_altitude_m=_f(row[7]),
        geo_altitude_m=_f(row[13]),
        on_ground=bool(row[8]),
        velocity_ms=_f(row[9]),
        true_track_deg=_f(row[10]),
        vertical_rate_ms=_f(row[11]),
        time_position=time_position,
        last_contact=last_contact,
        last_contact_age_s=age,
        position_source=POSITION_SOURCE.get(int(row[16]) if row[16] is not None else 0, "ADS-B"),
        squawk=row[14] or None,
        spi=bool(row[15]),
        content_hash_source=artifact.content_hash,
        snapshot_time=snapshot_time,
        epistemic_label=EpistemicLabel.OBSERVED,
    )


def _f(v: Any) -> float | None:
    return None if v is None else float(v)
