"""Tests del Índice de Tensión (TGTI) y alertas (ADR-0016): transparente, sin profecías."""

from __future__ import annotations

from titan_eye.analytics.intelligence import (
    TGTI_MODEL_NAME,
    AlertThresholds,
    compute_tension_index,
    generate_alerts,
)
from titan_eye.core.epistemics import EpistemicLabel


def _payload(orbital=0, aerial=0, maritime=0, suborbital=0, surface=0, heatmap=0) -> dict:
    mk = lambda n: [{"id": i} for i in range(n)]  # noqa: E731
    return {
        "domains": {"orbital": mk(orbital), "aerial": mk(aerial), "maritime": mk(maritime),
                    "suborbital": mk(suborbital), "surface": mk(surface)},
        "heatmap": mk(heatmap),
    }


# ── Índice ───────────────────────────────────────────────────────────
def test_empty_is_zero() -> None:
    idx = compute_tension_index(_payload())
    assert idx.value == 0.0
    assert all(c.raw_count == 0 for c in idx.components)


def test_value_in_range() -> None:
    idx = compute_tension_index(_payload(aerial=200, maritime=100, surface=50, suborbital=10))
    assert 0.0 <= idx.value <= 100.0


def test_monotonic_in_activity() -> None:
    low = compute_tension_index(_payload(surface=2)).value
    high = compute_tension_index(_payload(surface=20)).value
    assert high > low


def test_breakdown_is_transparent_and_sums() -> None:
    idx = compute_tension_index(_payload(aerial=50, maritime=30, surface=10, suborbital=2))
    total_w = sum(c.weight for c in idx.components)
    recomputed = round(100.0 * sum(c.contribution for c in idx.components) / total_w, 1)
    assert recomputed == idx.value           # el valor ES la suma del desglose
    assert idx.methodology and idx.model_name == TGTI_MODEL_NAME


def test_note_disclaims_threat() -> None:
    idx = compute_tension_index(_payload(surface=5))
    low = idx.note.lower()
    assert "no es predicción" in low and "amenaza" in low and "intención" in low


def test_weakest_epistemic() -> None:
    # Con superficie (asserted) y suborbital (inferred) presentes -> inferred (más débil).
    idx = compute_tension_index(_payload(surface=3, suborbital=1))
    assert idx.weakest_epistemic is EpistemicLabel.INFERRED
    # Solo aéreo (observed) -> observed.
    idx2 = compute_tension_index(_payload(aerial=5))
    assert idx2.weakest_epistemic is EpistemicLabel.OBSERVED


def test_weights_editable() -> None:
    base = compute_tension_index(_payload(aerial=50)).value
    boosted = compute_tension_index(_payload(aerial=50), weights={"aerial": 0.9}).value
    assert boosted > base   # subir el peso del componente presente sube el índice


# ── Alertas ──────────────────────────────────────────────────────────
def test_no_alerts_when_empty() -> None:
    assert generate_alerts(_payload()) == []


def test_alerts_for_present_domains() -> None:
    alerts = generate_alerts(_payload(maritime=5, suborbital=1, surface=3, heatmap=4))
    kinds = {a.kind for a in alerts}
    assert "ballistic" in kinds and "naval_concentration" in kinds and "conflict_events" in kinds


def test_alerts_are_descriptive_not_prophecy() -> None:
    for a in generate_alerts(_payload(surface=2, maritime=4)):
        assert "no es predicción" in a.note.lower()
        # ningún mensaje promete el futuro
        prophecy = ("inminente", "probable", "predicción", "atacará")
        assert not any(w in a.message.lower() for w in prophecy)


def test_naval_threshold() -> None:
    assert generate_alerts(_payload(maritime=2)) == []          # por debajo del umbral (3)
    assert any(a.kind == "naval_concentration"
               for a in generate_alerts(_payload(maritime=3), thresholds=AlertThresholds(naval=3)))
