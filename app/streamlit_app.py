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
    from app.demo_data import demo_payload
except ImportError:  # ejecutado desde dentro de app/
    from cesium_globe import html as globe_html
    from demo_data import demo_payload

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
def _fetch_aerial(bbox):
    from titan_eye.catalog.normalizers.opensky_states import normalize_states
    from titan_eye.ingestion.sources.opensky import OpenSkySource
    from titan_eye.ingestion.transport import UrllibTransport
    from titan_eye.orchestration.globe_payload import aerial_states_to_entries

    src = OpenSkySource(transport=UrllibTransport())
    art = src.fetch_states(bbox=bbox)
    states = normalize_states(art)
    return aerial_states_to_entries(states), {"hash": art.content_hash, "n": len(states),
                                              "note": art.license_note}


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
def _sidebar_controls() -> dict:
    st.sidebar.markdown("### Panel de situación")
    st.sidebar.caption("Activa dominios y pulsa **Actualizar**. Cada uno se "
                       "ingiere de su fuente pública con procedencia por hash.")
    cfg: dict = {}

    cfg["aerial"] = st.sidebar.checkbox("✈ Aéreo · OpenSky (ADS-B)", value=False)
    cfg["aerial_bbox"] = st.sidebar.text_input("bbox aéreo (lat_min,lat_max,lon_min,lon_max)",
                                               value="35,60,-10,40", disabled=not cfg["aerial"])

    cfg["orbital"] = st.sidebar.checkbox("🛰 Orbital · CelesTrak (TLE)", value=False)
    cfg["orbital_group"] = st.sidebar.text_input("GROUP orbital", value="stations",
                                                disabled=not cfg["orbital"])

    cfg["surface"] = st.sidebar.checkbox("🔥 Superficie · eventos + heatmap", value=False)
    cfg["surface_file"] = st.sidebar.file_uploader("Dataset de eventos (JSON)", type=["json"],
                                                  disabled=not cfg["surface"])
    cfg["bandwidth"] = st.sidebar.slider("Bandwidth KDE (km)", 10, 200, 50, 5,
                                        disabled=not cfg["surface"])

    cfg["maritime"] = st.sidebar.checkbox("⚓ Marítimo · buques (AIS)", value=False)
    cfg["maritime_file"] = st.sidebar.file_uploader("Dataset AIS (JSON)", type=["json"],
                                                   disabled=not cfg["maritime"])

    cfg["ballistic"] = st.sidebar.checkbox("🚀 Suborbital · reporte balístico", value=False)
    cfg["ballistic_file"] = st.sidebar.file_uploader("Reporte balístico (JSON)", type=["json"],
                                                    disabled=not cfg["ballistic"])

    cfg["installations"] = st.sidebar.checkbox("🏛 Bases e infraestructura (referencia)", value=False)
    cfg["installations_file"] = st.sidebar.file_uploader("Dataset de instalaciones (JSON)", type=["json"],
                                                        disabled=not cfg["installations"])

    cfg["osint"] = st.sidebar.checkbox("✎ OSINT · noticias/RRSS", value=False)
    cfg["osint_file"] = st.sidebar.file_uploader("Dataset OSINT (JSON)", type=["json"],
                                                disabled=not cfg["osint"])

    cfg["go"] = st.sidebar.button("⟳ Actualizar panel", use_container_width=True, type="primary")
    st.sidebar.caption("Sin selección, el panel muestra datos de **demostración**.")
    return cfg


