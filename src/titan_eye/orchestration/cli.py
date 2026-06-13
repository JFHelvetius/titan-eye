"""CLI de Titan Eye.

`argparse` puro, cero dependencias nuevas (P3). Output JSON a stdout; errores
tipados como `{"error": kind, "message": ...}` a stderr con código de salida 1.

Comandos (Fase 1):
    titan-eye ingest aerial [--bbox lamin,lamax,lomin,lomax] [--cache DIR]

El núcleo testeable (`run_ingest_aerial`) se separa del wiring de red para poder
inyectar una fuente fake en tests, sin tocar Internet.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import UTC
from typing import Any

from titan_eye.catalog.normalizers.opensky_states import (
    NORMALIZER_VERSION,
    normalize_states,
)
from titan_eye.core.errors import TitanEyeError
from titan_eye.ingestion.sources.opensky import OpenSkySource

_VERSION = "0.0.1"


def run_ingest_aerial(
    *,
    source: OpenSkySource,
    bbox: tuple[float, float, float, float] | None = None,
    sample: int = 5,
) -> dict[str, Any]:
    """Ingesta + normalización del dominio aéreo. Devuelve un resumen serializable.

    No toca red por sí mismo: usa la `source` inyectada (real o fake)."""
    artifact = source.fetch_states(bbox=bbox)
    states = normalize_states(artifact)
    with_pos = [s for s in states if s.has_position]
    return {
        "domain": "aerial",
        "source_id": artifact.source_id,
        "content_hash": artifact.content_hash,
        "fetched_at": artifact.fetched_at.isoformat(),
        "epistemic_label": artifact.epistemic_label.value,
        "license_note": artifact.license_note,
        "normalizer_version": NORMALIZER_VERSION,
        "n_states": len(states),
        "n_with_position": len(with_pos),
        "sample": [
            {
                "icao24": s.icao24,
                "callsign": s.callsign,
                "lat": s.latitude,
                "lon": s.longitude,
                "altitude_km": s.altitude_km,
                "position_source": s.position_source,
                "last_contact_age_s": s.last_contact_age_s,
            }
            for s in with_pos[:sample]
        ],
    }


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise TitanEyeError("--bbox requiere 4 valores: lamin,lamax,lomin,lomax")
    try:
        a, b, c, d = (float(p) for p in parts)
    except ValueError as exc:
        raise TitanEyeError(f"--bbox con valores no numéricos: {raw}") from exc
    return (a, b, c, d)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="titan-eye", description="Titan Eye CLI")
    parser.add_argument("--version", action="version", version=f"titan-eye {_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingiere un dominio desde su fuente pública")
    ingest_sub = p_ingest.add_subparsers(dest="domain", required=True)

    p_aerial = ingest_sub.add_parser("aerial", help="Dominio aéreo (OpenSky / ADS-B)")
    p_aerial.add_argument("--bbox", default=None,
                          help="Región: lamin,lamax,lomin,lomax (grados)")
    p_aerial.add_argument("--data-root", default=None,
                          help="Raíz de datos local. Activa cache CAS + persistencia Normalized.")
    p_aerial.add_argument("--persist", action="store_true",
                          help="Persiste la capa Normalized en Parquet (requiere --data-root).")

    p_orbital = ingest_sub.add_parser("orbital", help="Dominio orbital (CelesTrak / TLE)")
    p_orbital.add_argument("--group", default="stations",
                           help="GROUP de CelesTrak (p. ej. stations, active). Default: stations")
    p_orbital.add_argument("--catnr", type=int, default=None,
                           help="Número de catálogo NORAD (alternativa a --group)")
    p_orbital.add_argument("--data-root", default=None,
                           help="Raíz de datos local. Activa cache CAS + persistencia.")
    p_orbital.add_argument("--persist", action="store_true",
                           help="Persiste la capa Normalized en Parquet (requiere --data-root).")

    p_surface = ingest_sub.add_parser("surface", help="Dominio superficie (eventos de conflicto)")
    p_surface.add_argument("--events", required=True,
                           help="Fichero JSON de eventos (ACLED/GDELT exportado).")
    p_surface.add_argument("--data-root", default=None,
                           help="Raíz de datos local (para --persist).")
    p_surface.add_argument("--persist", action="store_true",
                           help="Persiste los eventos en Parquet (requiere --data-root).")

    p_maritime = ingest_sub.add_parser("maritime", help="Dominio marítimo (buques / AIS)")
    p_maritime.add_argument("--vessels", required=True,
                            help="Fichero JSON de buques (AIS exportado).")
    p_maritime.add_argument("--data-root", default=None,
                            help="Raíz de datos local (para --persist).")
    p_maritime.add_argument("--persist", action="store_true",
                            help="Persiste los buques en Parquet (requiere --data-root).")

    p_inst = ingest_sub.add_parser("installations",
                                   help="Referencia: bases e infraestructura (OSINT estático)")
    p_inst.add_argument("--file", required=True,
                        help="Fichero JSON de instalaciones (fuentes públicas).")
    p_inst.add_argument("--data-root", default=None, help="Raíz de datos local (para --persist).")
    p_inst.add_argument("--persist", action="store_true",
                        help="Persiste las instalaciones en Parquet (requiere --data-root).")

    p_heat = sub.add_parser("heatmap",
                            help="Mapa de calor KDE de densidad de eventos REPORTADOS (superficie)")
    p_heat.add_argument("--events", required=True, help="Fichero JSON de eventos.")
    p_heat.add_argument("--bandwidth-km", type=float, default=50.0,
                        help="Ancho de banda del kernel (km). Default: 50")
    p_heat.add_argument("--grid-deg", type=float, default=0.25,
                        help="Resolución de la rejilla (grados). Default: 0.25")

    p_bal = sub.add_parser(
        "reconstruct-ballistic",
        help="Reconstruye una trayectoria balística desde un reporte público (suborbital)")
    p_bal.add_argument("--report", required=True,
                       help="Fichero JSON del reporte (launch/impact/apogee + tolerancias).")
    p_bal.add_argument("--data-root", default=None, help="Raíz de datos local (para --persist).")
    p_bal.add_argument("--persist", action="store_true",
                       help="Persiste la trayectoria reconstruida (requiere --data-root).")

    for dom in ("aerial", "orbital", "surface", "maritime", "installations"):
        pv = sub.add_parser(f"verify-{dom}", help=f"Verifica integridad de la cadena {dom}")
        pv.add_argument("--data-root", required=True, help="Raíz de datos local a verificar.")
        pv.add_argument("--no-reproducibility", action="store_true",
                        help="Omite la comprobación I2 (reproducibilidad).")

    p_build = sub.add_parser("build-case",
                             help="Ensambla un caso de situación portable y auditable por hash")
    p_build.add_argument("--data-root", required=True, help="Raíz de datos persistida.")
    p_build.add_argument("--title", default="Caso de situación Titan Eye", help="Título del caso.")
    p_build.add_argument("--case-id", default=None,
                         help="ID del caso (por defecto: derivado de la fecha).")
    p_build.add_argument("--out", required=True, help="Ruta de salida del caso JSON.")

    p_vcase = sub.add_parser("verify-case",
                             help="Verifica la auto-consistencia de un caso de situación por hash")
    p_vcase.add_argument("--case", required=True, help="Fichero JSON del caso.")
    return parser


def cli_entry_point(argv: list[str] | None = None) -> int:
    # En Windows la consola es cp1252 por defecto; el output JSON es UTF-8
    # (ensure_ascii=False). Forzar UTF-8 evita mojibake en notas con acentos.
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest" and args.domain == "aerial":
            return _cmd_ingest_aerial(args)
        if args.command == "ingest" and args.domain == "orbital":
            return _cmd_ingest_orbital(args)
        if args.command == "ingest" and args.domain == "surface":
            return _cmd_ingest_surface(args)
        if args.command == "ingest" and args.domain == "maritime":
            return _cmd_ingest_maritime(args)
        if args.command == "ingest" and args.domain == "installations":
            return _cmd_ingest_installations(args)
        if args.command == "heatmap":
            return _cmd_heatmap(args)
        if args.command == "reconstruct-ballistic":
            return _cmd_reconstruct_ballistic(args)
        if args.command in ("verify-aerial", "verify-orbital", "verify-surface", "verify-maritime"):
            return _cmd_verify(args, domain=args.command.split("-", 1)[1])
        if args.command == "verify-installations":
            return _cmd_verify_installations(args)
        if args.command == "build-case":
            return _cmd_build_case(args)
        if args.command == "verify-case":
            return _cmd_verify_case(args)
        parser.error("comando no reconocido")
        return 2
    except TitanEyeError as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1


def _cmd_ingest_aerial(args: argparse.Namespace) -> int:
    from pathlib import Path

    from titan_eye.catalog.aircraft_states_repo import AircraftStatesRepository
    from titan_eye.ingestion.cache import FetchCache
    from titan_eye.ingestion.transport import UrllibTransport
    from titan_eye.orchestration.ingest_pipeline import AerialIngestPipeline

    if args.persist and not args.data_root:
        raise TitanEyeError("--persist requiere --data-root")

    cache = None
    repo = None
    if args.data_root:
        root = Path(args.data_root)
        cache = FetchCache(root / "cache")
        if args.persist:
            repo = AircraftStatesRepository(root / "normalized" / "aerial")

    source = OpenSkySource(transport=UrllibTransport(), cache=cache)
    bbox = _parse_bbox(args.bbox)

    if repo is not None:
        pipeline = AerialIngestPipeline(source, repo)
        result = pipeline.ingest(bbox=bbox)
        print(json.dumps({
            "domain": "aerial",
            "content_hash": result.content_hash,
            "n_states": result.n_states,
            "n_with_position": result.n_with_position,
            "snapshot_written": result.snapshot_written,
            "persisted_total": repo.count(),
        }, indent=2, ensure_ascii=False))
        return 0

    summary = run_ingest_aerial(source=source, bbox=bbox)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def run_ingest_orbital(*, source, group: str | None, catnr: int | None) -> dict[str, Any]:
    """Ingesta + parseo del dominio orbital. Resumen serializable. No toca red por
    sí mismo: usa la `source` inyectada."""
    from titan_eye.catalog.normalizers.tle import TLE_NORMALIZER_VERSION, normalize_tles

    if catnr is not None:
        artifact = source.fetch_catnr(catnr)
    else:
        artifact = source.fetch_group(group or "stations")
    elements = normalize_tles(artifact)
    return {
        "domain": "orbital",
        "source_id": artifact.source_id,
        "content_hash": artifact.content_hash,
        "epistemic_label": artifact.epistemic_label.value,
        "license_note": artifact.license_note,
        "normalizer_version": TLE_NORMALIZER_VERSION,
        "n_elements": len(elements),
        "elements": elements,
        "sample": [
            {"norad": e.norad_cat_id, "name": e.object_name,
             "incl_deg": round(e.inclination_deg, 2),
             "period_min": round(e.period_min, 1),
             "mean_alt_km": round(e.mean_altitude_km, 1)}
            for e in elements[:5]
        ],
    }


def _cmd_ingest_orbital(args: argparse.Namespace) -> int:
    from pathlib import Path

    from titan_eye.catalog.orbital_elements_repo import OrbitalElementsRepository
    from titan_eye.ingestion.cache import FetchCache
    from titan_eye.ingestion.sources.celestrak import CelesTrakSource
    from titan_eye.ingestion.transport import UrllibTransport

    if args.persist and not args.data_root:
        raise TitanEyeError("--persist requiere --data-root")

    cache = None
    repo = None
    if args.data_root:
        root = Path(args.data_root)
        cache = FetchCache(root / "cache")
        if args.persist:
            repo = OrbitalElementsRepository(root / "normalized" / "orbital")

    source = CelesTrakSource(transport=UrllibTransport(), cache=cache)
    summary = run_ingest_orbital(source=source, group=args.group, catnr=args.catnr)
    elements = summary.pop("elements")
    written = repo.insert_snapshot(elements) if repo is not None else None
    if repo is not None:
        summary["snapshot_written"] = written
        summary["persisted_total"] = repo.count()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def run_ingest_surface(*, artifact) -> tuple[dict[str, Any], list]:
    """Normaliza un dataset de eventos sellado. No toca red. (resumen, eventos)."""
    from titan_eye.catalog.normalizers.conflict_events import normalize_conflict_events

    events = normalize_conflict_events(artifact)
    res = {}
    for e in events:
        res[e.geoloc_resolution.value] = res.get(e.geoloc_resolution.value, 0) + 1
    summary = {
        "domain": "surface",
        "content_hash": artifact.content_hash,
        "epistemic_label": artifact.epistemic_label.value,   # asserted
        "n_events": len(events),
        "by_geoloc_resolution": res,
        "note": "Eventos AFIRMADOS por terceros (asserted). No verificados por Titan Eye.",
    }
    return summary, events


def _cmd_ingest_surface(args: argparse.Namespace) -> int:
    from pathlib import Path

    from titan_eye.core.domains import Domain
    from titan_eye.ingestion.sources.local_report import seal_report_file

    artifact = seal_report_file(
        args.events, domain=Domain.SURFACE, source_id="conflict.events",
        license_note="Dataset público de eventos (p. ej. ACLED/GDELT) — respetar atribución y TOS.",
    )
    summary, events = run_ingest_surface(artifact=artifact)
    if args.persist:
        if not args.data_root:
            raise TitanEyeError("--persist requiere --data-root")
        from titan_eye.catalog.conflict_events_repo import ConflictEventsRepository
        from titan_eye.ingestion.cache import FetchCache
        # Sella el Raw en la cache para que verify-surface tenga su ancla (I1).
        FetchCache(Path(args.data_root) / "cache").put(artifact, cache_key=artifact.content_hash)
        repo = ConflictEventsRepository(Path(args.data_root) / "normalized" / "surface")
        summary["snapshot_written"] = repo.insert_snapshot(events)
        summary["persisted_total"] = repo.count()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _cmd_heatmap(args: argparse.Namespace) -> int:
    from titan_eye.analytics.surface.heatmap import compute_heatmap
    from titan_eye.core.domains import Domain
    from titan_eye.ingestion.sources.local_report import seal_report_file

    artifact = seal_report_file(
        args.events, domain=Domain.SURFACE, source_id="conflict.events",
    )
    _summary, events = run_ingest_surface(artifact=artifact)
    hm = compute_heatmap(events, bandwidth_km=args.bandwidth_km, grid_deg=args.grid_deg)
    print(json.dumps({
        "domain": "surface",
        "kernel": hm.kernel_name,
        "bandwidth_km": hm.bandwidth_km,
        "grid_deg": hm.grid_deg,
        "n_events": hm.n_events,
        "n_cells": len(hm.points),
        "semantics": hm.semantics_note,
    }, indent=2, ensure_ascii=False))
    return 0


def run_ingest_maritime(*, artifact) -> tuple[dict[str, Any], list]:
    """Normaliza un dataset AIS sellado. No toca red. (resumen, buques)."""
    from titan_eye.catalog.normalizers.ais import normalize_ais

    vessels = normalize_ais(artifact)
    by_type: dict[str, int] = {}
    for v in vessels:
        by_type[v.vessel_type.value] = by_type.get(v.vessel_type.value, 0) + 1
    summary = {
        "domain": "maritime",
        "content_hash": artifact.content_hash,
        "epistemic_label": artifact.epistemic_label.value,   # observed
        "n_vessels": len(vessels),
        "by_vessel_type": by_type,
        "note": ("AIS AUTODECLARADO por el buque. Falsificable; buques de guerra "
                 "apagan/falsean el AIS; submarinos sumergidos no transmiten (ADR-0015)."),
    }
    return summary, vessels


def _cmd_ingest_maritime(args: argparse.Namespace) -> int:
    from pathlib import Path

    from titan_eye.core.domains import Domain
    from titan_eye.core.epistemics import EpistemicLabel
    from titan_eye.ingestion.sources.local_report import seal_report_file

    artifact = seal_report_file(
        args.vessels, domain=Domain.MARITIME, source_id="ais.vessels",
        epistemic_label=EpistemicLabel.OBSERVED,
        license_note="Dataset AIS público (p. ej. AISHub/AISStream) — respetar atribución y TOS.",
    )
    summary, vessels = run_ingest_maritime(artifact=artifact)
    if args.persist:
        if not args.data_root:
            raise TitanEyeError("--persist requiere --data-root")
        from titan_eye.catalog.vessel_positions_repo import VesselPositionsRepository
        from titan_eye.ingestion.cache import FetchCache
        # Sella el Raw en la cache para que verify-maritime tenga su ancla (I1).
        FetchCache(Path(args.data_root) / "cache").put(artifact, cache_key=artifact.content_hash)
        repo = VesselPositionsRepository(Path(args.data_root) / "normalized" / "maritime")
        summary["snapshot_written"] = repo.insert_snapshot(vessels)
        summary["persisted_total"] = repo.count()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def run_ingest_installations(*, artifact) -> tuple[dict[str, Any], list]:
    """Normaliza un dataset de instalaciones sellado. No toca red. (resumen, items)."""
    from titan_eye.catalog.normalizers.installations import normalize_installations

    items = normalize_installations(artifact)
    by_cat: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for it in items:
        by_cat[it.category.value] = by_cat.get(it.category.value, 0) + 1
        by_type[it.installation_type.value] = by_type.get(it.installation_type.value, 0) + 1
    summary = {
        "layer": "installations",
        "content_hash": artifact.content_hash,
        "epistemic_label": artifact.epistemic_label.value,   # asserted
        "n_installations": len(items),
        "by_category": by_cat,
        "by_type": by_type,
        "note": ("Geografía de referencia PÚBLICA y estática (asserted). Puede estar "
                 "desactualizada/aproximada. Sin cómputo operacional ni targeting (ADR-0017)."),
    }
    return summary, items


def _cmd_ingest_installations(args: argparse.Namespace) -> int:
    from pathlib import Path

    from titan_eye.core.domains import Domain
    from titan_eye.ingestion.sources.local_report import seal_report_file

    artifact = seal_report_file(
        args.file, domain=Domain.REFERENCE, source_id="installations.reference",
        license_note="Referencia pública (OSM/Wikipedia/FAS) — respetar atribución y TOS.",
    )
    summary, items = run_ingest_installations(artifact=artifact)
    if args.persist:
        if not args.data_root:
            raise TitanEyeError("--persist requiere --data-root")
        from titan_eye.catalog.installations_repo import InstallationsRepository
        from titan_eye.ingestion.cache import FetchCache
        FetchCache(Path(args.data_root) / "cache").put(artifact, cache_key=artifact.content_hash)
        repo = InstallationsRepository(Path(args.data_root) / "reference" / "installations")
        summary["snapshot_written"] = repo.insert_snapshot(items)
        summary["persisted_total"] = repo.count()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _cmd_verify_installations(args: argparse.Namespace) -> int:
    from pathlib import Path

    from titan_eye.catalog.installations_repo import InstallationsRepository
    from titan_eye.ingestion.cache import FetchCache
    from titan_eye.provenance.integrity import verify_installations_integrity

    root = Path(args.data_root)
    repo = InstallationsRepository(root / "reference" / "installations")
    cache = FetchCache(root / "cache")
    report = verify_installations_integrity(
        repo, cache, check_reproducibility=not args.no_reproducibility
    )
    print(json.dumps({
        "ok": report.ok, "n_states": report.n_states,
        "n_source_hashes": report.n_source_hashes,
        "orphan_source_hashes": report.orphan_source_hashes,
        "reproducibility_mismatches": report.reproducibility_mismatches,
    }, indent=2, ensure_ascii=False))
    return 0 if report.ok else 1


def run_reconstruct_ballistic(*, artifact, n_points: int = 60) -> tuple[dict[str, Any], Any]:
    """Normaliza el reporte sellado y reconstruye la trayectoria. No toca red.

    Devuelve (resumen serializable, BallisticTrajectory)."""
    from titan_eye.analytics.ballistic.reconstruct import reconstruct
    from titan_eye.catalog.normalizers.ballistic_report import normalize_ballistic_report

    report = normalize_ballistic_report(artifact)
    traj = reconstruct(report, n_points=n_points)
    summary = {
        "domain": "suborbital",
        "event_id": traj.event_id,
        "content_hash_source": artifact.content_hash,
        "report_epistemic": report.epistemic_label.value,        # asserted
        "trajectory_epistemic": traj.epistemic_label.value,      # inferred
        "model_name": traj.model_name,
        "range_km": traj.range_km,
        "apogee_km": traj.apogee_km,
        "eccentricity": traj.eccentricity,
        "band_km": traj.band_km,
        "impact_dispersion_km": traj.impact_dispersion_km,
        "model_uncertainty_km": traj.model_uncertainty_km,
        "n_arc_points": len(traj.arc),
        "note": ("RECONSTRUCCIÓN desde reporte público (asserted) -> trayectoria "
                 "(inferred). NO es track de sensor."),
    }
    return summary, traj


def _cmd_reconstruct_ballistic(args: argparse.Namespace) -> int:
    from pathlib import Path

    from titan_eye.core.domains import Domain
    from titan_eye.ingestion.sources.local_report import seal_report_file

    artifact = seal_report_file(
        args.report, domain=Domain.SUBORBITAL, source_id="ballistic.report",
    )
    summary, traj = run_reconstruct_ballistic(artifact=artifact)

    if args.persist:
        if not args.data_root:
            raise TitanEyeError("--persist requiere --data-root")
        from titan_eye.catalog.ballistic_repo import BallisticTrajectoryRepository
        from titan_eye.ingestion.cache import FetchCache
        # Sella el reporte Raw en la cache (ancla de procedencia para build-case).
        FetchCache(Path(args.data_root) / "cache").put(artifact, cache_key=artifact.content_hash)
        repo = BallisticTrajectoryRepository(Path(args.data_root) / "derived" / "ballistic")
        summary["persisted"] = repo.insert(traj)
        summary["persisted_total"] = repo.count()

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _collect_refs_from_root(root) -> list:
    """Lee las detecciones persistidas en el data-root y produce DetectionRefs."""
    from pathlib import Path

    from titan_eye.catalog.aircraft_states_repo import AircraftStatesRepository
    from titan_eye.catalog.ballistic_repo import BallisticTrajectoryRepository
    from titan_eye.catalog.conflict_events_repo import ConflictEventsRepository
    from titan_eye.catalog.orbital_elements_repo import OrbitalElementsRepository
    from titan_eye.catalog.vessel_positions_repo import VesselPositionsRepository
    from titan_eye.core.domains import Domain
    from titan_eye.provenance.situation_case import DetectionRef

    root = Path(root)
    norm = root / "normalized"
    refs: list = []
    specs = [
        (Domain.AERIAL, "opensky.states", AircraftStatesRepository(norm / "aerial")),
        (Domain.ORBITAL, "celestrak.gp", OrbitalElementsRepository(norm / "orbital")),
        (Domain.SURFACE, "conflict.events", ConflictEventsRepository(norm / "surface")),
        (Domain.MARITIME, "ais.vessels", VesselPositionsRepository(norm / "maritime")),
        (Domain.SUBORBITAL, "ballistic.report",
         BallisticTrajectoryRepository(root / "derived" / "ballistic")),
    ]
    for domain, source_id, repo in specs:
        for det in repo.iter_all():
            refs.append(DetectionRef(
                domain=domain, source_id=source_id,
                content_hash_source=det.content_hash_source,
                epistemic_label=det.epistemic_label,
                canonical=det.model_dump(mode="json"),
            ))
    return refs


def _cmd_build_case(args: argparse.Namespace) -> int:
    from datetime import datetime
    from pathlib import Path

    from titan_eye.provenance.situation_case import build_situation_case

    refs = _collect_refs_from_root(args.data_root)
    if not refs:
        raise TitanEyeError(
            f"No hay detecciones persistidas en {args.data_root} (¿usaste --persist?)"
        )
    created_at = datetime.now(UTC)
    case_id = args.case_id or f"case_{created_at.strftime('%Y%m%dT%H%M%SZ')}"
    case = build_situation_case(case_id=case_id, title=args.title, created_at=created_at, refs=refs)
    Path(args.out).write_text(case.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps({
        "case_id": case.case_id,
        "case_hash": case.case_hash,
        "n_entries": len(case.entries),
        "domains": sorted({e.domain.value for e in case.entries}),
        "out": str(args.out),
    }, indent=2, ensure_ascii=False))
    return 0


def _cmd_verify_case(args: argparse.Namespace) -> int:
    from pathlib import Path

    from titan_eye.provenance.situation_case import SituationCase, verify_situation_case

    # utf-8-sig tolera un BOM opcional (editores Windows lo añaden).
    case = SituationCase.model_validate_json(Path(args.case).read_text(encoding="utf-8-sig"))
    rep = verify_situation_case(case)
    print(json.dumps({
        "case_id": rep.case_id,
        "ok": rep.ok,
        "case_hash": rep.expected_hash,
        "recomputed_hash": rep.actual_hash,
        "n_entries": rep.n_entries,
        "issues": rep.issues,
    }, indent=2, ensure_ascii=False))
    return 0 if rep.ok else 1


def _cmd_verify(args: argparse.Namespace, *, domain: str) -> int:
    from pathlib import Path

    from titan_eye.ingestion.cache import FetchCache

    root = Path(args.data_root)
    cache = FetchCache(root / "cache")
    if domain == "aerial":
        from titan_eye.catalog.aircraft_states_repo import AircraftStatesRepository
        from titan_eye.provenance.integrity import verify_aerial_integrity

        repo = AircraftStatesRepository(root / "normalized" / "aerial")
        report = verify_aerial_integrity(
            repo, cache, check_reproducibility=not args.no_reproducibility
        )
    elif domain == "orbital":
        from titan_eye.catalog.orbital_elements_repo import OrbitalElementsRepository
        from titan_eye.provenance.integrity import verify_orbital_integrity

        repo = OrbitalElementsRepository(root / "normalized" / "orbital")
        report = verify_orbital_integrity(
            repo, cache, check_reproducibility=not args.no_reproducibility
        )
    elif domain == "surface":
        from titan_eye.catalog.conflict_events_repo import ConflictEventsRepository
        from titan_eye.provenance.integrity import verify_surface_integrity

        repo = ConflictEventsRepository(root / "normalized" / "surface")
        report = verify_surface_integrity(
            repo, cache, check_reproducibility=not args.no_reproducibility
        )
    else:
        from titan_eye.catalog.vessel_positions_repo import VesselPositionsRepository
        from titan_eye.provenance.integrity import verify_maritime_integrity

        repo = VesselPositionsRepository(root / "normalized" / "maritime")
        report = verify_maritime_integrity(
            repo, cache, check_reproducibility=not args.no_reproducibility
        )
    print(json.dumps({
        "ok": report.ok,
        "n_states": report.n_states,
        "n_source_hashes": report.n_source_hashes,
        "orphan_source_hashes": report.orphan_source_hashes,
        "reproducibility_mismatches": report.reproducibility_mismatches,
    }, indent=2, ensure_ascii=False))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(cli_entry_point())
