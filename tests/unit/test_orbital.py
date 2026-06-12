"""Tests del dominio orbital: parser TLE, SGP4, groundtrack, globo, repo, CLI."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.unit.fixtures_tle import ISS_LINE1, ISS_LINE2, iss_payload, multi_payload
from titan_eye.analytics.propagation.frames import ecef_to_geodetic_spherical, gmst_iau_1982
from titan_eye.analytics.propagation.sgp4_propagator import groundtrack, propagate_geodetic
from titan_eye.catalog.normalizers.tle import normalize_tles
from titan_eye.catalog.orbital import OrbitalElement
from titan_eye.catalog.orbital_elements_repo import OrbitalElementsRepository
from titan_eye.core.domains import Domain
from titan_eye.core.errors import NormalizationError
from titan_eye.core.timebase import FixedClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.sources.celestrak import CELESTRAK_GP_URL, CelesTrakSource
from titan_eye.ingestion.transport import FakeTransport, TransportResponse
from titan_eye.orchestration.cli import run_ingest_orbital
from titan_eye.orchestration.globe_payload import orbital_elements_to_entries

T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


def _artifact(payload: bytes) -> RawArtifact:
    return RawArtifact.seal(
        source_id="celestrak.gp", domain=Domain.ORBITAL,
        request_url="u", fetched_at=T0, payload=payload,
    )


def _iss() -> OrbitalElement:
    return normalize_tles(_artifact(iss_payload()))[0]


# ── Parser TLE ───────────────────────────────────────────────────────
def test_parse_iss_fields() -> None:
    e = _iss()
    assert e.norad_cat_id == 25544
    assert e.object_name == "ISS (ZARYA)"
    assert e.inclination_deg == pytest.approx(51.6416, abs=1e-4)
    assert e.eccentricity == pytest.approx(0.0006703, abs=1e-7)
    assert e.mean_motion_rev_per_day == pytest.approx(15.72125391, abs=1e-6)
    assert e.line1 == ISS_LINE1 and e.line2 == ISS_LINE2


def test_epoch_parsed_to_2008() -> None:
    e = _iss()
    assert e.epoch.year == 2008
    assert e.epoch.tzinfo is not None


def test_derived_period_and_altitude() -> None:
    e = _iss()
    assert e.period_min == pytest.approx(91.6, abs=0.5)
    assert 300 < e.mean_altitude_km < 450  # ISS LEO


def test_multi_block_parse() -> None:
    elements = normalize_tles(_artifact(multi_payload()))
    assert len(elements) == 2
    assert {e.norad_cat_id for e in elements} == {25544, 48274}


def test_provenance_fk() -> None:
    art = _artifact(iss_payload())
    e = normalize_tles(art)[0]
    assert e.content_hash_source == art.content_hash
    assert len(e.tle_content_hash) == 64


def test_malformed_tle_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_tles(_artifact(b"esto no es un TLE\n"))


# ── Marcos de referencia ─────────────────────────────────────────────
def test_gmst_j2000_reference() -> None:
    # GMST en J2000 (2000-01-01 12:00 UTC) ≈ 280.46°
    import math
    g = gmst_iau_1982(datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC))
    assert math.degrees(g) == pytest.approx(280.46, abs=0.1)


def test_geodetic_north_pole() -> None:
    lat, _lon, alt = ecef_to_geodetic_spherical(0.0, 0.0, 6771.0)
    assert lat == pytest.approx(90.0, abs=1e-6)
    assert alt == pytest.approx(400.0, abs=1.0)


# ── SGP4 ─────────────────────────────────────────────────────────────
def test_propagate_iss_physical_sanity() -> None:
    e = _iss()
    pt = propagate_geodetic(e, [e.epoch])[0]
    assert pt.sgp4_error_code == 0
    assert -52.0 <= pt.latitude <= 52.0          # |lat| <= inclinación
    assert -180.0 <= pt.longitude <= 180.0
    assert 200.0 < pt.altitude_km < 500.0        # LEO


def test_propagate_determinism() -> None:
    e = _iss()
    a = propagate_geodetic(e, [e.epoch, T0])
    b = propagate_geodetic(e, [e.epoch, T0])
    assert [(p.latitude, p.longitude, p.altitude_km) for p in a] == \
           [(p.latitude, p.longitude, p.altitude_km) for p in b]


def test_groundtrack_one_period() -> None:
    e = _iss()
    pts = groundtrack(e, start=e.epoch, span_min=e.period_min, step_min=e.period_min / 30)
    assert len(pts) >= 30
    assert all(p.sgp4_error_code == 0 for p in pts)


# ── Globo ────────────────────────────────────────────────────────────
def test_orbital_globe_entries() -> None:
    e = _iss()
    entries = orbital_elements_to_entries([e], at=e.epoch)
    assert len(entries) == 1
    ent = entries[0]
    assert ent["id"] == 25544
    assert ent["name"] == "ISS (ZARYA)"
    assert len(ent["track"]) > 10
    assert ent["err_km"] >= 2.0  # error declarado (P2)


# ── Repositorio ──────────────────────────────────────────────────────
def test_orbital_repo_roundtrip(tmp_path) -> None:
    repo = OrbitalElementsRepository(tmp_path)
    elements = normalize_tles(_artifact(multi_payload()))
    assert repo.insert_snapshot(elements) is True
    assert repo.insert_snapshot(elements) is False  # idempotente
    assert repo.count() == 2
    iss = repo.find_by_norad(25544)
    assert len(iss) == 1 and iss[0].line1 == ISS_LINE1


# ── Fuente + CLI ─────────────────────────────────────────────────────
def _fake_source() -> CelesTrakSource:
    ft = FakeTransport()
    full = f"{CELESTRAK_GP_URL}?GROUP=stations&FORMAT=tle"
    ft.responses[full] = TransportResponse(
        url=full, status=200, body=multi_payload(), media_type="text/plain"
    )
    return CelesTrakSource(transport=ft, clock=FixedClock(T0))


def test_cli_ingest_orbital() -> None:
    summary = run_ingest_orbital(source=_fake_source(), group="stations", catnr=None)
    assert summary["domain"] == "orbital"
    assert summary["n_elements"] == 2
    assert summary["epistemic_label"] == "observed"
    assert "celestrak" in summary["license_note"].lower()
    assert len(summary["sample"]) == 2


# ── Integridad orbital (paridad con el aéreo) ────────────────────────
def _orbital_wired(tmp_path):
    from titan_eye.ingestion.cache import FetchCache
    ft = FakeTransport()
    full = f"{CELESTRAK_GP_URL}?GROUP=stations&FORMAT=tle"
    ft.responses[full] = TransportResponse(
        url=full, status=200, body=multi_payload(), media_type="text/plain"
    )
    cache = FetchCache(tmp_path / "cache")
    repo = OrbitalElementsRepository(tmp_path / "norm")
    source = CelesTrakSource(transport=ft, cache=cache, clock=FixedClock(T0))
    return source, cache, repo


def test_orbital_integrity_clean(tmp_path) -> None:
    from titan_eye.provenance.integrity import verify_orbital_integrity
    source, cache, repo = _orbital_wired(tmp_path)
    artifact = source.fetch_group("stations")
    repo.insert_snapshot(normalize_tles(artifact))
    report = verify_orbital_integrity(repo, cache)
    assert report.ok is True
    assert report.n_states == 2 and report.n_source_hashes == 1


def test_orbital_integrity_detects_orphan(tmp_path) -> None:
    from titan_eye.provenance.integrity import verify_orbital_integrity
    source, cache, repo = _orbital_wired(tmp_path)
    artifact = source.fetch_group("stations")
    repo.insert_snapshot(normalize_tles(artifact))
    for blob in (tmp_path / "cache" / "blobs").rglob("*.bin"):
        blob.unlink()
    report = verify_orbital_integrity(repo, cache)
    assert report.ok is False
    assert len(report.orphan_source_hashes) == 1
