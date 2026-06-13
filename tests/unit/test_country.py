"""Tests de fichas país y alianzas (ADR-0021): cifras públicas con procedencia, sin ranking."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.unit.fixtures_country import countries_payload
from titan_eye.catalog.country import CountryProfile
from titan_eye.catalog.country_repo import CountryRepository
from titan_eye.catalog.normalizers.country import normalize_countries
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.orchestration.cli import run_ingest_countries

T0 = datetime(2026, 6, 13, 0, 0, 0, tzinfo=UTC)


def _artifact(payload: bytes | None = None) -> RawArtifact:
    return RawArtifact.seal(
        source_id="countries.reference", domain=Domain.REFERENCE,
        request_url="file://x", fetched_at=T0, payload=payload or countries_payload(),
        epistemic_label=EpistemicLabel.ASSERTED,
    )


def _items() -> list[CountryProfile]:
    return normalize_countries(_artifact())


def test_asserted_with_provenance() -> None:
    art = _artifact()
    items = normalize_countries(art)
    assert len(items) == 3
    assert all(c.epistemic_label is EpistemicLabel.ASSERTED for c in items)
    assert all(c.content_hash_source == art.content_hash for c in items)


def test_fields_and_minimal_profile() -> None:
    c = {x.country: x for x in _items()}
    assert c["Atlantia"].military_budget_usd == 50_000_000_000
    assert c["Atlantia"].budget_year == 2025
    assert "NATO-like" in c["Atlantia"].alliances
    # Ficha mínima: opcionales None, alianzas vacías (no se inventa nada).
    assert c["Meridia"].military_budget_usd is None
    assert c["Meridia"].alliances == []


def test_missing_country_raises() -> None:
    import json
    with pytest.raises(NormalizationError):
        normalize_countries(_artifact(json.dumps([{"iso_code": "X"}]).encode()))


def test_alliances_must_be_list() -> None:
    import json
    bad = [{"country": "X", "alliances": "NATO"}]   # string, no lista
    with pytest.raises(NormalizationError):
        normalize_countries(_artifact(json.dumps(bad).encode()))


def test_repo_roundtrip_idempotent(tmp_path) -> None:
    repo = CountryRepository(tmp_path)
    assert repo.insert_snapshot(_items()) is True
    assert repo.insert_snapshot(_items()) is False
    assert repo.count() == 3
    back = {c.country: c for c in repo.iter_all()}
    assert back["Atlantia"].alliances == ["NATO-like", "UN-like"]   # lista preservada
    assert back["Meridia"].active_personnel is None


def test_integrity_clean(tmp_path) -> None:
    from titan_eye.ingestion.cache import FetchCache
    from titan_eye.provenance.integrity import verify_country_integrity

    cache = FetchCache(tmp_path / "cache")
    art = _artifact()
    cache.put(art, cache_key="k")
    repo = CountryRepository(tmp_path / "ref")
    repo.insert_snapshot(normalize_countries(art))
    rep = verify_country_integrity(repo, cache)
    assert rep.ok is True and rep.n_states == 3


def test_cli_no_ranking_no_threat() -> None:
    summary, items = run_ingest_countries(artifact=_artifact())
    assert summary["layer"] == "countries"
    assert summary["epistemic_label"] == "asserted"
    assert summary["n_countries"] == 3
    assert summary["alliances"]["UN-like"] == 2
    note = summary["note"].lower()
    assert "sin ranking" in note and "amenaza" in note
    assert len(items) == 3
