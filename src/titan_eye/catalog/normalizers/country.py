"""Normalizador puro: RawArtifact (JSON) -> list[CountryProfile] (ADR-0021).

Determinista, sin red. Acepta una lista o {countries:[...]}. Conserva `asserted`.
No inventa cifras ni alianzas: campos ausentes quedan en None / lista vacía.
"""

from __future__ import annotations

import json
from typing import Any

from titan_eye.catalog.country import CountryProfile
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact

COUNTRY_NORMALIZER_VERSION = "0.1.0"


def normalize_countries(artifact: RawArtifact) -> list[CountryProfile]:
    """Convierte el JSON de fichas país en una lista de CountryProfile."""
    try:
        doc: Any = json.loads(artifact.payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "Dataset de países no es JSON UTF-8 válido", source_hash=artifact.content_hash
        ) from exc

    rows = doc.get("countries") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise NormalizationError(
            "Dataset de países debe ser una lista (o {countries:[...]})",
            source_hash=artifact.content_hash,
        )
    return [_row(r, i, artifact) for i, r in enumerate(rows)]


def _row(row: Any, idx: int, artifact: RawArtifact) -> CountryProfile:
    if not isinstance(row, dict):
        raise NormalizationError(
            f"Ficha país {idx} no es un objeto JSON",
            source_hash=artifact.content_hash, line=idx,
        )
    if "country" not in row:
        raise NormalizationError(
            f"Ficha país {idx} sin campo requerido 'country'",
            source_hash=artifact.content_hash, line=idx,
        )
    alliances = row.get("alliances") or []
    if not isinstance(alliances, list):
        raise NormalizationError(
            f"'alliances' debe ser una lista en ficha {idx}",
            source_hash=artifact.content_hash, line=idx,
        )
    try:
        return CountryProfile(
            country=str(row["country"]),
            iso_code=row.get("iso_code") or None,
            region=row.get("region") or None,
            military_budget_usd=_f(row.get("military_budget_usd")),
            budget_year=_i(row.get("budget_year")),
            active_personnel=_i(row.get("active_personnel")),
            reserve_personnel=_i(row.get("reserve_personnel")),
            alliances=[str(a) for a in alliances],
            source=str(row.get("source", "")),
            source_url=str(row.get("source_url", "")),
            notes=str(row.get("notes", "")),
            content_hash_source=artifact.content_hash,
            epistemic_label=EpistemicLabel.ASSERTED,
        )
    except (TypeError, ValueError) as exc:
        raise NormalizationError(
            f"Campo inválido en ficha país {idx}: {exc}",
            source_hash=artifact.content_hash, line=idx,
        ) from exc


def _f(v: Any) -> float | None:
    return None if v is None else float(v)


def _i(v: Any) -> int | None:
    return None if v is None else int(v)
