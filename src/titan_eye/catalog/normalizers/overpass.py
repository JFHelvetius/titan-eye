"""Normalizador puro: RawArtifact (Overpass JSON) -> list[Installation] (ADR-0017).

Determinista, sin red. Mapea las etiquetas `military=*`/`landuse=military` de OSM a
`InstallationType`. Nodos llevan lat/lon directos; ways/relations traen `center`
(por `out center`). Sin nombre o sin coordenadas -> se omite (P2: no se inventa).
Etiqueta `asserted` (ubicación afirmada por OSM, puede estar desactualizada).
"""

from __future__ import annotations

import json
from typing import Any

from titan_eye.catalog.installations import (
    Installation,
    InstallationType,
    category_for,
)
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact

OVERPASS_NORMALIZER_VERSION = "0.1.0"

# Etiqueta OSM -> tipo de instalación de Titan Eye.
_MILITARY_TAG_MAP: dict[str, InstallationType] = {
    "naval_base": InstallationType.NAVAL_BASE,
    "airfield": InstallationType.AIR_BASE,
    "barracks": InstallationType.ARMY_BASE,
    "base": InstallationType.ARMY_BASE,
    "danger_area": InstallationType.STRATEGIC,
    "training_area": InstallationType.STRATEGIC,
    "range": InstallationType.STRATEGIC,
    "bunker": InstallationType.COMMAND_CENTER,
}


def normalize_overpass_military(artifact: RawArtifact) -> list[Installation]:
    """Convierte la respuesta Overpass en una lista de Installation (`asserted`)."""
    try:
        doc: Any = json.loads(artifact.payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "Respuesta Overpass no es JSON UTF-8 válido", source_hash=artifact.content_hash
        ) from exc

    elements = doc.get("elements") if isinstance(doc, dict) else None
    if not isinstance(elements, list):
        raise NormalizationError(
            "Respuesta Overpass sin lista 'elements'", source_hash=artifact.content_hash
        )

    out: list[Installation] = []
    seen: set[str] = set()
    for el in elements:
        inst = _to_installation(el, artifact)
        if inst is not None and inst.installation_id not in seen:
            seen.add(inst.installation_id)
            out.append(inst)
    return out


def _to_installation(el: Any, artifact: RawArtifact) -> Installation | None:
    if not isinstance(el, dict):
        return None
    tags = el.get("tags") or {}
    name = tags.get("name") or tags.get("name:en")
    if not name:
        return None
    lat, lon = _coords(el)
    if lat is None or lon is None:
        return None
    itype = _type(tags)
    country = tags.get("addr:country") or tags.get("is_in:country") or None
    osm_type = str(el.get("type", "node"))
    osm_id = el.get("id", "")
    iid = f"osm-{osm_type}-{osm_id}"
    return Installation(
        installation_id=iid,
        name=str(name)[:200],
        latitude=lat,
        longitude=lon,
        installation_type=itype,
        category=category_for(itype),
        country=country,
        source="OpenStreetMap (Overpass)",
        source_url=f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
        notes="Geografía pública de OSM · puede estar incompleta/desactualizada (ADR-0017)",
        content_hash_source=artifact.content_hash,
        epistemic_label=EpistemicLabel.ASSERTED,
    )


def _coords(el: dict) -> tuple[float | None, float | None]:
    if "lat" in el and "lon" in el:
        return float(el["lat"]), float(el["lon"])
    center = el.get("center")
    if isinstance(center, dict) and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None, None


def _type(tags: dict) -> InstallationType:
    mil = tags.get("military")
    if mil and mil in _MILITARY_TAG_MAP:
        return _MILITARY_TAG_MAP[mil]
    if tags.get("landuse") == "military" or mil:
        return InstallationType.STRATEGIC  # área militar genérica
    return InstallationType.OTHER
