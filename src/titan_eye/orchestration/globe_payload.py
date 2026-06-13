"""Traducción de modelos Normalized -> payload de render del globo (ADR-0004).

Función pura que convierte una lista de `AircraftState` en la lista de entradas
del dominio aéreo que el globo (`docs/cesium/index.html`) sabe dibujar. No
inventa nada: las aeronaves sin posición se omiten del render (no se pueden
dibujar honestamente) pero se cuentan aparte para que el usuario lo sepa.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from titan_eye.analytics.propagation.sgp4_propagator import groundtrack, propagate_geodetic
from titan_eye.analytics.surface.heatmap import HeatmapResult
from titan_eye.catalog.aircraft import AircraftState
from titan_eye.catalog.ballistic import BallisticTrajectory
from titan_eye.catalog.installations import Installation
from titan_eye.catalog.maritime import VesselPosition
from titan_eye.catalog.orbital import SGP4_BASELINE_KM, OrbitalElement
from titan_eye.catalog.surface import ConflictEvent

_MS_TO_KT = 1.943_844


def aerial_states_to_entries(states: list[AircraftState]) -> list[dict[str, Any]]:
    """list[AircraftState] -> entradas 'aerial' del payload del globo."""
    out: list[dict[str, Any]] = []
    for s in states:
        if not s.has_position:
            continue
        out.append({
            "id": s.icao24,
            "callsign": s.callsign or s.icao24,
            "lon": s.longitude,
            "lat": s.latitude,
            "alt_km": round(s.altitude_km, 2) if s.altitude_km is not None else 0.0,
            "heading": round(s.true_track_deg, 1) if s.true_track_deg is not None else 0.0,
            "speed_kt": round(s.velocity_ms * _MS_TO_KT, 0) if s.velocity_ms is not None else 0.0,
            "age_s": round(s.last_contact_age_s, 0) if s.last_contact_age_s is not None else 0.0,
            "origin": s.origin_country or "",
            "country": s.origin_country or "",   # eje de filtro (ADR-0018)
            "kind": "",                           # clase de aeronave: requiere ref DB (diferido)
        })
    return out


def orbital_elements_to_entries(
    elements: list[OrbitalElement],
    *,
    at: datetime | None = None,
    track_points: int = 60,
) -> list[dict[str, Any]]:
    """list[OrbitalElement] -> entradas 'orbital' del payload del globo.

    Propaga cada satélite al instante `at` (posición actual) y genera un
    groundtrack de ~un período. Omite los que fallan al propagar (código SGP4 !=0)
    en lugar de dibujar una posición falsa (P2)."""
    at = at or datetime.now(UTC)
    out: list[dict[str, Any]] = []
    for el in elements:
        try:
            now_pt = propagate_geodetic(el, [at])[0]
            if now_pt.sgp4_error_code != 0:
                continue
            period = el.period_min or 95.0
            step = max(period / track_points, 0.5)
            track = [
                [round(p.longitude, 3), round(p.latitude, 3), round(p.altitude_km, 1)]
                for p in groundtrack(el, start=at, span_min=period, step_min=step)
                if p.sgp4_error_code == 0
            ]
        except Exception:
            continue
        # antigüedad del TLE en días -> error declarado creciente (P2)
        age_days = abs(now_pt.minutes_from_epoch) / 1440.0
        err_km = round(SGP4_BASELINE_KM + age_days * SGP4_BASELINE_KM, 1)
        out.append({
            "id": el.norad_cat_id,
            "name": el.object_name or str(el.norad_cat_id),
            "lon": round(now_pt.longitude, 3),
            "lat": round(now_pt.latitude, 3),
            "alt_km": round(now_pt.altitude_km, 1),
            "incl": round(el.inclination_deg, 2),
            "period_min": round(el.period_min, 1),
            "err_km": err_km,
            "owner": el.intl_designator or "",
            "track": track,
            "country": "",   # el TLE no lleva operador/país (diferido: satcat)
            "kind": "",      # clase de satélite: requiere satcat (diferido)
        })
    return out


def orbital_payload(
    elements: list[OrbitalElement], *, at: datetime | None = None,
    layers: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Payload completo del globo con solo el dominio orbital poblado."""
    return {
        "domains": {
            "orbital": orbital_elements_to_entries(elements, at=at),
            "aerial": [], "suborbital": [], "surface": [],
        },
        "heatmap": [],
        "layers": layers or {"orbital": True, "aerial": False, "suborbital": False,
                             "surface": False, "heatmap": False, "range": False},
    }


def ballistic_trajectories_to_entries(
    trajectories: list[BallisticTrajectory],
) -> list[dict[str, Any]]:
    """list[BallisticTrajectory] -> entradas 'suborbital' del payload del globo.

    El globo dibuja el `arc` como tubo/corredor de incertidumbre (ancho ∝ band_km),
    nunca línea fina (ADR-0003/0004). El impacto lleva su elipse de dispersión."""
    out: list[dict[str, Any]] = []
    for t in trajectories:
        out.append({
            "id": t.event_id,
            "name": t.event_id,
            "source": f"{t.model_name} (inferido)",
            "launch": t.launch,
            "impact": t.impact,
            "arc": t.arc,
            "apogee_km": t.apogee_km,
            "range_km": t.range_km,
            "band_km": t.band_km,
            "impact_dispersion_km": t.impact_dispersion_km,
            "country": "",          # país de lanzamiento: solo si el reporte lo aporta (diferido)
            "kind": "ballistic",
        })
    return out


