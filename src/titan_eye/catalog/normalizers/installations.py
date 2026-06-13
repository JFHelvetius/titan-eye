"""Normalizador puro: RawArtifact (JSON) -> list[Installation] (ADR-0017).

Determinista, sin red. Acepta una lista o {installations:[...]}. La categoría se
deriva del tipo si no se da explícita. Conserva `asserted` y la procedencia.
"""

from __future__ import annotations

import json
from typing import Any

from titan_eye.catalog.installations import (
    Installation,
    InstallationCategory,
    InstallationType,
    category_for,
)
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact

INSTALLATIONS_NORMALIZER_VERSION = "0.1.0"
_REQUIRED = ("installation_id", "name", "latitude", "longitude")


def normalize_installations(artifact: RawArtifact) -> list[Installation]:
    """Convierte el JSON de instalaciones en una lista de Installation (`asserted`)."""
    try:
        doc: Any = json.loads(artifact.payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "Dataset de instalaciones no es JSON UTF-8 válido", source_hash=artifact.content_hash
        ) from exc

    rows = doc.get("installations") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise NormalizationError(
            "Dataset de instalaciones debe ser una lista (o {installations:[...]})",
            source_hash=artifact.content_hash,
        )
    return [_row(r, i, artifact) for i, r in enumerate(rows)]


def _row(row: Any, idx: int, artifact: RawArtifact) -> Installation:
    if not isinstance(row, dict):
        raise NormalizationError(
            f"Instalación {idx} no es un objeto JSON",
            source_hash=artifact.content_hash, line=idx,
        )
    missing = [k for k in _REQUIRED if k not in row]
    if missing:
        raise NormalizationError(
            f"Instalación {idx} sin campos requeridos: {missing}",
            source_hash=artifact.content_hash, line=idx,
        )
    itype = _type(row)
    try:
        return Installation(
            installation_id=str(row["installation_id"]),
            name=str(row["name"]),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            installation_type=itype,
            category=_category(row, itype),
            country=row.get("country") or None,
            source=str(row.get("source", "")),
            source_url=str(row.get("source_url", "")),
            notes=str(row.get("notes", "")),
            content_hash_source=artifact.content_hash,
            epistemic_label=EpistemicLabel.ASSERTED,
        )
    except (TypeError, ValueError) as exc:
        raise NormalizationError(
            f"Campo inválido en instalación {idx}: {exc}",
            source_hash=artifact.content_hash, line=idx,
        ) from exc


def _type(row: dict) -> InstallationType:
    if row.get("installation_type"):
        try:
            return InstallationType(str(row["installation_type"]).lower())
        except ValueError:
            return InstallationType.OTHER
    return InstallationType.OTHER


def _category(row: dict, itype: InstallationType) -> InstallationCategory:
    if row.get("category"):
        try:
            return InstallationCategory(str(row["category"]).lower())
        except ValueError:
            pass
    return category_for(itype)
