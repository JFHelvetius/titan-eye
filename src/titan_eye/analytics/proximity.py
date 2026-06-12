"""Proximidad geométrica multidominio (ADR-0014).

Computa qué entidades posicionadas están geométricamente cerca, reportando
distancia horizontal y separación vertical POR SEPARADO, con la incertidumbre
combinada declarada y la etiqueta epistémica más débil heredada.

Honestidad (ADR-0003, No-objetivos de ADR-0000): el resultado NO contiene score
de amenaza, probabilidad de intercepción, clasificación de riesgo ni veredicto de
intención. Una proximidad es un hecho geométrico con error, no un juicio. Es el
paralelo de las conjunciones de Orbital Sentinel: geometría + σ, sin veredicto.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import AnalyticsError

EARTH_RADIUS_KM = 6371.0
MAX_PAIRS_DEFAULT = 50_000
PROXIMITY_NOTE = (
    "Proximidad geométrica con incertidumbre declarada. NO implica intención, "
    "amenaza ni riesgo de intercepción (ADR-0003)."
)
# Confianza relativa de cada etiqueta (mayor = más sólido). La proximidad hereda
# la MÁS DÉBIL de las dos entidades (P9).
_EPISTEMIC_RANK = {
    EpistemicLabel.OBSERVED: 2,
    EpistemicLabel.ASSERTED: 1,
    EpistemicLabel.INFERRED: 0,
}


@dataclass(frozen=True)
class PositionedEntity:
    """Una entidad con posición e incertidumbre declarada, para proximidad."""

    domain: Domain
    entity_id: str
    latitude: float
    longitude: float
    altitude_km: float
    epistemic_label: EpistemicLabel
    position_uncertainty_km: float


@dataclass(frozen=True)
class ProximityEvent:
    """Un par geométricamente próximo. Sin veredicto: solo geometría con error."""

    a_domain: Domain
    a_id: str
    a_epistemic: EpistemicLabel
    b_domain: Domain
    b_id: str
    b_epistemic: EpistemicLabel
    horizontal_distance_km: float
    vertical_separation_km: float
    combined_uncertainty_km: float
    cross_domain: bool
    weakest_epistemic: EpistemicLabel
    note: str = PROXIMITY_NOTE


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _weakest(a: EpistemicLabel, b: EpistemicLabel) -> EpistemicLabel:
    return a if _EPISTEMIC_RANK[a] <= _EPISTEMIC_RANK[b] else b


def find_proximities(
    entities: list[PositionedEntity],
    *,
    horizontal_threshold_km: float,
    vertical_threshold_km: float | None = None,
    same_domain: bool = True,
    max_pairs: int = MAX_PAIRS_DEFAULT,
) -> list[ProximityEvent]:
    """Pares con distancia horizontal <= umbral (y, si se da, vertical <= umbral).

    same_domain=False restringe a pares de dominios DISTINTOS. El resultado se
    ordena por distancia horizontal ascendente. No emite veredictos (ADR-0014)."""
    if horizontal_threshold_km <= 0:
        raise AnalyticsError("horizontal_threshold_km debe ser > 0.")
    n = len(entities)
    if n * (n - 1) // 2 > max_pairs:
        raise AnalyticsError(
            f"Demasiados pares ({n * (n - 1) // 2} > {max_pairs}); acota las entidades."
        )

    out: list[ProximityEvent] = []
    for a, b in itertools.combinations(entities, 2):
        if not same_domain and a.domain is b.domain:
            continue
        horiz = _haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
        if horiz > horizontal_threshold_km:
            continue
        vert = abs(a.altitude_km - b.altitude_km)
        if vertical_threshold_km is not None and vert > vertical_threshold_km:
            continue
        out.append(ProximityEvent(
            a_domain=a.domain, a_id=a.entity_id, a_epistemic=a.epistemic_label,
            b_domain=b.domain, b_id=b.entity_id, b_epistemic=b.epistemic_label,
            horizontal_distance_km=round(horiz, 3),
            vertical_separation_km=round(vert, 3),
            combined_uncertainty_km=round(
                math.hypot(a.position_uncertainty_km, b.position_uncertainty_km), 3),
            cross_domain=a.domain is not b.domain,
            weakest_epistemic=_weakest(a.epistemic_label, b.epistemic_label),
        ))
    out.sort(key=lambda e: e.horizontal_distance_km)
    return out


# Incertidumbre nominal por dominio cuando el payload no la trae explícita (km).
_GEOLOC_UNC_KM = {"exact": 1.5, "city": 12.0, "region": 55.0, "country": 150.0}
_AERIAL_NOMINAL_KM = 0.5  # precisión nominal de posición ADS-B


def entities_from_payload(payload: dict) -> list[PositionedEntity]:
    """Extrae entidades posicionadas del payload del globo para proximidad.

    Representante por detección: aeronave (posición ADS-B), satélite (punto
    subastral), evento (ubicación con radio según geoloc), balístico (impacto
    estimado con su dispersión)."""
    d = payload.get("domains", {})
    out: list[PositionedEntity] = []

    for a in d.get("aerial", []):
        out.append(PositionedEntity(
            Domain.AERIAL, str(a["id"]), a["lat"], a["lon"], a.get("alt_km", 0.0),
            EpistemicLabel.OBSERVED, _AERIAL_NOMINAL_KM))
    for o in d.get("orbital", []):
        out.append(PositionedEntity(
            Domain.ORBITAL, str(o["id"]), o["lat"], o["lon"], o.get("alt_km", 0.0),
            EpistemicLabel.OBSERVED, float(o.get("err_km", 2.0))))
    for e in d.get("surface", []):
        out.append(PositionedEntity(
            Domain.SURFACE, str(e["id"]), e["lat"], e["lon"], 0.0,
            EpistemicLabel.ASSERTED, _GEOLOC_UNC_KM.get(e.get("geoloc_res", "city"), 12.0)))
    for s in d.get("suborbital", []):
        impact = s.get("impact")
        if impact:
            out.append(PositionedEntity(
                Domain.SUBORBITAL, str(s["id"]), impact[1], impact[0], 0.0,
                EpistemicLabel.INFERRED, float(s.get("impact_dispersion_km", 30.0))))
    return out
