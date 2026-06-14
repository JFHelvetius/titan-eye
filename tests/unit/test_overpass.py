"""Tests del adaptador y normalizador Overpass/OSM (instalaciones militares)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from titan_eye.catalog.installations import InstallationCategory, InstallationType
from titan_eye.catalog.normalizers.overpass import normalize_overpass_military
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.sources.overpass import OVERPASS_URL, OverpassSource

T0 = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)

_SAMPLE = {
    "version": 0.6,
    "elements": [
        {"type": "node", "id": 1, "lat": 36.6, "lon": -76.3,
         "tags": {"military": "naval_base", "name": "Naval Station Norfolk",
                  "addr:country": "US"}},
        {"type": "way", "id": 2, "center": {"lat": 51.5, "lon": 7.6},
         "tags": {"military": "airfield", "name": "Fliegerhorst"}},
        {"type": "relation", "id": 3, "center": {"lat": 55.7, "lon": 37.6},
         "tags": {"landuse": "military", "name": "Poligono"}},
        {"type": "node", "id": 4, "lat": 1.0, "lon": 1.0,
         "tags": {"military": "barracks"}},          # sin nombre -> se omite
        {"type": "node", "id": 5,
         "tags": {"military": "base", "name": "Sin coords"}},  # sin coords -> se omite
    ],
}


def _artifact(payload: bytes) -> RawArtifact:
    return RawArtifact.seal(
        source_id="osm.overpass", domain=Domain.REFERENCE, request_url=OVERPASS_URL,
        fetched_at=T0, payload=payload, epistemic_label=EpistemicLabel.ASSERTED,
    )


def test_maps_tags_to_types() -> None:
    items = normalize_overpass_military(_artifact(json.dumps(_SAMPLE).encode()))
    by_id = {it.installation_id: it for it in items}
    assert by_id["osm-node-1"].installation_type is InstallationType.NAVAL_BASE
    assert by_id["osm-way-2"].installation_type is InstallationType.AIR_BASE
    assert by_id["osm-relation-3"].installation_type is InstallationType.STRATEGIC


def test_all_classified_military() -> None:
    items = normalize_overpass_military(_artifact(json.dumps(_SAMPLE).encode()))
    assert all(it.category is InstallationCategory.MILITARY for it in items)


def test_drops_unnamed_and_uncoordinated() -> None:
    items = normalize_overpass_military(_artifact(json.dumps(_SAMPLE).encode()))
    ids = {it.installation_id for it in items}
    assert ids == {"osm-node-1", "osm-way-2", "osm-relation-3"}  # 4 y 5 omitidos


def test_way_uses_center_coords() -> None:
    items = normalize_overpass_military(_artifact(json.dumps(_SAMPLE).encode()))
    way = next(it for it in items if it.installation_id == "osm-way-2")
    assert (way.latitude, way.longitude) == (51.5, 7.6)


def test_provenance_and_asserted() -> None:
    art = _artifact(json.dumps(_SAMPLE).encode())
    items = normalize_overpass_military(art)
    assert all(it.content_hash_source == art.content_hash for it in items)
    assert all(it.epistemic_label is EpistemicLabel.ASSERTED for it in items)
    assert all(it.source_url.startswith("https://www.openstreetmap.org/") for it in items)


def test_bad_json_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_overpass_military(_artifact(b"<html>error</html>"))


def test_source_seals_reference_domain() -> None:
    from titan_eye.core.timebase import FixedClock
    from titan_eye.ingestion.transport import FakeTransport

    fake = FakeTransport()
    src = OverpassSource(transport=fake, clock=FixedClock(T0))
    # Registrar la URL completa que generará el GET (data urlencoded).
    import urllib.parse

    from titan_eye.ingestion.sources.overpass import _query
    full = OVERPASS_URL + "?" + urllib.parse.urlencode({"data": _query(1500)})
    fake.register(full, json.dumps(_SAMPLE).encode())
    art = src.fetch_military()
    assert art.domain is Domain.REFERENCE
    assert art.epistemic_label is EpistemicLabel.ASSERTED
    assert len(normalize_overpass_military(art)) == 3
