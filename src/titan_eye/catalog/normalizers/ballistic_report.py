"""Normalizador puro: RawArtifact (JSON de reporte) -> BallisticReport (ADR-0011).

Determinista, sin red. El reporte es un JSON estructurado que el operador compone
desde fuentes públicas (NOTAM, aviso, comunicado, prensa). Se conserva la etiqueta
`asserted` (es una afirmación de un tercero) y la procedencia por hash.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from titan_eye.catalog.ballistic import BallisticReport
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact

_REQUIRED = ("event_id", "launch_lat", "launch_lon", "impact_lat", "impact_lon", "apogee_km")


def normalize_ballistic_report(artifact: RawArtifact) -> BallisticReport:
    """Convierte el JSON del reporte en un BallisticReport (`asserted`)."""
    try:
        # utf-8-sig tolera un BOM opcional: los reportes públicos pueden venir
        # de editores Windows que lo añaden. No altera el contenido sin BOM.
        doc: Any = json.loads(artifact.payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "Reporte balístico no es JSON UTF-8 válido", source_hash=artifact.content_hash
        ) from exc

    if not isinstance(doc, dict):
        raise NormalizationError(
            "Reporte balístico debe ser un objeto JSON", source_hash=artifact.content_hash
        )
    missing = [k for k in _REQUIRED if k not in doc]
    if missing:
        raise NormalizationError(
            f"Reporte balístico sin campos requeridos: {missing}",
            source_hash=artifact.content_hash,
        )

    event_time = None
    if doc.get("event_time"):
        try:
            event_time = datetime.fromisoformat(str(doc["event_time"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise NormalizationError(
                f"event_time inválido: {doc['event_time']!r}", source_hash=artifact.content_hash
            ) from exc

    try:
        return BallisticReport(
            event_id=str(doc["event_id"]),
            launch_lat=float(doc["launch_lat"]),
            launch_lon=float(doc["launch_lon"]),
            impact_lat=float(doc["impact_lat"]),
            impact_lon=float(doc["impact_lon"]),
            apogee_km=float(doc["apogee_km"]),
            apogee_sigma_km=float(doc.get("apogee_sigma_km", 0.0)),
            geoloc_sigma_km=float(doc.get("geoloc_sigma_km", 0.0)),
            event_time=event_time,
            source=str(doc.get("source", "")),
            source_url=str(doc.get("source_url", "")),
            content_hash_source=artifact.content_hash,
            epistemic_label=EpistemicLabel.ASSERTED,
        )
    except (TypeError, ValueError) as exc:
        raise NormalizationError(
            f"Campo numérico inválido en reporte balístico: {exc}",
            source_hash=artifact.content_hash,
        ) from exc
