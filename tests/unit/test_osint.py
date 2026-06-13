"""Tests de la capa OSINT (ADR-0020): asserted, procedencia, sin veredicto de veracidad."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.unit.fixtures_osint import osint_payload
from titan_eye.catalog.normalizers.osint import normalize_osint
from titan_eye.catalog.osint import OsintItem, SourceTier
from titan_eye.catalog.osint_repo import OsintRepository
from titan_eye.core.domains import DOMAIN_UNCERTAINTY_NOTE, Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.orchestration.cli import run_ingest_osint
from titan_eye.orchestration.globe_payload import osint_to_entries

T0 = datetime(2026, 6, 12, 0, 0, 0, tzinfo=UTC)


def _artifact(payload: bytes | None = None) -> RawArtifact:
    return RawArtifact.seal(
        source_id="osint.items", domain=Domain.OSINT,
        request_url="file://x", fetched_at=T0, payload=payload or osint_payload(),
        epistemic_label=EpistemicLabel.ASSERTED,
    )


def _items() -> list[OsintItem]:
    return normalize_osint(_artifact())


def test_osint_domain_tag_note() -> None:
    note = DOMAIN_UNCERTAINTY_NOTE[Domain.OSINT].lower()
    assert "no verdad" in note or "no es verdad" in note or "afirmación" in note


def test_items_asserted_with_provenance() -> None:
    art = _artifact()
    items = normalize_osint(art)
    assert len(items) == 4
    assert all(i.epistemic_label is EpistemicLabel.ASSERTED for i in items)
    assert all(i.content_hash_source == art.content_hash for i in items)


def test_source_tier_and_fallback() -> None:
    items = {i.item_id: i for i in _items()}
    assert items["N1"].source_tier is SourceTier.NEWS_AGENCY
    assert items["N2"].source_tier is SourceTier.GOVERNMENT
    assert items["N3"].source_tier is SourceTier.SOCIAL_MEDIA
    assert items["N4"].source_tier is SourceTier.OTHER       # sin tier
    assert items["N1"].published_at is not None and items["N2"].published_at is None


def test_missing_field_raises() -> None:
    import json
    bad = [{"item_id": "x", "title": "y", "latitude": 1.0}]   # falta longitude
    with pytest.raises(NormalizationError):
        normalize_osint(_artifact(json.dumps(bad).encode()))


def test_globe_entries_filterable() -> None:
    e = {x["id"]: x for x in osint_to_entries(_items())}
    assert e["N3"]["kind"] == "social_media"          # eje de filtro = tier
    assert e["N1"]["country"] == "Borealia"
    assert "source_url" in e["N1"]


def test_repo_roundtrip_idempotent(tmp_path) -> None:
    repo = OsintRepository(tmp_path)
    assert repo.insert_snapshot(_items()) is True
    assert repo.insert_snapshot(_items()) is False
    assert repo.count() == 4


def test_integrity_clean(tmp_path) -> None:
    from titan_eye.ingestion.cache import FetchCache
    from titan_eye.provenance.integrity import verify_osint_integrity

    cache = FetchCache(tmp_path / "cache")
    art = _artifact()
    cache.put(art, cache_key="k")
    repo = OsintRepository(tmp_path / "osint")
    repo.insert_snapshot(normalize_osint(art))
    rep = verify_osint_integrity(repo, cache)
    assert rep.ok is True and rep.n_states == 4


def test_cli_ingest_osint_no_veracity_verdict() -> None:
    summary, items = run_ingest_osint(artifact=_artifact())
    assert summary["layer"] == "osint"
    assert summary["epistemic_label"] == "asserted"
    assert summary["n_items"] == 4
    assert summary["by_source_tier"]["news_agency"] == 1
    note = summary["note"].lower()
    assert "no verifica" in note and "credibilidad" in note
    assert len(items) == 4
