"""Índice de tensión (TGTI) y alertas de actividad observable (ADR-0016).

El **Titan Tension Index (TGTI, 0-100)** compone conteos de actividad militar
OBSERVABLE (eventos de conflicto reportados, trayectorias balísticas reconstruidas,
aeronaves, buques) con una normalización saturante declarada y pesos declarados.
Cada índice incluye su **desglose completo** (conteo, normalizado, peso,
contribución) y su metodología: no hay número mágico, cualquiera lo reproduce.

Honestidad (ADR-0016, patrón Pc-con-asunciones de Orbital Sentinel ADR-0020):
el índice NO es predicción de conflicto, evaluación de amenaza ni juicio de
intención. Es una composición transparente de actividad ya pública. Las alertas
DESCRIBEN lo observado/reportado, nunca profetizan. Sin targeting (ADR-0000).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from titan_eye.core.epistemics import EpistemicLabel

TGTI_MODEL_NAME = "saturating_weighted_activity_v1"
TGTI_NOTE = (
    "Índice de actividad militar OBSERVABLE reportada (0-100). NO es predicción de "
    "conflicto, evaluación de amenaza ni juicio de intención: compone actividad ya "
    "pública con pesos declarados (ADR-0016). Reproducible y editable."
)

# Componentes del índice: (clave de dominio en el payload, peso, escala de saturación,
# etiqueta epistémica del componente). Pesos y escalas son DATOS DECLARADOS, editables.
_COMPONENTS = [
    ("surface",    "eventos de conflicto",   0.30, 10.0, EpistemicLabel.ASSERTED),
    ("suborbital", "trayectorias balísticas", 0.30,  2.0, EpistemicLabel.INFERRED),
    ("aerial",     "aeronaves",               0.20, 50.0, EpistemicLabel.OBSERVED),
    ("maritime",   "buques",                  0.20, 30.0, EpistemicLabel.OBSERVED),
]
_EPISTEMIC_RANK = {
    EpistemicLabel.OBSERVED: 2, EpistemicLabel.ASSERTED: 1, EpistemicLabel.INFERRED: 0,
}


@dataclass(frozen=True)
class TensionComponent:
    domain: str
    label: str
    raw_count: int
    weight: float
    saturation_scale: float
    normalized: float       # 1 - exp(-count/scale) ∈ [0,1)
    contribution: float     # weight * normalized (en puntos 0-100)
    epistemic_label: EpistemicLabel


@dataclass(frozen=True)
class TensionIndex:
    """TGTI con su desglose completo y su metodología (transparencia total)."""

    value: float            # 0-100
    components: list[TensionComponent]
    weakest_epistemic: EpistemicLabel
    model_name: str = TGTI_MODEL_NAME
    methodology: str = (
        "value = 100·Σ(weight_i·(1−exp(−count_i/scale_i))) / Σ(weight_i). "
        "Normalización saturante por componente; pesos y escalas declarados."
    )
    note: str = TGTI_NOTE


def compute_tension_index(
    payload: dict, *, weights: dict[str, float] | None = None
) -> TensionIndex:
    """Computa el TGTI 0-100 desde el payload del globo, con desglose total."""
    domains = payload.get("domains", {})
    comps: list[TensionComponent] = []
    total_weight = 0.0
    weighted_sum = 0.0
    present_ranks: list[EpistemicLabel] = []

    for dom, label, default_w, scale, ep in _COMPONENTS:
        weight = float(weights[dom]) if weights and dom in weights else default_w
        count = len(domains.get(dom, []))
        normalized = 1.0 - math.exp(-count / scale) if count > 0 else 0.0
        contribution = weight * normalized
        comps.append(TensionComponent(
            domain=dom, label=label, raw_count=count, weight=weight,
            saturation_scale=scale, normalized=round(normalized, 4),
            contribution=round(contribution, 4), epistemic_label=ep,
        ))
        total_weight += weight
        weighted_sum += contribution
        if count > 0:
            present_ranks.append(ep)

    value = round(100.0 * weighted_sum / total_weight, 1) if total_weight > 0 else 0.0
    weakest = (min(present_ranks, key=lambda e: _EPISTEMIC_RANK[e])
               if present_ranks else EpistemicLabel.OBSERVED)
    return TensionIndex(value=value, components=comps, weakest_epistemic=weakest)


# ── Alertas (descriptivas, no profecías) ──────────────────────────────────────
ALERT_NOTE = ("Descriptivo: reporta actividad ya observable/pública. "
              "NO es predicción ni veredicto de amenaza.")


@dataclass(frozen=True)
class Alert:
    kind: str
    message: str
    domain: str
    count: int
    epistemic_label: EpistemicLabel
    note: str = ALERT_NOTE


@dataclass(frozen=True)
class AlertThresholds:
    naval: int = 3
    aerial: int = 10
    surface: int = 1
    heatmap_cells: int = 1


def generate_alerts(payload: dict, *, thresholds: AlertThresholds | None = None) -> list[Alert]:
    """Genera alertas DESCRIPTIVAS desde la situación observable. Sin pronósticos."""
    t = thresholds or AlertThresholds()
    d = payload.get("domains", {})
    out: list[Alert] = []

    n_bal = len(d.get("suborbital", []))
    if n_bal > 0:
        out.append(Alert("ballistic",
                         f"{n_bal} trayectoria(s) balística(s) reconstruida(s) en la situación",
                         "suborbital", n_bal, EpistemicLabel.INFERRED))
    n_nav = len(d.get("maritime", []))
    if n_nav >= t.naval:
        out.append(Alert("naval_concentration",
                         f"Concentración naval: {n_nav} buques en la situación",
                         "maritime", n_nav, EpistemicLabel.OBSERVED))
    n_air = len(d.get("aerial", []))
    if n_air >= t.aerial:
        out.append(Alert("air_activity", f"Actividad aérea elevada: {n_air} aeronaves",
                         "aerial", n_air, EpistemicLabel.OBSERVED))
    n_evt = len(d.get("surface", []))
    if n_evt >= t.surface:
        out.append(Alert("conflict_events", f"{n_evt} evento(s) de conflicto reportado(s)",
                         "surface", n_evt, EpistemicLabel.ASSERTED))
    n_heat = len(payload.get("heatmap", []))
    if n_heat >= t.heatmap_cells:
        out.append(Alert("activity_hotspot",
                         f"Mapa de calor con {n_heat} celda(s) de densidad de reportes",
                         "surface", n_heat, EpistemicLabel.ASSERTED))
    return out
