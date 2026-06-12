"""Tests del caso de situación portable y verificable (ADR-0013)."""

from __future__ import annotations

from datetime import UTC, datetime

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.provenance.situation_case import (
    DetectionRef,
    build_situation_case,
    detections_digest,
    verify_situation_case,
)

T0 = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)


def _ref(domain, source_id, src_hash, ep, payload) -> DetectionRef:
    return DetectionRef(domain=domain, source_id=source_id, content_hash_source=src_hash,
                        epistemic_label=ep, canonical=payload)


OBS = EpistemicLabel.OBSERVED


def _sample_refs() -> list[DetectionRef]:
    return [
        _ref(Domain.AERIAL, "opensky.states", "hashA", OBS, {"icao24": "abc", "lat": 1.0}),
        _ref(Domain.AERIAL, "opensky.states", "hashA", OBS, {"icao24": "def", "lat": 2.0}),
        _ref(Domain.SURFACE, "conflict.events", "hashS",
             EpistemicLabel.ASSERTED, {"event_id": "E1"}),
        _ref(Domain.SUBORBITAL, "ballistic.report", "hashB",
             EpistemicLabel.INFERRED, {"event_id": "BAL"}),
    ]


def _build():
    return build_situation_case(case_id="c1", title="t", created_at=T0, refs=_sample_refs())


# ── Estructura y agrupación ──────────────────────────────────────────
def test_entries_grouped_by_domain_and_source() -> None:
    case = _build()
    # 3 grupos: aéreo (1 snapshot, 2 detecciones), superficie, suborbital
    assert len(case.entries) == 3
    aerial = next(e for e in case.entries if e.domain is Domain.AERIAL)
    assert aerial.n_detections == 2
    assert aerial.content_hash_source == "hashA"


def test_epistemic_labels_preserved() -> None:
    case = _build()
    labels = {e.domain: e.epistemic_label for e in case.entries}
    assert labels[Domain.AERIAL] is EpistemicLabel.OBSERVED
    assert labels[Domain.SURFACE] is EpistemicLabel.ASSERTED
    assert labels[Domain.SUBORBITAL] is EpistemicLabel.INFERRED


# ── Hash determinista e invariante al orden ──────────────────────────
def test_case_hash_deterministic() -> None:
    a = _build()
    b = _build()
    assert a.case_hash == b.case_hash


def test_case_hash_order_independent() -> None:
    refs = _sample_refs()
    case1 = build_situation_case(case_id="c1", title="t", created_at=T0, refs=refs)
    case2 = build_situation_case(case_id="c1", title="t", created_at=T0, refs=list(reversed(refs)))
    assert case1.case_hash == case2.case_hash


def test_digest_order_independent() -> None:
    a = detections_digest([{"x": 1}, {"x": 2}])
    b = detections_digest([{"x": 2}, {"x": 1}])
    assert a == b


def test_case_hash_changes_with_content() -> None:
    case = _build()
    more = [*_sample_refs(),
            _ref(Domain.AERIAL, "opensky.states", "hashA", OBS, {"icao24": "zzz", "lat": 9.0})]
    case2 = build_situation_case(case_id="c1", title="t", created_at=T0, refs=more)
    assert case.case_hash != case2.case_hash


# ── Verificación ─────────────────────────────────────────────────────
def test_verify_clean_case() -> None:
    rep = verify_situation_case(_build())
    assert rep.ok is True
    assert rep.expected_hash == rep.actual_hash
    assert rep.n_entries == 3


def test_verify_detects_tampering() -> None:
    case = _build()
    # Manipula una entrada sin recomputar el case_hash -> debe detectarse.
    tampered = case.model_copy(update={
        "entries": [case.entries[0].model_copy(update={"n_detections": 999}), *case.entries[1:]]
    })
    rep = verify_situation_case(tampered)
    assert rep.ok is False
    assert any("no coincide" in i for i in rep.issues)


def test_roundtrip_json_preserves_hash() -> None:
    from titan_eye.provenance.situation_case import SituationCase
    case = _build()
    restored = SituationCase.model_validate_json(case.model_dump_json())
    assert verify_situation_case(restored).ok is True
    assert restored.case_hash == case.case_hash