def suborbital_payload(
    trajectories: list[BallisticTrajectory], *, layers: dict[str, bool] | None = None
) -> dict[str, Any]:
    """Payload completo del globo con solo el dominio suborbital poblado."""
    return {
        "domains": {
            "orbital": [], "aerial": [],
            "suborbital": ballistic_trajectories_to_entries(trajectories),
            "surface": [],
        },
        "heatmap": [],
        "layers": layers or {"suborbital": True, "orbital": False, "aerial": False,
                             "surface": False, "heatmap": False, "range": False},
    }


def installations_to_entries(items: list[Installation]) -> list[dict[str, Any]]:
    """list[Installation] -> entradas 'installations' del payload (capa de referencia).

    Geografía pública estática (asserted). El globo las dibuja como referencia; el
    sistema no computa nada operacional con ellas (ADR-0017)."""
    out: list[dict[str, Any]] = []
    for it in items:
        out.append({
            "id": it.installation_id,
            "name": it.name,
            "lon": it.longitude,
            "lat": it.latitude,
            "type": it.installation_type.value,
            "category": it.category.value,        # militar/infra (lo usa el globo para colorear)
            "country": it.country or "",          # eje de filtro (ADR-0018)
            "kind": it.installation_type.value,   # eje de filtro: tipo de instalación
            "source": it.source or "(referencia pública)",
        })
    return out


def installations_payload(
    items: list[Installation], *, layers: dict[str, bool] | None = None
) -> dict[str, Any]:
    """Payload del globo con solo la capa de instalaciones."""
    return {
        "domains": {"orbital": [], "aerial": [], "maritime": [], "suborbital": [], "surface": []},
        "heatmap": [],
        "installations": installations_to_entries(items),
        "layers": layers or {"installations": True, "orbital": False, "aerial": False,
                             "maritime": False, "suborbital": False, "surface": False,
                             "heatmap": False, "range": False},
    }


def vessels_to_entries(vessels: list[VesselPosition]) -> list[dict[str, Any]]:
    """list[VesselPosition] -> entradas 'maritime' del payload del globo.

    AIS autodeclarado (observed con fuerte caveat de spoofing/AIS-off, ADR-0015)."""
    out: list[dict[str, Any]] = []
    for v in vessels:
        out.append({
            "id": v.mmsi,
            "name": v.name or v.mmsi,
            "lon": v.longitude,
            "lat": v.latitude,
            "vessel_type": v.vessel_type.value,
            "flag": v.flag or "",
            "course": round(v.course_deg, 1) if v.course_deg is not None else 0.0,
            "speed_kt": round(v.speed_knots, 1) if v.speed_knots is not None else 0.0,
            "nav_status": v.nav_status or "",
            "age_s": round(v.last_contact_age_s, 0) if v.last_contact_age_s is not None else 0.0,
            "country": v.flag or "",              # eje de filtro: bandera (ADR-0018)
            "kind": v.vessel_type.value,          # clase de buque
        })
    return out


def maritime_payload(
    vessels: list[VesselPosition], *, layers: dict[str, bool] | None = None
) -> dict[str, Any]:
    """Payload completo del globo con solo el dominio marítimo poblado."""
    return {
        "domains": {
            "orbital": [], "aerial": [], "suborbital": [], "surface": [],
            "maritime": vessels_to_entries(vessels),
        },
        "heatmap": [],
        "layers": layers or {"maritime": True, "orbital": False, "aerial": False,
                             "suborbital": False, "surface": False, "heatmap": False,
                             "range": False},
    }


def conflict_events_to_entries(events: list[ConflictEvent]) -> list[dict[str, Any]]:
    """list[ConflictEvent] -> entradas 'surface' del payload del globo.

    El globo dibuja un halo cuyo radio refleja la `geoloc_resolution` declarada
    (ADR-0004): nunca un punto nítido sobre una ubicación aproximada (P2)."""
    out: list[dict[str, Any]] = []
    for e in events:
        out.append({
            "id": e.event_id,
            "name": e.location_name or e.event_id,
            "lon": e.longitude,
            "lat": e.latitude,
            "source": e.source or "(reporte público)",
            "event_type": e.event_type,
            "date": e.event_date.isoformat(),
            "events_count": 1,
            "geoloc_res": e.geoloc_resolution.value,
            "country": e.country or "",           # eje de filtro: país del reporte (ADR-0018)
            "kind": e.event_type or "",           # tipo de evento
        })
    return out


def heatmap_to_points(heatmap: HeatmapResult) -> list[dict[str, Any]]:
    """HeatmapResult -> puntos 'heatmap' del payload (densidad de REPORTES)."""
    return [{"lon": p[0], "lat": p[1], "weight": p[2]} for p in heatmap.points]


def surface_payload(
    events: list[ConflictEvent],
    *,
    heatmap: HeatmapResult | None = None,
    layers: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Payload completo del globo con el dominio superficie (+ heatmap opcional)."""
    return {
        "domains": {
            "orbital": [], "aerial": [], "suborbital": [],
            "surface": conflict_events_to_entries(events),
        },
        "heatmap": heatmap_to_points(heatmap) if heatmap is not None else [],
        "layers": layers or {"surface": True, "heatmap": heatmap is not None,
                             "orbital": False, "aerial": False, "suborbital": False,
                             "range": False},
    }


def aerial_payload(
    states: list[AircraftState], *, layers: dict[str, bool] | None = None
) -> dict[str, Any]:
    """Payload completo del globo con solo el dominio aéreo poblado."""
    return {
        "domains": {
            "orbital": [],
            "aerial": aerial_states_to_entries(states),
            "suborbital": [],
            "surface": [],
        },
        "heatmap": [],
        "layers": layers or {"aerial": True, "orbital": False, "suborbital": False,
                             "surface": False, "heatmap": False, "range": False},
    }
