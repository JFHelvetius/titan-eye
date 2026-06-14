"""Titan Eye — dashboard Streamlit (culminación del proyecto).

Panel de situación multidominio: combina los cuatro dominios (aéreo, orbital,
suborbital, superficie) sobre un único globo táctico Cesium, con KPIs, tablas por
dominio y verificación de procedencia. Es el destino del proyecto, igual que
Orbital Sentinel culmina en su app Streamlit.

Honestidad (ADR-0003): cada panel declara la naturaleza epistémica de su dato
(observed / asserted / inferred) y su incertidumbre. El mapa de calor mide
densidad de eventos REPORTADOS, no intensidad de conflicto.

Ejecutar:
    pip install -e ".[app]"
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

# Bootstrap de path: hace importables `app.*` y `titan_eye` sin instalación
# editable, para que el dashboard arranque en Streamlit Community Cloud (que
# ejecuta app/streamlit_app.py directamente desde el repo público).
_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import streamlit as st
import streamlit.components.v1 as components

try:
    from app.cesium_globe import html as globe_html
except ImportError:  # ejecutado desde dentro de app/
    from cesium_globe import html as globe_html

AMBER = "#d98a2b"


def _css() -> None:
    st.markdown(
        f"""
        <style>
          .stApp {{ background: #080b10; }}
          h1, h2, h3 {{ color: #e6e9ef; letter-spacing: .02em; }}
          .te-tag {{ color: {AMBER}; font-family: 'JetBrains Mono', monospace; font-size: 12px; }}
          .te-warn {{ background: rgba(217,138,43,.10); border: 1px solid rgba(217,138,43,.35);
            border-radius: 8px; padding: 10px 14px; color: #f0d6a8; font-size: 13px; }}
          [data-testid="stMetricValue"] {{ color: {AMBER}; }}
          section[data-testid="stSidebar"] {{ background: #0c1016; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _empty_payload() -> dict:
    return {
        "domains": {"orbital": [], "aerial": [], "maritime": [], "suborbital": [], "surface": []},
        "heatmap": [],
        "installations": [],
        "osint": [],
        "layers": {"orbital": True, "aerial": True, "maritime": True, "suborbital": True,
                   "surface": True, "heatmap": False, "range": False, "installations": True,
                   "osint": True},
    }


def _fetch_osint(raw: bytes):
    from titan_eye.catalog.normalizers.osint import normalize_osint
    from titan_eye.core.domains import Domain
    from titan_eye.core.epistemics import EpistemicLabel
    from titan_eye.ingestion.artifact import RawArtifact
    from titan_eye.orchestration.globe_payload import osint_to_entries

    art = RawArtifact.seal(
        source_id="osint.items", domain=Domain.OSINT, request_url="upload://osint",
        fetched_at=datetime.now(UTC), payload=raw, epistemic_label=EpistemicLabel.ASSERTED,
    )
    items = normalize_osint(art)
    return osint_to_entries(items), {"hash": art.content_hash, "n": len(items)}


def _fetch_installations(raw: bytes):
    from titan_eye.catalog.normalizers.installations import normalize_installations
    from titan_eye.core.domains import Domain
    from titan_eye.core.epistemics import EpistemicLabel
    from titan_eye.ingestion.artifact import RawArtifact
    from titan_eye.orchestration.globe_payload import installations_to_entries

    art = RawArtifact.seal(
        source_id="installations.reference", domain=Domain.REFERENCE,
        request_url="upload://installations", fetched_at=datetime.now(UTC), payload=raw,
        epistemic_label=EpistemicLabel.ASSERTED,
    )
    items = normalize_installations(art)
    return installations_to_entries(items), {"hash": art.content_hash, "n": len(items)}


def _fetch_maritime(raw: bytes):
    from titan_eye.catalog.normalizers.ais import normalize_ais
    from titan_eye.core.domains import Domain
    from titan_eye.core.epistemics import EpistemicLabel
    from titan_eye.ingestion.artifact import RawArtifact
    from titan_eye.orchestration.globe_payload import vessels_to_entries

    art = RawArtifact.seal(
        source_id="ais.vessels", domain=Domain.MARITIME, request_url="upload://ais",
        fetched_at=datetime.now(UTC), payload=raw, epistemic_label=EpistemicLabel.OBSERVED,
    )
    vessels = normalize_ais(art)
    return vessels_to_entries(vessels), {"hash": art.content_hash, "n": len(vessels)}


# ── Fetchers por dominio (cada uno aislado; el fallo de uno no tumba el panel) ──
def _fetch_aerial(bbox, *, military_only: bool = True):
    from titan_eye.analytics.military_filter import military_match
    from titan_eye.catalog.normalizers.opensky_states import normalize_states
    from titan_eye.ingestion.sources.opensky import OpenSkySource
    from titan_eye.ingestion.transport import UrllibTransport
    from titan_eye.orchestration.globe_payload import aerial_states_to_entries

    src = OpenSkySource(transport=UrllibTransport())
    art = src.fetch_states(bbox=bbox)
    states = normalize_states(art)
    n_total = len(states)
    entries = aerial_states_to_entries(states)
    # Clasificación heurística militar (asserted): la posición sigue siendo observed.
    mil = 0
    kept = []
    for e in entries:
        reason = military_match(e.get("callsign"), e.get("id"))
        if reason:
            e["kind"], e["mil"] = "militar", reason
            mil += 1
            kept.append(e)
        elif not military_only:
            kept.append(e)
    return kept, {"hash": art.content_hash, "n": len(kept), "n_total": n_total,
                  "n_mil": mil, "military_only": military_only, "note": art.license_note}


# Grupos CelesTrak militares / de doble uso (operados por fuerzas armadas).
# Se agregan para dar volumen real manteniendo el foco militar.
_MIL_SAT_GROUPS: tuple[str, ...] = (
    "military",   # satélites militares varios
    "gps-ops",    # GPS — operado por la USAF/USSF (doble uso)
    "glo-ops",    # GLONASS — Fuerzas Aeroespaciales rusas
    "beidou",     # BeiDou — China (PLA)
    "galileo",    # Galileo — UE
    "sbas",       # aumentación (WAAS/EGNOS…)
    "radar",      # calibración radar / observación
    "nnss",       # Navy Navigation Satellite System (US Navy)
    "musson",     # navegación militar rusa (Parus/Tsikada)
)

# Misión declarada por el grupo de origen de CelesTrak (clasificación honesta:
# es la categoría que da la propia fuente, NO una inferencia de Titan Eye).
_GROUP_MISSION: dict[str, str] = {
    "military": "Militar (varios)",
    "gps-ops": "Navegación · GPS (USSF)",
    "glo-ops": "Navegación · GLONASS (RU)",
    "beidou": "Navegación · BeiDou (PLA/CN)",
    "galileo": "Navegación · Galileo (UE)",
    "sbas": "Aumentación de navegación (SBAS)",
    "radar": "Radar / vigilancia",
    "nnss": "Navegación · NNSS (US Navy)",
    "musson": "Navegación militar (RU)",
    "molniya": "Comms / alerta temprana — órbita Molniya (RU)",
    "gorizont": "Comunicaciones militares (RU)",
    "raduga": "Comunicaciones militares (RU)",
    "geo": "Geoestacionario (comms/SIGINT)",
    "active": "Catálogo general (activo)",
    "stations": "Estación espacial",
    "visual": "Visible a simple vista",
}


def _orbit_regime(alt_km: float, ecc: float) -> str:
    """Régimen orbital a partir de física pública (no clasificado)."""
    if ecc >= 0.25:
        return "HEO (muy elíptica)"   # p. ej. Molniya: alerta temprana/comms
    if alt_km < 2000:
        return "LEO (baja)"            # recon/ISR, observación
    if alt_km < 30000:
        return "MEO (media)"           # navegación (GPS/GLONASS/Galileo/BeiDou)
    return "GEO (geoestacionaria)"     # comms/alerta temprana/SIGINT


def _fetch_orbital(group):
    from titan_eye.catalog.normalizers.tle import normalize_tles
    from titan_eye.ingestion.sources.celestrak import CelesTrakSource
    from titan_eye.ingestion.transport import UrllibTransport
    from titan_eye.orchestration.globe_payload import orbital_elements_to_entries

    src = CelesTrakSource(transport=UrllibTransport())
    art = src.fetch_group(group)
    elements = normalize_tles(art)
    return orbital_elements_to_entries(elements), {"hash": art.content_hash, "n": len(elements),
                                                   "note": art.license_note}


# Tope de satélites dibujados a la vez (rendimiento del globo) y nº de los más
# recientes a los que se les pinta groundtrack (lo caro de propagar).
_MAX_SATS = 4000
_TRACKS_FOR_FIRST = 120


def _fetch_orbital_multi(groups):
    """Agrega varios grupos CelesTrak en una sola capa orbital, deduplicando por
    NORAD. Resiliente (un grupo caído no tumba la capa) y RÁPIDO: descarga los
    grupos EN PARALELO y solo propaga groundtracks para un puñado; el resto son
    posiciones puntuales."""
    from concurrent.futures import ThreadPoolExecutor

    from titan_eye.catalog.normalizers.tle import normalize_tles
    from titan_eye.ingestion.sources.celestrak import CelesTrakSource
    from titan_eye.ingestion.transport import UrllibTransport
    from titan_eye.orchestration.globe_payload import orbital_elements_to_entries

    # 2 reintentos por grupo; descarga concurrente (máx 4 a la vez para no
    # disparar el rate-limit de CelesTrak) → mucho más rápido que secuencial.
    src = CelesTrakSource(transport=UrllibTransport(retries=2))

    def _fetch_one(g):
        try:
            return src.fetch_group(g), None
        except Exception as exc:  # se reporta arriba; un grupo no tumba la capa
            return None, exc

    seen: set[int] = set()
    elements = []
    norad_group: dict[int, str] = {}   # de qué grupo CelesTrak vino cada satélite
    ok_groups, failed = [], []
    last_err = ""
    with ThreadPoolExecutor(max_workers=min(4, len(groups))) as pool:
        results = list(pool.map(_fetch_one, groups))
    for g, (art, exc) in zip(groups, results, strict=True):
        if exc is not None:
            failed.append(g)
            last_err = f"{type(exc).__name__}: {exc}"
            continue
        try:
            for el in normalize_tles(art):
                if el.norad_cat_id not in seen:
                    seen.add(el.norad_cat_id)
                    elements.append(el)
                    norad_group[el.norad_cat_id] = g
            ok_groups.append(g)
        except Exception as exc:  # parseo fallido de un grupo no tumba la capa
            failed.append(g)
            last_err = f"{type(exc).__name__}: {exc}"

    elements = elements[:_MAX_SATS]
    # Groundtrack solo para los primeros (caro); el resto, posición puntual.
    with_t = orbital_elements_to_entries(elements[:_TRACKS_FOR_FIRST], with_tracks=True)
    no_t = orbital_elements_to_entries(elements[_TRACKS_FOR_FIRST:], with_tracks=False)
    entries = with_t + no_t
    # Clasificación militar honesta: misión = la del grupo de origen; régimen =
    # física pública. Sirven como ejes de filtro (kind) y para el popup del globo.
    by_mission: dict[str, int] = {}
    for e in entries:
        g = norad_group.get(e["id"], "")
        mission = _GROUP_MISSION.get(g, g or "—")
        e["mission"] = mission
        e["src_group"] = g
        e["regime"] = _orbit_regime(e.get("alt_km", 0.0), e.get("ecc", 0.0))
        e["kind"] = mission          # eje de filtro por misión
        by_mission[mission] = by_mission.get(mission, 0) + 1
    meta = {"n": len(entries), "groups_ok": ok_groups, "groups_failed": failed,
            "by_mission": by_mission}
    if not entries:
        # No cachear un resultado vacío: que el siguiente rerun reintente.
        raise RuntimeError(
            "CelesTrak no devolvió satélites en ningún grupo "
            f"({last_err or 'sin detalle'}). Pulsa «Recargar feeds en vivo» en unos segundos.")
    return entries, meta


def _fetch_surface(raw: bytes, bandwidth_km: float):
    from titan_eye.analytics.surface.heatmap import compute_heatmap
    from titan_eye.catalog.normalizers.conflict_events import normalize_conflict_events
    from titan_eye.core.domains import Domain
    from titan_eye.core.epistemics import EpistemicLabel
    from titan_eye.ingestion.artifact import RawArtifact
    from titan_eye.orchestration.globe_payload import (
        conflict_events_to_entries,
        heatmap_to_points,
    )

    art = RawArtifact.seal(
        source_id="conflict.events", domain=Domain.SURFACE, request_url="upload://events",
        fetched_at=datetime.now(UTC), payload=raw,
        epistemic_label=EpistemicLabel.ASSERTED,
    )
    events = normalize_conflict_events(art)
    hm = compute_heatmap(events, bandwidth_km=bandwidth_km)
    return (conflict_events_to_entries(events), heatmap_to_points(hm),
            {"hash": art.content_hash, "n": len(events), "n_cells": len(hm.points)})


def _fetch_gdelt_news(query: str | None = None):
    """Noticias militares/conflicto geolocalizadas EN VIVO desde GDELT (sin clave)."""
    from titan_eye.catalog.normalizers.gdelt_doc import normalize_gdelt_doc
    from titan_eye.ingestion.sources.gdelt import DEFAULT_QUERY, GdeltSource
    from titan_eye.ingestion.transport import UrllibTransport
    from titan_eye.orchestration.globe_payload import osint_to_entries

    src = GdeltSource(transport=UrllibTransport(retries=2))
    art = src.fetch_doc(query=query or DEFAULT_QUERY)
    items = normalize_gdelt_doc(art)
    return osint_to_entries(items), {"hash": art.content_hash, "n": len(items),
                                     "note": art.license_note}


def _reconstruct_ballistic(raw: bytes):
    from titan_eye.analytics.ballistic.reconstruct import reconstruct
    from titan_eye.catalog.normalizers.ballistic_report import normalize_ballistic_report
    from titan_eye.core.domains import Domain
    from titan_eye.core.epistemics import EpistemicLabel
    from titan_eye.ingestion.artifact import RawArtifact
    from titan_eye.orchestration.globe_payload import ballistic_trajectories_to_entries

    art = RawArtifact.seal(
        source_id="ballistic.report", domain=Domain.SUBORBITAL, request_url="upload://report",
        fetched_at=datetime.now(UTC), payload=raw,
        epistemic_label=EpistemicLabel.ASSERTED,
    )
    report = normalize_ballistic_report(art)
    traj = reconstruct(report)
    return ballistic_trajectories_to_entries([traj]), {"hash": art.content_hash,
                                                       "band_km": traj.band_km,
                                                       "range_km": traj.range_km}


# ── Panel de situación ────────────────────────────────────────────────────────
def _sidebar_live_feeds() -> dict:
    """Barra lateral SLIM: solo ajustes finos de los feeds en vivo (secundario)."""
    st.sidebar.markdown("#### Feeds en vivo (avanzado)")
    st.sidebar.caption("El panel ya carga satélites y aeronaves **militares** en vivo. "
                       "Estos ajustes son opcionales.")
    cfg: dict = {}
    cfg["military_only"] = st.sidebar.toggle("Solo militar (oculta el tráfico civil)", value=True,
        help="Activado: solo aeronaves militares (heurística indicativo + ICAO24). "
             "Desactívalo para ver TODO el tráfico con los militares resaltados en rojo.")
    cfg["orbital_group"] = st.sidebar.text_input(
        "Grupos orbitales (CelesTrak)", value="military",
        help="'military' = set militar/doble-uso agregado (GPS, GLONASS, BeiDou, Galileo…). "
             "O escribe grupos separados por comas, p. ej. 'active' o 'stations,visual'.")
    cfg["aerial_bbox"] = st.sidebar.text_input(
        "Área aérea — vacío = GLOBAL, o lat_min,lat_max,lon_min,lon_max", value="",
        help="Por defecto cubre TODO el planeta. Acota con un bbox si quieres una región.")
    cfg["go"] = st.sidebar.button("⟳ Recargar feeds en vivo", use_container_width=True)
    return cfg


def _upload_panel() -> dict:
    """Acción PRINCIPAL del panel: subir tus propios datasets (foco del usuario)."""
    up: dict = {}
    with st.expander("📤 **Sube tu dataset** — añade tus capas al globo (JSON)", expanded=True):
        st.caption("Arrastra un JSON por dominio. Cada dato se sella con su **hash de "
                   "procedencia** (ADR-0005) y su etiqueta epistémica (P9). Formatos en "
                   "`docs/sources.md`. Lo que subas se combina con los feeds en vivo.")
        c1, c2, c3 = st.columns(3)
        with c1:
            up["maritime_file"] = st.file_uploader("⚓ Buques · AIS", type=["json"], key="up_mar")
            up["surface_file"] = st.file_uploader("🔥 Eventos de conflicto", type=["json"], key="up_srf")
        with c2:
            up["ballistic_file"] = st.file_uploader("🚀 Reporte balístico", type=["json"], key="up_bal")
            up["installations_file"] = st.file_uploader("🏛 Bases e infraestructura", type=["json"], key="up_inst")
        with c3:
            up["osint_file"] = st.file_uploader("✎ OSINT noticias/RRSS", type=["json"], key="up_osint")
            up["bandwidth"] = st.slider("Bandwidth KDE heatmap (km)", 10, 200, 50, 5)
    return up


def _build_combined(live: dict, up: dict) -> tuple[dict, list[str], list[str]]:
    """Feeds en vivo (orbital+aéreo militar) + cualquier dataset subido por el usuario."""
    payload, notes, errors = _default_payload(
        orbital_group=(live.get("orbital_group") or "military").strip(),
        aerial_bbox=_parse_bbox(live.get("aerial_bbox")),
        military_only=live.get("military_only", True),
    )

    if up.get("maritime_file") is not None:
        try:
            entries, meta = _fetch_maritime(up["maritime_file"].getvalue())
            payload["domains"]["maritime"] = entries
            notes.append(f"⚓ Tu dataset: {meta['n']} buques · `{meta['hash'][:10]}…` (observed/AIS)")
        except Exception as exc:
            errors.append(f"Marítimo: {type(exc).__name__}: {exc}")

    if up.get("surface_file") is not None:
        try:
            entries, hm_pts, meta = _fetch_surface(up["surface_file"].getvalue(), float(up["bandwidth"]))
            payload["domains"]["surface"] = entries
            payload["heatmap"] = hm_pts
            payload["layers"]["heatmap"] = True
            notes.append(f"🔥 Tu dataset: {meta['n']} eventos · {meta['n_cells']} celdas (asserted)")
        except Exception as exc:
            errors.append(f"Superficie: {type(exc).__name__}: {exc}")

    if up.get("ballistic_file") is not None:
        try:
            entries, meta = _reconstruct_ballistic(up["ballistic_file"].getvalue())
            payload["domains"]["suborbital"] = entries
            notes.append(f"🚀 Tu reporte: reconstruido · banda ±{meta['band_km']:.0f} km (inferred)")
        except Exception as exc:
            errors.append(f"Suborbital: {type(exc).__name__}: {exc}")

    if up.get("installations_file") is not None:
        try:
            entries, meta = _fetch_installations(up["installations_file"].getvalue())
            payload["installations"] = entries
            notes.append(f"🏛 Tu dataset: {meta['n']} instalaciones (asserted, estático)")
        except Exception as exc:
            errors.append(f"Instalaciones: {type(exc).__name__}: {exc}")

    if up.get("osint_file") is not None:
        try:
            entries, meta = _fetch_osint(up["osint_file"].getvalue())
            payload["osint"] = (payload.get("osint") or []) + entries  # se suma a GDELT
            notes.append(f"✎ Tu dataset: {meta['n']} ítems OSINT (asserted · no verificado)")
        except Exception as exc:
            errors.append(f"OSINT: {type(exc).__name__}: {exc}")

    return payload, notes, errors


# Área aérea por defecto: GLOBAL (None → OpenSky devuelve todos los estados del
# mundo). El foco militar lo da el filtro, no la geografía.
_DEFAULT_AERIAL_BBOX = None


@st.cache_data(ttl=600, show_spinner=False)
def _cached_orbital(group: str):
    """Satélites en vivo (CelesTrak) cacheados 10 min (no re-llama en cada rerun)."""
    return _fetch_orbital(group)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_orbital_multi(groups: tuple):
    """Capa orbital agregada de varios grupos militares (cacheada 10 min)."""
    return _fetch_orbital_multi(groups)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_aerial(bbox: tuple, military_only: bool = True):
    """Aeronaves en vivo (OpenSky/ADS-B) cacheadas 2 min (límite de la API pública)."""
    return _fetch_aerial(bbox, military_only=military_only)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_gdelt_news(query: str):
    """Noticias geolocalizadas en vivo (GDELT) cacheadas 5 min."""
    return _fetch_gdelt_news(query)


def _resolve_orbital_groups(spec: str) -> tuple[str, ...]:
    """'military' → el set militar agregado; lista separada por comas → esos; uno → ese."""
    spec = (spec or "military").strip()
    if spec.lower() in ("military", "mil", ""):
        return _MIL_SAT_GROUPS
    return tuple(g.strip() for g in spec.split(",") if g.strip())


def _default_payload(
    *, orbital_group: str = "military", aerial_bbox: tuple | None = None,
    military_only: bool = True,
) -> tuple[dict, list[str], list[str]]:
    """Vista base con SOLO datos reales EN VIVO de fuentes públicas sin clave.

    - Orbital: agrega varios grupos militares/de doble uso de CelesTrak (GPS,
      GLONASS, BeiDou, Galileo, military…) → SGP4. Mucho volumen, foco militar.
    - Aéreo: TODO el tráfico OpenSky (ADS-B) del área, con las aeronaves militares
      resaltadas por heurística pública. `military_only` lo reduce a solo militares.
    Los dominios que requieren clave de API (AIS marítimo) o un dataset público
    se añaden subiéndolos."""
    payload = _empty_payload()
    notes: list[str] = []
    errors: list[str] = []
    bbox = aerial_bbox or _DEFAULT_AERIAL_BBOX

    groups = _resolve_orbital_groups(orbital_group)
    try:
        entries, meta = _cached_orbital_multi(groups)
        if entries:
            payload["domains"]["orbital"] = entries
            note = (f"🛰 Orbital EN VIVO · CelesTrak — **{meta['n']} satélites** "
                    f"militares/doble-uso de {len(meta['groups_ok'])} grupos (observed)")
            bm = meta.get("by_mission") or {}
            if bm:
                top = sorted(bm.items(), key=lambda kv: -kv[1])[:4]
                note += " · " + ", ".join(f"{m.split(' · ')[0].split(' (')[0]}: {n}" for m, n in top)
            if meta["groups_failed"]:
                note += f" · grupos no disponibles ahora: {', '.join(meta['groups_failed'])}"
            notes.append(note)
        else:
            errors.append("Orbital: ningún grupo respondió (red CelesTrak caída ahora mismo). "
                          "Se reintenta solo al recargar.")
    except Exception as exc:
        errors.append(f"Orbital en vivo no disponible ahora: {type(exc).__name__}: {exc}")

    try:
        entries, meta = _cached_aerial(bbox, military_only)
        payload["domains"]["aerial"] = entries
        scope = "en el mundo" if not bbox else "en el área"
        if military_only:
            notes.append(f"✈ Aéreo EN VIVO · OpenSky/ADS-B — {meta['n_mil']} aeronaves "
                         f"**militares** (heurística) de {meta['n_total']} {scope} (observed)")
            if not entries:
                notes.append("Ahora mismo no hay vuelos militares detectables; desactiva *Solo "
                             "militar* para ver todo el tráfico. Ausencia ≠ inexistencia (los "
                             "militares apagan el ADS-B).")
        else:
            notes.append(f"✈ Aéreo EN VIVO · OpenSky/ADS-B — **{meta['n']} aeronaves** "
                         f"({meta['n_mil']} **militares** resaltadas, heurística) (observed)")
    except Exception as exc:
        errors.append(f"Aéreo en vivo no disponible ahora: {type(exc).__name__}: {exc}")

    try:
        from titan_eye.ingestion.sources.gdelt import DEFAULT_QUERY

        entries, meta = _cached_gdelt_news(DEFAULT_QUERY)
        if entries:
            payload["osint"] = entries
            payload["layers"]["osint"] = True
            notes.append(f"✎ Noticias EN VIVO · GDELT — **{meta['n']} artículos** de "
                         f"conflicto/militar (24h, asserted · no verificado)")
    except Exception as exc:
        errors.append(f"Noticias GDELT no disponibles ahora: {type(exc).__name__}: {exc}")

    return payload, notes, errors


def _parse_bbox(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    a, b, c, d = (float(x) for x in raw.split(","))
    return (a, b, c, d)


def _kpis(payload: dict) -> None:
    d = payload["domains"]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Satélites", len(d["orbital"]))
    c2.metric("Aeronaves", len(d["aerial"]))
    c3.metric("Buques", len(d.get("maritime", [])))
    c4.metric("Trayectorias", len(d["suborbital"]))
    c5.metric("Eventos", len(d["surface"]))
    c6.metric("Celdas calor", len(payload["heatmap"]))


def _domain_tables(payload: dict) -> None:
    d = payload["domains"]
    if d["orbital"]:
        with st.expander(f"🛰 Satélites ({len(d['orbital'])}) · observed", expanded=False):
            st.dataframe([{**{k: r[k] for k in ("id", "name")},
                           "misión": r.get("mission", ""), "régimen": r.get("regime", ""),
                           **{k: r[k] for k in ("alt_km", "incl", "period_min", "err_km")}}
                          for r in d["orbital"]], use_container_width=True, hide_index=True)
            st.caption("**Misión** = categoría del grupo CelesTrak de origen (clasificación de la "
                       "fuente, no de Titan Eye). **Régimen** orbital derivado de física pública. "
                       "Filtra por misión arriba (p. ej. solo navegación o solo militar).")
    if d["aerial"]:
        n_mil = sum(1 for r in d["aerial"] if r.get("mil"))
        with st.expander(f"✈ Aeronaves ({len(d['aerial'])}, {n_mil} militares) · observed",
                         expanded=False):
            st.dataframe([{**{k: r[k] for k in ("id", "callsign", "lat", "lon", "alt_km", "heading", "age_s")},
                           "militar (heurística)": r.get("mil", "")}
                          for r in d["aerial"]], use_container_width=True, hide_index=True)
            st.caption("La etiqueta «militar» es una **heurística pública** (prefijo de indicativo "
                       "+ rango ICAO24), AFIRMADA y no verificada; la **posición** sí es observed. "
                       "Falsos +/− posibles. Ver `docs/sources.md`.")
    if d.get("maritime"):
        with st.expander(f"⚓ Buques ({len(d['maritime'])}) · observed (AIS)", expanded=False):
            st.dataframe([{k: r[k] for k in ("id", "name", "vessel_type", "lat", "lon", "speed_kt", "age_s")}
                          for r in d["maritime"]], use_container_width=True, hide_index=True)
            st.caption("AIS **autodeclarado** y falsificable; los buques de guerra apagan o falsean "
                       "el AIS, y los submarinos sumergidos no transmiten (ADR-0015). Ausencia ≠ inexistencia.")
    if d["suborbital"]:
        with st.expander(f"🚀 Trayectorias balísticas ({len(d['suborbital'])}) · inferred", expanded=True):
            st.dataframe([{k: r[k] for k in ("id", "apogee_km", "range_km", "band_km", "impact_dispersion_km")}
                          for r in d["suborbital"]], use_container_width=True, hide_index=True)
            st.caption("RECONSTRUCCIÓN desde reporte público (asserted → inferred). NO es track de sensor.")
    if d["surface"]:
        with st.expander(f"🔥 Eventos de conflicto ({len(d['surface'])}) · asserted", expanded=False):
            st.dataframe([{k: r[k] for k in ("id", "name", "lat", "lon", "event_type", "date", "geoloc_res")}
                          for r in d["surface"]], use_container_width=True, hide_index=True)
            st.caption("AFIRMADOS por terceros. Halo en el globo = resolución de geolocalización. "
                       "Mapa de calor = densidad de eventos REPORTADOS, no intensidad (ADR-0003).")
    if payload.get("installations"):
        inst = payload["installations"]
        with st.expander(f"🏛 Bases e infraestructura ({len(inst)}) · referencia (asserted)", expanded=False):
            st.dataframe([{k: r[k] for k in ("id", "name", "type", "category", "country", "source")}
                          for r in inst], use_container_width=True, hide_index=True)
            st.caption("Geografía PÚBLICA estática (OSM/Wikipedia/FAS). Puede estar desactualizada. "
                       "Solo display: sin proximidad-a-objetivo ni cómputo operacional (ADR-0017).")
    if payload.get("osint"):
        osint = payload["osint"]
        with st.expander(f"✎ OSINT noticias/RRSS ({len(osint)}) · asserted", expanded=False):
            st.dataframe([{k: r[k] for k in ("id", "name", "source", "source_tier",
                                             "country", "published_at")}
                          for r in osint], use_container_width=True, hide_index=True)
            st.caption("AFIRMACIONES de fuentes con procedencia. Titan Eye **no verifica veracidad** "
                       "ni puntúa credibilidad; el tier describe el tipo de fuente (ADR-0020).")


def _page_situation() -> None:
    live = _sidebar_live_feeds()
    up = _upload_panel()
    # Firma de estado: cualquier cambio en feeds en vivo (incl. toggle militar) o en
    # los datasets subidos dispara una reconstrucción automática (sin pulsar botón).
    sig = (
        ("mil", live["military_only"]), ("grp", live["orbital_group"]), ("bbox", live["aerial_bbox"]),
        *((k, up[k].name, up[k].size) for k in
          ("maritime_file", "surface_file", "ballistic_file", "installations_file", "osint_file")
          if up.get(k) is not None),
        ("bw", up.get("bandwidth")),
    )
    changed = st.session_state.get("te_sig") != sig
    if live["go"] or changed or "te_payload" not in st.session_state:
        with st.spinner("Ingiriendo feeds en vivo y datasets…"):
            payload, notes, errors = _build_combined(live, up)
        st.session_state["te_payload"] = payload
        st.session_state["te_notes"] = notes
        st.session_state["te_errors"] = errors
        st.session_state["te_sig"] = sig

    payload = st.session_state["te_payload"]
    for e in st.session_state.get("te_errors", []):
        st.error(e)
    notes = st.session_state.get("te_notes", [])
    if notes:
        st.markdown('<div class="te-warn">' + " · ".join(notes) + "</div>", unsafe_allow_html=True)

    payload = _apply_filters(payload)

    _kpis(payload)
    components.html(globe_html(payload, height=820), height=840, scrolling=False)
    st.caption("Iconos: ✈ avión (orientado al rumbo) · ⚓ buque (orientado al rumbo) · 🛰 satélite · "
               "🚀 misil. Epistemología (P9): observed = icono nítido + error nominal · asserted = halo "
               "según resolución de geoloc · inferred = banda de incertidumbre (línea fina prohibida).")
    _domain_tables(payload)
    _proximity_panel(payload)


def _apply_filters(payload: dict) -> dict:
    """Filtro de vista por país y tipo (ADR-0018), transversal a todos los dominios."""
    from titan_eye.analytics.filtering import (
        available_countries,
        available_kinds,
        filter_payload,
    )

    countries = available_countries(payload)
    kinds = available_kinds(payload)
    if not countries and not kinds:
        return payload

    c1, c2 = st.columns(2)
    with c1:
        sel_c = st.multiselect("Filtrar por país / bandera", countries, default=[])
    with c2:
        sel_k = st.multiselect("Filtrar por tipo / clase", kinds, default=[])
    if not sel_c and not sel_k:
        return payload
    filtered = filter_payload(payload, countries=sel_c or None, kinds=sel_k or None)
    st.caption("Filtro de vista (ADR-0018): selecciona lo observado por país/tipo declarado. "
               "No atribuye bando ni amenaza; país/tipo vacío = el dato no lo soporta.")
    return filtered


def _proximity_panel(payload: dict) -> None:
    """Proximidad geométrica multidominio (ADR-0014): geometría con error, sin veredictos."""
    from titan_eye.analytics.proximity import entities_from_payload, find_proximities

    ents = entities_from_payload(payload)
    if len(ents) < 2:
        return
    with st.expander("📐 Proximidad geométrica multidominio", expanded=False):
        thr = st.slider("Umbral de distancia horizontal (km)", 5, 500, 100, 5)
        try:
            evs = find_proximities(ents, horizontal_threshold_km=float(thr))
        except Exception as exc:
            st.error(f"{type(exc).__name__}: {exc}")
            return
        if not evs:
            st.caption("Sin pares por debajo del umbral.")
            return
        st.dataframe([{
            "A": f"{e.a_domain.value}:{e.a_id}", "B": f"{e.b_domain.value}:{e.b_id}",
            "horiz_km": e.horizontal_distance_km, "vert_km": e.vertical_separation_km,
            "± incert_km": e.combined_uncertainty_km, "epistemología": e.weakest_epistemic.value,
        } for e in evs[:200]], use_container_width=True, hide_index=True)
        st.caption("Distancia horizontal y separación vertical **por separado**, con incertidumbre "
                   "combinada. Es **geometría con error, no un veredicto**: no implica intención, "
                   "amenaza ni riesgo de intercepción (ADR-0003/0014).")


def _page_verify() -> None:
    st.subheader("Verificación de procedencia")
    st.markdown(
        "Cada detección se ata por hash a los bytes públicos que la produjeron (ADR-0005). "
        "Los verificadores comprueban dos invariantes por dominio: **I1** referencial "
        "(todo Normalized tiene su Raw en la cache) y **I2** reproducibilidad "
        "(re-normalizar el Raw reproduce las mismas filas)."
    )
    root = st.text_input("Raíz de datos local (la generada con `--persist`)", value="./data")
    domain = st.selectbox("Dominio", ["aerial", "orbital", "surface", "maritime"])
    if st.button("Verificar integridad"):
        try:
            from pathlib import Path

            from titan_eye.ingestion.cache import FetchCache
            cache = FetchCache(Path(root) / "cache")
            if domain == "aerial":
                from titan_eye.catalog.aircraft_states_repo import AircraftStatesRepository
                from titan_eye.provenance.integrity import verify_aerial_integrity
                rep = verify_aerial_integrity(
                    AircraftStatesRepository(Path(root) / "normalized" / "aerial"), cache)
            elif domain == "orbital":
                from titan_eye.catalog.orbital_elements_repo import OrbitalElementsRepository
                from titan_eye.provenance.integrity import verify_orbital_integrity
                rep = verify_orbital_integrity(
                    OrbitalElementsRepository(Path(root) / "normalized" / "orbital"), cache)
            elif domain == "surface":
                from titan_eye.catalog.conflict_events_repo import ConflictEventsRepository
                from titan_eye.provenance.integrity import verify_surface_integrity
                rep = verify_surface_integrity(
                    ConflictEventsRepository(Path(root) / "normalized" / "surface"), cache)
            else:
                from titan_eye.catalog.vessel_positions_repo import VesselPositionsRepository
                from titan_eye.provenance.integrity import verify_maritime_integrity
                rep = verify_maritime_integrity(
                    VesselPositionsRepository(Path(root) / "normalized" / "maritime"), cache)
            (st.success if rep.ok else st.error)(
                f"{'✓ Íntegro' if rep.ok else '✗ Violación'} · {rep.n_states} filas · "
                f"{rep.n_source_hashes} snapshots · huérfanos: {len(rep.orphan_source_hashes)} · "
                f"mismatches: {len(rep.reproducibility_mismatches)}"
            )
        except Exception as exc:
            st.error(f"{type(exc).__name__}: {exc}")


def _page_intel() -> None:
    from titan_eye.analytics.intelligence import compute_tension_index, generate_alerts

    payload = st.session_state.get("te_payload")
    if payload is None:
        payload, _, _ = _default_payload()
    idx = compute_tension_index(payload)
    alerts = generate_alerts(payload)

    st.subheader("Titan Tension Index (TGTI)")
    c1, c2 = st.columns([1, 3])
    with c1:
        st.metric("TGTI", f"{idx.value:.0f} / 100")
    with c2:
        st.progress(min(1.0, idx.value / 100.0))
    st.markdown('<div class="te-warn">' + idx.note + "</div>", unsafe_allow_html=True)

    st.markdown("**Desglose** (transparente y reproducible · ADR-0016)")
    st.dataframe([{
        "componente": c.label, "conteo": c.raw_count, "peso": c.weight,
        "escala": c.saturation_scale, "normalizado": c.normalized,
        "contribución": c.contribution, "epistemología": c.epistemic_label.value,
    } for c in idx.components], use_container_width=True, hide_index=True)
    st.caption(f"Metodología: {idx.methodology}  ·  epistemología del índice: "
               f"**{idx.weakest_epistemic.value}** (la más débil de sus componentes).")

    st.subheader("Alertas")
    if not alerts:
        st.caption("Sin actividad por encima de los umbrales en la situación actual.")
    else:
        st.dataframe([{
            "tipo": a.kind, "mensaje": a.message, "dominio": a.domain,
            "conteo": a.count, "epistemología": a.epistemic_label.value,
        } for a in alerts], use_container_width=True, hide_index=True)
        st.caption("Las alertas **describen actividad ya observable/reportada**, no predicen "
                   "ni emiten veredictos de amenaza (ADR-0016).")


def _page_timeline() -> None:
    from titan_eye.analytics.timeline import (
        available_days,
        daily_activity,
        payload_for_day,
    )
    from titan_eye.orchestration.cli import load_timeline_items

    st.subheader("Línea temporal histórica")
    st.markdown(
        "Reproduce la situación de un día desde el store **append-only** (ADR-0019). "
        "Muestra lo observado/reportado y persistido ese día; los días sin datos "
        "están vacíos porque **no hubo captura**, no porque no hubiera actividad."
    )
    root = st.text_input("Raíz de datos local (la generada con `--persist`)",
                         value="./data", key="tl_root")
    try:
        items = load_timeline_items(root)
    except Exception as exc:
        st.error(f"{type(exc).__name__}: {exc}")
        return
    days = available_days(items)
    if not days:
        st.info("No hay datos persistidos con fecha en este data-root "
                "(superficie/aéreo/marítimo). Ingiere con `--persist` primero.")
        return

    activity = daily_activity(items)
    chart = {d.date: d.counts for d in activity}
    domains = sorted({k for c in chart.values() for k in c})
    st.markdown("**Evolución día a día** (conteo por dominio)")
    st.bar_chart({dom: [chart[day].get(dom, 0) for day in days] for dom in domains})
    st.caption("Eje X: días con datos · " + " · ".join(days[:8]) + ("…" if len(days) > 8 else ""))

    sel = st.select_slider("Día a reproducir", options=days, value=days[-1])
    payload = payload_for_day(items, sel)
    n = sum(len(v) for v in payload["domains"].values())
    st.success(f"Replay {sel}: {n} detecciones persistidas ese día.")
    components.html(globe_html(payload, height=700), height=720, scrolling=False)


def _page_countries() -> None:
    from titan_eye.catalog.normalizers.country import normalize_countries
    from titan_eye.core.domains import Domain
    from titan_eye.core.epistemics import EpistemicLabel
    from titan_eye.ingestion.artifact import RawArtifact

    st.subheader("Países & Alianzas")
    st.markdown(
        "Cifras de fuentes **públicas** (SIPRI / IISS Military Balance / oficiales) con su "
        "año y fuente. Son **estimaciones**, no datos de Titan Eye; **no** hay ranking de "
        "poder ni 'amenazas activas' (ADR-0021). El lector compara con la procedencia dada."
    )
    up = st.file_uploader("Dataset de fichas país (JSON: lista o {countries:[...]})",
                          type=["json"], key="countries_up")
    if up is None:
        st.info("Sube un dataset de fichas país para explorarlas.")
        return
    try:
        art = RawArtifact.seal(
            source_id="countries.reference", domain=Domain.REFERENCE,
            request_url="upload://countries", fetched_at=datetime.now(UTC),
            payload=up.getvalue(), epistemic_label=EpistemicLabel.ASSERTED)
        profiles = normalize_countries(art)
    except Exception as exc:
        st.error(f"{type(exc).__name__}: {exc}")
        return
    if not profiles:
        st.warning("El dataset no tiene fichas.")
        return

    by_name = {p.country: p for p in profiles}
    sel = st.selectbox("País", sorted(by_name))
    p = by_name[sel]
    c1, c2, c3 = st.columns(3)
    budget = f"${p.military_budget_usd:,.0f}" if p.military_budget_usd is not None else "—"
    c1.metric(f"Presupuesto militar{f' ({p.budget_year})' if p.budget_year else ''}", budget)
    c2.metric("Personal activo", f"{p.active_personnel:,}" if p.active_personnel is not None else "—")
    c3.metric("Reservistas", f"{p.reserve_personnel:,}" if p.reserve_personnel is not None else "—")
    st.write(f"**Región:** {p.region or '—'}  ·  **Alianzas:** "
             + (", ".join(p.alliances) if p.alliances else "—"))
    if p.source:
        st.caption(f"Fuente: {p.source} {p.source_url}".strip())

    # Agrupación por alianza (declarada por el dato, no inferida).
    alliances: dict[str, list[str]] = {}
    for prof in profiles:
        for a in prof.alliances:
            alliances.setdefault(a, []).append(prof.country)
    if alliances:
        st.markdown("**Alianzas y bloques** (pertenencia declarada por el dato)")
        st.dataframe([{"alianza": a, "miembros": ", ".join(sorted(m)), "n": len(m)}
                      for a, m in sorted(alliances.items())],
                     use_container_width=True, hide_index=True)


def _page_about() -> None:
    st.subheader("Qué es Titan Eye")
    st.markdown(
        """
Registro de detección verificable de eventos **orbitales, suborbitales, aéreos y de
superficie** de relevancia militar, con **datos públicos**, **procedencia por hash**
e **incertidumbre declarada**.

**No** es un sistema de targeting. **No** clasifica intención ni amenaza. Produce
geometría con error, conteos con procedencia y visualización honesta.

| Dominio | Fuente pública | Naturaleza (P9) |
|---|---|---|
| Aéreo | OpenSky (ADS-B) | `observed` |
| Orbital | CelesTrak (TLE) → SGP4 | `observed` |
| Suborbital | Reportes públicos → reconstrucción Kepleriana | `asserted → inferred` |
| Superficie | ACLED/GDELT → KDE | `asserted` |

El mapa de calor mide densidad de eventos **reportados**, no intensidad de conflicto.
Ver `docs/adr/0000-long-term-vision.md` y `docs/adr/0003-uncertainty-and-no-intent.md`.
        """
    )


def main() -> None:
    st.set_page_config(page_title="Titan Eye · Panel de situación", page_icon="🛰",
                       layout="wide", initial_sidebar_state="expanded")
    _css()
    st.markdown("# 🛰 Titan Eye <span class='te-tag'>· panel de situación multidominio</span>",
                unsafe_allow_html=True)
    tab_sit, tab_intel, tab_time, tab_country, tab_verify, tab_about = st.tabs(
        ["Panel de situación", "Índice & Alertas", "Línea temporal",
         "Países & Alianzas", "Verificación", "Acerca de"])
    with tab_sit:
        _page_situation()
    with tab_intel:
        _page_intel()
    with tab_time:
        _page_timeline()
    with tab_country:
        _page_countries()
    with tab_verify:
        _page_verify()
    with tab_about:
        _page_about()


if __name__ == "__main__":
    main()
