"""Normalizador puro: RawArtifact (JSON) -> list[OsintItem] (ADR-0020).

Determinista, sin red. Acepta una lista o {items:[...]}. Conserva `asserted` y la
procedencia. El `source_tier` desconocido cae a `other` (no se inventa un tier).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from titan_eye.catalog.osint import OsintItem, SourceTier
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact

OSINT_NORMALIZER_VERSION = "0.1.0"
_REQUIRED = ("item_id", "title", "latitude", "longitude")


def normalize_osint(artifact: RawArtifact) -> list[OsintItem]:
    """Convierte el JSON OSINT en una lista de OsintItem (`asserted`)."""
    try:
        doc: Any = json.loads(artifact.payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "Dataset OSINT no es JSON UTF-8 válido", source_hash=artifact.content_hash
        ) from exc

    rows = doc.get("items") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise NormalizationError(
            "Dataset OSINT debe ser una lista (o {items:[...]})",
            source_hash=artifact.content_hash,
        )
    return [_row(r, i, artifact) for i, r in enumerate(rows)]


def _row(row: Any, idx: int, artifact: RawArtifact) -> OsintItem:
    if not isinstance(row, dict):
        raise NormalizationError(
            f"Ítem OSINT {idx} no es un objeto JSON",
            source_hash=artifact.content_hash, line=idx,
        )
    missing = [k for k in _REQUIRED if k not in row]
    if missing:
        raise NormalizationError(
            f"Ítem OSINT {idx} sin campos requeridos: {missing}",
            source_hash=artifact.content_hash, line=idx,
        )
    published = None
    if row.get("published_at"):
        try:
            published = datetime.fromisoformat(str(row["published_at"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise NormalizationError(
                f"published_at inválido en ítem {idx}: {row['published_at']!r}",
                source_hash=artifact.content_hash, line=idx,
            ) from exc
    try:
        return OsintItem(
            item_id=str(row["item_id"]),
            title=str(row["title"]),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            source=str(row.get("source", "")),
            source_url=str(row.get("source_url", "")),
            source_tier=_tier(row),
            published_at=published,
            country=row.get("country") or None,
            summary=str(row.get("summary", "")),
            content_hash_source=artifact.content_hash,
            epistemic_label=EpistemicLabel.ASSERTED,
        )
    except (TypeError, ValueError) as exc:
        raise NormalizationError(
            f"Campo inválido en ítem OSINT {idx}: {exc}",
            source_hash=artifact.content_hash, line=idx,
        ) from exc


def _tier(row: dict) -> SourceTier:
    if row.get("source_tier"):
        try:
            return SourceTier(str(row["source_tier"]).lower())
        except ValueError:
            return SourceTier.OTHER
    return SourceTier.OTHER
