"""Tests de persistencia Normalized (ADR-0008) e integridad (ADR-0005)."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.unit.fixtures_opensky import opensky_payload
from titan_eye.catalog.aircraft_states_repo import AircraftStatesRepository
from titan_eye.catalog.normalizers.opensky_states import normalize_states
from titan_eye.core.domains import Domain
from titan_eye.core.timebase import FixedClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.cache import FetchCache
from titan_eye.ingestion.sources.opensky import OPENSKY_STATES_URL, OpenSkySource
from titan_eye.ingestion.transport import FakeTransport, TransportResponse
from titan_eye.orchestration.ingest_pipeline import AerialIngestPipeline
from titan_eye.provenance.integrity import verify_aerial_integrity

T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


def _states() -> list:
    art = RawArtifact.seal(
        source_id="opensky.states", domain=Domain.AERIAL,
        request_url="u", fetched_at=T0, payload=opensky_payload(),
    )
    return normalize_states(art)


# ── Repositorio ──────────────────────────────────────────────────────
def test_insert_and_count(tmp_path) -> None:
    repo = AircraftStatesRepository(tmp_path)
    assert repo.insert_snapshot(_states()) is True
    assert repo.count() == 3


def test_insert_is_idempotent(tmp_path) -> None:
    repo = AircraftStatesRepository(tmp_path)
    repo.insert_snapshot(_states())
    assert repo.insert_snapshot(_states()) is False  # mismo Raw -> no-op
    assert repo.count() == 3
    files = list(tmp_path.rglob("*.parquet"))
    assert len(files) == 1


def test_roundtrip_preserves_fields(tmp_path) -> None:
    repo = AircraftStatesRepository(tmp_path)
    repo.insert_snapshot(_states())
    a = next(s for s in repo.iter_all() if s.icao24 == "abc123")
    assert a.callsign == "DEMO01"
    assert a.latitude == 49.5 and a.longitude == 33.0
    assert a.position_source == "ADS-B"
    assert a.epistemic_label.value == "observed"


def test_partition_layout_year_month_day(tmp_path) -> None:
    repo = AircraftStatesRepository(tmp_path)
    repo.insert_snapshot(_states())
    f = next(tmp_path.rglob("*.parquet"))
    parts = f.parts
    assert "year=2026" in parts and "month=06" in parts and "day=11" in parts


def test_find_by_icao24(tmp_path) -> None:
    repo = AircraftStatesRepository(tmp_path)
    repo.insert_snapshot(_states())
    rows = repo.find_by_icao24("def456")
    assert len(rows) == 1 and rows[0].position_source == "MLAT"


# ── Integridad ───────────────────────────────────────────────────────
def _wired(tmp_path):
    ft = FakeTransport()
    ft.responses[OPENSKY_STATES_URL] = TransportResponse(
        url=OPENSKY_STATES_URL, status=200, body=opensky_payload(), media_type="application/json"
    )
    cache = FetchCache(tmp_path / "cache")
    repo = AircraftStatesRepository(tmp_path / "norm")
    source = OpenSkySource(transport=ft, cache=cache, clock=FixedClock(T0))
    return source, cache, repo


def test_pipeline_persists_and_verifies_clean(tmp_path) -> None:
    source, cache, repo = _wired(tmp_path)
    result = AerialIngestPipeline(source, repo).ingest()
    assert result.snapshot_written is True
    report = verify_aerial_integrity(repo, cache)
    assert report.ok is True
    assert report.n_states == 3
    assert report.n_source_hashes == 1
    assert report.orphan_source_hashes == []


def test_integrity_detects_orphan_when_blob_missing(tmp_path) -> None:
    source, cache, repo = _wired(tmp_path)
    AerialIngestPipeline(source, repo).ingest()
    # Borra el blob Raw -> el Normalized queda huérfano (I1 debe detectarlo).
    for blob in (tmp_path / "cache" / "blobs").rglob("*.bin"):
        blob.unlink()
    report = verify_aerial_integrity(repo, cache)
    assert report.ok is False
    assert len(report.orphan_source_hashes) == 1


def test_integrity_reproducibility_holds(tmp_path) -> None:
    source, cache, repo = _wired(tmp_path)
    AerialIngestPipeline(source, repo).ingest()
    report = verify_aerial_integrity(repo, cache, check_reproducibility=True)
    assert report.reproducibility_mismatches == []
    assert report.ok is True
