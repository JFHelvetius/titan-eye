"""Normalizador puro: RawArtifact (JSON AIS) -> list[VesselPosition] (ADR-0015).

Determinista, sin red. Acepta una lista de buques o {vessels:[...]} / {states:[...]}.
Conserva la etiqueta `observed` (autodeclarada por el buque) y la procedencia por
hash. Mapea tipos AIS conocidos a `VesselType` cuando el dataset no da clase explícita.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from titan_eye.catalog.maritime import VesselPosition, VesselType
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.core.timebase import from_unix
from titan_eye.ingestion.artifact import RawArtifact

AIS_NORMALIZER_VERSION = "0.1.0"
_REQUIRED = ("mmsi", "latitude", "longitude")


def normalize_ais(artifact: RawArtifact) -> list[VesselPosition]:
    """Convierte el JSON AIS en una lista de VesselPosition (`observed`)."""
    try:
        doc: Any = json.loads(artifact.payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "Dataset AIS no es JSON UTF-8 válido", source_hash=artifact.content_hash
        ) from exc

    rows = doc
    if isinstance(doc, dict):
        rows = doc.get("vessels") or doc.get("states") or doc.get("data")
    if not isinstance(rows, list):
        raise NormalizationError(
            "Dataset AIS debe ser una lista (o {vessels:[...]})",
            source_hash=artifact.content_hash,
        )
    snap = _snapshot_time(doc, artifact)
    return [_row_to_vessel(r, i, artifact, snap) for i, r in enumerate(rows)]


def _snapshot_time(doc: Any, artifact: RawArtifact) -> datetime:
    if isinstance(doc, dict) and isinstance(doc.get("time"), (int, float)):
        return from_unix(float(doc["time"]))
    return artifact.fetched_at.astimezone(UTC)


def _row_to_vessel(row: Any, idx: int, artifact: RawArtifact, snap: datetime) -> VesselPosition:
    if not isinstance(row, dict):
        raise NormalizationError(
            f"Buque {idx} no es un objeto JSON", source_hash=artifact.content_hash, line=idx
        )
    missing = [k for k in _REQUIRED if k not in row]
    if missing:
        raise NormalizationError(
            f"Buque {idx} sin campos requeridos: {missing}",
            source_hash=artifact.content_hash, line=idx,
        )
    last_contact = _ts(row.get("last_contact"), snap)
    age = (snap - last_contact).total_seconds()
    try:
        return VesselPosition(
            mmsi=str(row["mmsi"]),
            name=(str(row["name"]).strip() or None) if row.get("name") else None,
            vessel_type=_vessel_type(row),
            flag=row.get("flag") or None,
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            course_deg=_f(row.get("course")),
            heading_deg=_f(row.get("heading")),
            speed_knots=_f(row.get("speed")),
            nav_status=row.get("nav_status") or None,
            last_contact=last_contact,
            last_contact_age_s=age,
            content_hash_source=artifact.content_hash,
            snapshot_time=snap,
            epistemic_label=EpistemicLabel.OBSERVED,
        )
    except (TypeError, ValueError) as exc:
        raise NormalizationError(
            f"Campo inválido en buque {idx}: {exc}",
            source_hash=artifact.content_hash, line=idx,
        ) from exc


def _vessel_type(row: dict) -> VesselType:
    if row.get("vessel_type"):
        try:
            return VesselType(str(row["vessel_type"]).lower())
        except ValueError:
            return VesselType.OTHER
    return VesselType.OTHER


def _ts(value: Any, default: datetime) -> datetime:
    if isinstance(value, (int, float)):
        return from_unix(float(value))
    return default


def _f(v: Any) -> float | None:
    return None if v is None else float(v)
