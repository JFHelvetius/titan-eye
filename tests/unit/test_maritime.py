"""Tests del dominio marítimo: normalizador AIS, globo, persistencia, integridad, CLI."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.unit.fixtures_ais import AIS_FIXTURE, AIS_TIME, ais_payload
from titan_eye.catalog.maritime import VesselPosition, VesselType
from titan_eye.catalog.normalizers.ais import normalize_ais
from titan_eye.catalog.vessel_positions_repo import VesselPositionsRepository
from titan_eye.core.domains import DOMAIN_UNCERTAINTY_NOTE, Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.orchestration.cli import run_ingest_maritime
from titan_eye.orchestration.globe_payload import vessels_to_entries

T0 = datetime(2026, 6, 12, 0, 0, 0, tzinfo=UTC)


def _artifact(payload: bytes | None = None) -> RawArtifact:
    return RawArtifact.seal(
        source_id="ais.vessels", domain=Domain.MARITIME,
        request_url="file://x", fetched_at=T0, payload=payload or ais_payload(),
        epistemic_label=EpistemicLabel.OBSERVED,
    )


def _vessels() -> list[VesselPosition]:
    return normalize_ais(_artifact())


# ── Dominio ──────────────────────────────────────────────────────────
def test_maritime_domain_registered() -> None:
    assert Domain.MARITIME.value == "maritime"
    assert "AIS" in DOMAIN_UNCERTAINTY_NOTE[Domain.MARITIME]
    assert "submarino" in DOMAIN_UNCERTAINTY_NOTE[Domain.MARITIME].lower()


# ── Normalizador (observed) ──────────────────────────────────────────
def test_vessels_observed_with_provenance() -> None:
    art = _artifact()
    vs = normalize_ais(art)
    assert len(vs) == 4
    assert all(v.epistemic_label is EpistemicLabel.OBSERVED for v in vs)
    assert all(v.content_hash_source == art.content_hash for v in vs)


def test_vessel_types_and_fallback() -> None:
    vs = {v.mmsi: v for v in _vessels()}
    assert vs["273000001"].vessel_type is VesselType.CARRIER
    assert vs["273000003"].vessel_type is VesselType.SUBMARINE
    assert vs["273000004"].vessel_type is VesselType.OTHER   # sin clase -> other
    assert vs["273000001"].name == "DEMO CARRIER"            # trim


def test_last_contact_age_and_snapshot() -> None:
    vs = {v.mmsi: v for v in _vessels()}
    assert vs["273000002"].last_contact_age_s == 600.0       # AIS_TIME - 600
    assert vs["273000001"].snapshot_time.timestamp() == AIS_TIME


def test_missing_field_raises() -> None:
    import json
    bad = {"vessels": [{"mmsi": "x", "latitude": 1.0}]}   # falta longitude
    with pytest.raises(NormalizationError):
        normalize_ais(_artifact(json.dumps(bad).encode()))


# ── Globo ────────────────────────────────────────────────────────────
def test_globe_entries() -> None:
    entries = {e["id"]: e for e in vessels_to_entries(_vessels())}
    assert entries["273000001"]["vessel_type"] == "carrier"
    assert "speed_kt" in entries["273000001"] and "course" in entries["273000001"]


# ── Persistencia + integridad ────────────────────────────────────────
def test_repo_roundtrip_idempotent(tmp_path) -> None:
    repo = VesselPositionsRepository(tmp_path)
    assert repo.insert_snapshot(_vessels()) is True
    assert repo.insert_snapshot(_vessels()) is False
    assert repo.count() == 4
    sub = repo.find_by_mmsi("273000003")
    assert len(sub) == 1 and sub[0].vessel_type is VesselType.SUBMARINE


def test_maritime_integrity_clean(tmp_path) -> None:
    from titan_eye.ingestion.cache import FetchCache
    from titan_eye.provenance.integrity import verify_maritime_integrity

    cache = FetchCache(tmp_path / "cache")
    art = _artifact()
    cache.put(art, cache_key="k")
    repo = VesselPositionsRepository(tmp_path / "norm")
    repo.insert_snapshot(normalize_ais(art))
    report = verify_maritime_integrity(repo, cache)
    assert report.ok is True
    assert report.n_states == 4 and report.n_source_hashes == 1


# ── CLI ──────────────────────────────────────────────────────────────
def test_cli_ingest_maritime_is_observed() -> None:
    summary, vessels = run_ingest_maritime(artifact=_artifact())
    assert summary["domain"] == "maritime"
    assert summary["epistemic_label"] == "observed"
    assert summary["n_vessels"] == 4
    assert summary["by_vessel_type"]["carrier"] == 1
    assert "AUTODECLARADO" in summary["note"]
    assert len(vessels) == 4


def test_fixture_has_four() -> None:
    assert len(AIS_FIXTURE["vessels"]) == 4


def test_cli_persist_then_verify_clean(tmp_path) -> None:
    # Regresión: el ingest --persist debe sellar el Raw en la cache para que
    # verify-maritime tenga su ancla (I1). Ejercita el camino CLI completo.
    from titan_eye.orchestration.cli import cli_entry_point

    ais_file = tmp_path / "ais.json"
    ais_file.write_bytes(ais_payload())
    root = tmp_path / "data"
    rc1 = cli_entry_point(["ingest", "maritime", "--vessels", str(ais_file),
                           "--data-root", str(root), "--persist"])
    assert rc1 == 0
    rc2 = cli_entry_point(["verify-maritime", "--data-root", str(root)])
    assert rc2 == 0   # ok=true (sin huérfanos)
