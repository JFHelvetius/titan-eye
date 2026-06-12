"""Normalizador puro: RawArtifact (JSON de eventos) -> list[ConflictEvent] (ADR-0012).

Determinista, sin red. El JSON es un dataset estructurado que el operador exporta
de una fuente pública (ACLED, GDELT). Acepta una lista de eventos o un objeto con
clave `events`. Conserva la etiqueta `asserted` y la procedencia por hash.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from titan_eye.catalog.surface import ConflictEvent, GeolocResolution
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact

_REQUIRED = ("event_id", "event_date", "latitude", "longitude")
# Mapea geo_precision tipo-ACLED (1/2/3) a la resolución declarada.
_ACLED_PRECISION = {1: GeolocResolution.EXACT, 2: GeolocResolution.CITY,
                    3: GeolocResolution.REGION}


def normalize_conflict_events(artifact: RawArtifact) -> list[ConflictEvent]:
    """Convierte el JSON de eventos en una lista de ConflictEvent (`asserted`)."""
    try:
        doc: Any = json.loads(artifact.payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "Dataset de eventos no es JSON UTF-8 válido", source_hash=artifact.content_hash
        ) from exc

    rows = doc.get("events") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise NormalizationError(
            "Dataset de eventos debe ser una lista (o {events: [...]})",
            source_hash=artifact.content_hash,
        )
    return [_row_to_event(r, i, artifact) for i, r in enumerate(rows)]


def _row_to_event(row: Any, idx: int, artifact: RawArtifact) -> ConflictEvent:
    if not isinstance(row, dict):
        raise NormalizationError(
            f"Evento {idx} no es un objeto JSON", source_hash=artifact.content_hash, line=idx
        )
    missing = [k for k in _REQUIRED if k not in row]
    if missing:
        raise NormalizationError(
            f"Evento {idx} sin campos requeridos: {missing}",
            source_hash=artifact.content_hash, line=idx,
        )
    try:
        return ConflictEvent(
            event_id=str(row["event_id"]),
            event_date=_parse_date(row["event_date"]),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            geoloc_resolution=_resolution(row),
            event_type=str(row.get("event_type", "")),
            location_name=str(row.get("location_name", "")),
            reported_fatalities=int(row.get("reported_fatalities", 0) or 0),
            source=str(row.get("source", "")),
            source_url=str(row.get("source_url", "")),
            notes=str(row.get("notes", "")),
            content_hash_source=artifact.content_hash,
            epistemic_label=EpistemicLabel.ASSERTED,
        )
    except (TypeError, ValueError) as exc:
        raise NormalizationError(
            f"Campo inválido en evento {idx}: {exc}",
            source_hash=artifact.content_hash, line=idx,
        ) from exc


def _parse_date(value: Any) -> date:
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date() \
            if "T" in value else date.fromisoformat(value)
    raise ValueError(f"event_date no es una fecha ISO: {value!r}")


def _resolution(row: dict) -> GeolocResolution:
    if "geoloc_resolution" in row:
        return GeolocResolution(str(row["geoloc_resolution"]))
    if "geo_precision" in row:
        return _ACLED_PRECISION.get(int(row["geo_precision"]), GeolocResolution.REGION)
    return GeolocResolution.CITY