def _build_combined(cfg) -> tuple[dict, list[str], list[str]]:
    """Ingiere los dominios activos y los combina en un único payload del globo."""
    payload = _empty_payload()
    notes: list[str] = []
    errors: list[str] = []

    if cfg["aerial"]:
        try:
            entries, meta = _fetch_aerial(_parse_bbox(cfg["aerial_bbox"]))
            payload["domains"]["aerial"] = entries
            notes.append(f"Aéreo: {meta['n']} aeronaves · `{meta['hash'][:10]}…` (observed)")
        except Exception as exc:
            errors.append(f"Aéreo: {type(exc).__name__}: {exc}")

    if cfg["orbital"]:
        try:
            entries, meta = _fetch_orbital(cfg["orbital_group"].strip() or "stations")
            payload["domains"]["orbital"] = entries
            notes.append(f"Orbital: {meta['n']} satélites · `{meta['hash'][:10]}…` (observed)")
        except Exception as exc:
            errors.append(f"Orbital: {type(exc).__name__}: {exc}")

    if cfg["maritime"] and cfg["maritime_file"] is not None:
        try:
            entries, meta = _fetch_maritime(cfg["maritime_file"].getvalue())
            payload["domains"]["maritime"] = entries
            notes.append(f"Marítimo: {meta['n']} buques · `{meta['hash'][:10]}…` (observed/AIS)")
        except Exception as exc:
            errors.append(f"Marítimo: {type(exc).__name__}: {exc}")

    if cfg["surface"] and cfg["surface_file"] is not None:
        try:
            entries, hm_pts, meta = _fetch_surface(cfg["surface_file"].getvalue(), float(cfg["bandwidth"]))
            payload["domains"]["surface"] = entries
            payload["heatmap"] = hm_pts
            payload["layers"]["heatmap"] = True
            notes.append(f"Superficie: {meta['n']} eventos · {meta['n_cells']} celdas (asserted)")
        except Exception as exc:
            errors.append(f"Superficie: {type(exc).__name__}: {exc}")

    if cfg["ballistic"] and cfg["ballistic_file"] is not None:
        try:
            entries, meta = _reconstruct_ballistic(cfg["ballistic_file"].getvalue())
            payload["domains"]["suborbital"] = entries
            notes.append(f"Suborbital: reconstruido · banda ±{meta['band_km']:.0f} km (inferred)")
        except Exception as exc:
            errors.append(f"Suborbital: {type(exc).__name__}: {exc}")

    if cfg["installations"] and cfg["installations_file"] is not None:
        try:
            entries, meta = _fetch_installations(cfg["installations_file"].getvalue())
            payload["installations"] = entries
            notes.append(f"Referencia: {meta['n']} instalaciones (asserted, estático)")
        except Exception as exc:
            errors.append(f"Instalaciones: {type(exc).__name__}: {exc}")

    if cfg["osint"] and cfg["osint_file"] is not None:
        try:
            entries, meta = _fetch_osint(cfg["osint_file"].getvalue())
            payload["osint"] = entries
            notes.append(f"OSINT: {meta['n']} ítems (asserted, procedencia · no verificado)")
        except Exception as exc:
            errors.append(f"OSINT: {type(exc).__name__}: {exc}")

    any_data = (any(payload["domains"].values()) or payload["heatmap"]
                or payload.get("installations") or payload.get("osint"))
    if not any_data:
        return demo_payload(), ["Mostrando datos de demostración sintéticos."], errors
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
            st.dataframe([{k: r[k] for k in ("id", "name", "alt_km", "incl", "period_min", "err_km")}
                          for r in d["orbital"]], use_container_width=True, hide_index=True)
    if d["aerial"]:
        with st.expander(f"✈ Aeronaves ({len(d['aerial'])}) · observed", expanded=False):
            st.dataframe([{k: r[k] for k in ("id", "callsign", "lat", "lon", "alt_km", "heading", "age_s")}
                          for r in d["aerial"]], use_container_width=True, hide_index=True)
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
    cfg = _sidebar_controls()
    if cfg["go"] or "te_payload" not in st.session_state:
        payload, notes, errors = _build_combined(cfg)
        st.session_state["te_payload"] = payload
        st.session_state["te_notes"] = notes
        st.session_state["te_errors"] = errors

    payload = st.session_state["te_payload"]
    for e in st.session_state.get("te_errors", []):
        st.error(e)
    notes = st.session_state.get("te_notes", [])
    if notes:
        st.markdown('<div class="te-warn">' + " · ".join(notes) + "</div>", unsafe_allow_html=True)

    payload = _apply_filters(payload)

    _kpis(payload)
    components.html(globe_html(payload, height=820), height=840, scrolling=False)
    st.caption("Epistemología (P9): observed = punto nítido + error nominal · asserted = halo según "
               "resolución de geoloc · inferred = banda de incertidumbre (línea fina prohibida).")
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

    payload = st.session_state.get("te_payload") or demo_payload()
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
