"""Tests del adaptador y normalizador GDELT (noticias geolocalizadas, OSINT)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from titan_eye.catalog.normalizers.gdelt_doc import normalize_gdelt_doc
from titan_eye.catalog.osint import SourceTier
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.core.timebase import FixedClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.sources.gdelt import GDELT_DOC_URL, GdeltSource
from titan_eye.ingestion.transport import FakeTransport

T0 = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)

_SAMPLE = {
    "articles": [
        {"url": "https://reuters.com/a1", "title": "Troops mass at border",
         "seendate": "20260613T101500Z", "domain": "reuters.com",
         "language": "English", "sourcecountry": "Ukraine"},
        {"url": "https://apnews.com/a2", "title": "Airstrike reported",
         "seendate": "20260613T090000Z", "domain": "apnews.com",
         "language": "English", "sourcecountry": "Israel"},
        {"url": "https://x.com/a3", "title": "second from Ukraine",
         "seendate": "20260613T080000Z", "domain": "x.com",
         "language": "English", "sourcecountry": "Ukraine"},
        {"url": "https://nowhere/a4", "title": "unmapped country",
         "seendate": "20260613T070000Z", "domain": "nowhere",
         "language": "English", "sourcecountry": "Atlantis"},
    ]
}


def _artifact(payload: bytes) -> RawArtifact:
    return RawArtifact.seal(
        source_id="gdelt.doc", domain=Domain.OSINT, request_url=GDELT_DOC_URL,
        fetched_at=T0, payload=payload, epistemic_label=EpistemicLabel.ASSERTED,
    )


def test_normalize_maps_articles_to_osint() -> None:
    items = normalize_gdelt_doc(_artifact(json.dumps(_SAMPLE).encode()))
    # 3 con país mapeado; "Atlantis" se omite (no se inventa ubicación)
    assert len(items) == 3
    assert all(it.epistemic_label is EpistemicLabel.ASSERTED for it in items)
    assert all(it.source_tier is SourceTier.NEWS_AGENCY for it in items)


def test_unmapped_country_is_dropped() -> None:
    items = normalize_gdelt_doc(_artifact(json.dumps(_SAMPLE).encode()))
    assert all(it.country != "Atlantis" for it in items)


def test_same_country_articles_are_spread() -> None:
    items = normalize_gdelt_doc(_artifact(json.dumps(_SAMPLE).encode()))
    ua = [it for it in items if it.country == "Ukraine"]
    assert len(ua) == 2
    # el desplazamiento determinista evita el solape exacto
    assert (ua[0].latitude, ua[0].longitude) != (ua[1].latitude, ua[1].longitude)


def test_seendate_parsed_to_utc() -> None:
    items = normalize_gdelt_doc(_artifact(json.dumps(_SAMPLE).encode()))
    it = next(i for i in items if i.source == "reuters.com")
    assert it.published_at == datetime(2026, 6, 13, 10, 15, 0, tzinfo=UTC)


def test_provenance_links_to_artifact() -> None:
    art = _artifact(json.dumps(_SAMPLE).encode())
    items = normalize_gdelt_doc(art)
    assert all(it.content_hash_source == art.content_hash for it in items)


def test_bad_json_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_gdelt_doc(_artifact(b"not json"))


def test_source_seals_with_provenance_and_no_network_escape() -> None:
    fake = FakeTransport()
    full = GDELT_DOC_URL + (
        "?query=q&mode=artlist&format=json&maxrecords=250&timespan=24h&sort=datedesc"
    )
    fake.register(full, json.dumps(_SAMPLE).encode())
    src = GdeltSource(transport=fake, clock=FixedClock(T0))
    art = src.fetch_doc(query="q")
    assert art.domain is Domain.OSINT
    assert art.epistemic_label is EpistemicLabel.ASSERTED
    items = normalize_gdelt_doc(art)
    assert len(items) == 3
