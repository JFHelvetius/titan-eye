"""Tests del dominio suborbital: reconstrucción Kepleriana, banda, globo, persistencia, CLI."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.unit.fixtures_ballistic import BALLISTIC_REPORT, report_payload
from titan_eye.analytics.ballistic.reconstruct import (
    BALLISTIC_MODEL_NAME,
    MODEL_UNCERTAINTY_KM,
    central_angle,
    reconstruct,
)
from titan_eye.catalog.ballistic import BallisticTrajectory
from titan_eye.catalog.ballistic_repo import BallisticTrajectoryRepository
from titan_eye.catalog.normalizers.ballistic_report import normalize_ballistic_report
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.orchestration.cli import run_reconstruct_ballistic
from titan_eye.orchestration.globe_payload import ballistic_trajectories_to_entries

T0 = datetime(2026, 6, 12, 0, 0, 0, tzinfo=UTC)


def _artifact(payload: bytes | None = None) -> RawArtifact:
    return RawArtifact.seal(
        source_id="ballistic.report", domain=Domain.SUBORBITAL,
        request_url="file://x", fetched_at=T0, payload=payload or report_payload(),
        epistemic_label=EpistemicLabel.ASSERTED,
    )


def _report():
    return normalize_ballistic_report(_artifact())


# ── Normalizador (asserted) ──────────────────────────────────────────
def test_report_is_asserted_with_provenance() -> None:
    art = _artifact()
    r = normalize_ballistic_report(art)
    assert r.epistemic_label is EpistemicLabel.ASSERTED
    assert r.content_hash_source == art.content_hash
    assert r.apogee_km == 480.0


def test_report_missing_field_raises() -> None:
    import json
    bad = dict(BALLISTIC_REPORT)
    del bad["apogee_km"]
    with pytest.raises(NormalizationError):
        normalize_ballistic_report(_artifact(json.dumps(bad).encode()))


# ── Física de reconstrucción (inferred) ──────────────────────────────
def test_trajectory_is_inferred() -> None:
    t = reconstruct(_report())
    assert t.epistemic_label is EpistemicLabel.INFERRED
    assert t.model_name == BALLISTIC_MODEL_NAME


def test_apogee_recovered_at_midpoint() -> None:
    # Por construcción, la altitud máxima del arco == apogeo de entrada.
    t = reconstruct(_report(), n_points=100)
    max_alt = max(p[2] for p in t.arc)
    assert max_alt == pytest.approx(480.0, abs=1.0)
    # y está en el punto medio del arco
    apex_idx = max(range(len(t.arc)), key=lambda i: t.arc[i][2])
    assert abs(apex_idx - len(t.arc) // 2) <= 2


def test_range_matches_great_circle() -> None:
    r = _report()
    t = reconstruct(r)
    phi = central_angle(r.launch_lat, r.launch_lon, r.impact_lat, r.impact_lon)
    assert t.range_km == pytest.approx(phi * 6371.0, abs=1.0)


def test_endpoints_at_surface() -> None:
    # El primer y último punto del arco están a altitud ~0 (superficie).
    t = reconstruct(_report(), n_points=80)
    assert t.arc[0][2] == pytest.approx(0.0, abs=2.0)
    assert t.arc[-1][2] == pytest.approx(0.0, abs=2.0)


def test_eccentricity_physical() -> None:
    t = reconstruct(_report())
    assert 0.0 <= t.eccentricity < 1.0


def test_band_is_declared_with_model_floor() -> None:
    # band_km = hypot(apogee_sigma, MODEL_UNCERTAINTY_KM); nunca menor que el suelo.
    t = reconstruct(_report())
    assert t.band_km >= MODEL_UNCERTAINTY_KM
    assert t.impact_dispersion_km >= MODEL_UNCERTAINTY_KM
    assert t.model_uncertainty_km == MODEL_UNCERTAINTY_KM


def test_determinism() -> None:
    a = reconstruct(_report())
    b = reconstruct(_report())
    assert a.model_dump() == b.model_dump()


# ── Globo ────────────────────────────────────────────────────────────
def test_globe_entry_has_band_and_arc() -> None:
    t = reconstruct(_report())
    entry = ballistic_trajectories_to_entries([t])[0]
    assert entry["band_km"] >= MODEL_UNCERTAINTY_KM
    assert len(entry["arc"]) > 10
    assert "launch" in entry and "impact" in entry


# ── Persistencia ─────────────────────────────────────────────────────
def test_repo_roundtrip_idempotent(tmp_path) -> None:
    repo = BallisticTrajectoryRepository(tmp_path)
    t = reconstruct(_report())
    assert repo.insert(t) is True
    assert repo.insert(t) is False  # idempotente por hash
    assert repo.count() == 1
    back = next(repo.iter_all())
    assert isinstance(back, BallisticTrajectory)
    assert back.event_id == "BAL-TEST-1"
    assert back.arc == t.arc


# ── CLI ──────────────────────────────────────────────────────────────
def test_cli_reconstruct_distinguishes_epistemics() -> None:
    summary, traj = run_reconstruct_ballistic(artifact=_artifact())
    assert summary["report_epistemic"] == "asserted"      # P9: el reporte es afirmado
    assert summary["trajectory_epistemic"] == "inferred"  # P9: la trayectoria es inferida
    assert summary["model_name"] == BALLISTIC_MODEL_NAME
    assert summary["band_km"] >= MODEL_UNCERTAINTY_KM
    assert "NO es track de sensor" in summary["note"]
