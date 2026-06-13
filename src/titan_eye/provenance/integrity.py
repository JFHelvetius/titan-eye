"""Verificadores de integridad de la cadena de procedencia (ADR-0005).

Funciones **puras** que SIEMPRE devuelven un reporte, nunca lanzan para esconder
un fallo (mismo principio que Orbital Sentinel: nada detrás de "confía en mí").

Dos invariantes para el dominio aéreo:

- **I1 — Referencial Raw→Normalized:** todo `content_hash_source` presente en la
  capa Normalized debe existir como blob en la cache CAS (la ancla Raw). Un
  huérfano significa que se persistió un Normalized cuyo Raw se perdió.
- **I2 — Reproducibilidad:** re-normalizar el Raw cacheado debe producir
  exactamente el mismo conjunto de filas Normalized (comparado por hash canónico
  de su contenido semántico). Si no coincide, el normalizador o el dato cambiaron
  bajo los pies del registro (viola P1/P4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from titan_eye.catalog.aircraft import AircraftState
from titan_eye.catalog.aircraft_states_repo import AircraftStatesRepository
from titan_eye.catalog.conflict_events_repo import ConflictEventsRepository
from titan_eye.catalog.country import CountryProfile
from titan_eye.catalog.country_repo import CountryRepository
from titan_eye.catalog.installations import Installation
from titan_eye.catalog.installations_repo import InstallationsRepository
from titan_eye.catalog.maritime import VesselPosition
from titan_eye.catalog.normalizers.ais import normalize_ais
from titan_eye.catalog.normalizers.conflict_events import normalize_conflict_events
from titan_eye.catalog.normalizers.country import normalize_countries
from titan_eye.catalog.normalizers.installations import normalize_installations
from titan_eye.catalog.normalizers.opensky_states import normalize_states
from titan_eye.catalog.normalizers.osint import normalize_osint
from titan_eye.catalog.normalizers.tle import normalize_tles
from titan_eye.catalog.orbital import OrbitalElement
from titan_eye.catalog.orbital_elements_repo import OrbitalElementsRepository
from titan_eye.catalog.osint import OsintItem
from titan_eye.catalog.osint_repo import OsintRepository
from titan_eye.catalog.surface import ConflictEvent
from titan_eye.catalog.vessel_positions_repo import VesselPositionsRepository
from titan_eye.core.identity import content_hash_obj
from titan_eye.ingestion.cache import FetchCache


@dataclass(frozen=True)
class IntegrityReport:
    """Resultado de verificar la cadena aérea. `ok` es el AND de las invariantes."""

    n_states: int
    n_source_hashes: int
    orphan_source_hashes: list[str] = field(default_factory=list)        # I1
    reproducibility_mismatches: list[str] = field(default_factory=list)  # I2

    @property
    def ok(self) -> bool:
        return not self.orphan_source_hashes and not self.reproducibility_mismatches


def _row_identity(
    row: AircraftState | OrbitalElement | ConflictEvent | VesselPosition
    | Installation | OsintItem | CountryProfile,
) -> str:
    """Hash canónico del contenido SEMÁNTICO de una fila Normalized (estable
    bajo reproceso). El content_hash_source y schema_version forman parte de la
    identidad: lo que define la fila es todo su contenido normalizado."""
    return content_hash_obj(row.model_dump(mode="json"))


def verify_aerial_integrity(
    repo: AircraftStatesRepository,
    cache: FetchCache,
    *,
    check_reproducibility: bool = True,
) -> IntegrityReport:
    """Verifica I1 (referencial) y, opcionalmente, I2 (reproducibilidad)."""
    states = list(repo.iter_all())
    source_hashes = sorted({s.content_hash_source for s in states})

    orphans: list[str] = [h for h in source_hashes if not cache.has_blob(h)]

    mismatches: list[str] = []
    if check_reproducibility:
        # Agrupa filas persistidas por su Raw de origen.
        by_source: dict[str, list[AircraftState]] = {}
        for s in states:
            by_source.setdefault(s.content_hash_source, []).append(s)
        for h in source_hashes:
            if h in orphans:
                continue  # sin Raw no se puede reproducir; ya contado en I1
            artifact = cache.get_by_content_hash(h)
            if artifact is None:
                orphans.append(h)
                continue
            reproduced = normalize_states(artifact)
            expected = {_row_identity(s) for s in reproduced}
            persisted = {_row_identity(s) for s in by_source[h]}
            if expected != persisted:
                mismatches.append(h)

    return IntegrityReport(
        n_states=len(states),
        n_source_hashes=len(source_hashes),
        orphan_source_hashes=orphans,
        reproducibility_mismatches=mismatches,
    )


def verify_orbital_integrity(
    repo: OrbitalElementsRepository,
    cache: FetchCache,
    *,
    check_reproducibility: bool = True,
) -> IntegrityReport:
    """Espejo orbital de `verify_aerial_integrity`: I1 referencial + I2
    reproducibilidad del parseo TLE (ADR-0010)."""
    elements = list(repo.iter_all())
    source_hashes = sorted({e.content_hash_source for e in elements})

    orphans: list[str] = [h for h in source_hashes if not cache.has_blob(h)]

    mismatches: list[str] = []
    if check_reproducibility:
        by_source: dict[str, list[OrbitalElement]] = {}
        for e in elements:
            by_source.setdefault(e.content_hash_source, []).append(e)
        for h in source_hashes:
            if h in orphans:
                continue
            artifact = cache.get_by_content_hash(h)
            if artifact is None:
                orphans.append(h)
                continue
            reproduced = normalize_tles(artifact)
            expected = {_row_identity(e) for e in reproduced}
            persisted = {_row_identity(e) for e in by_source[h]}
            if expected != persisted:
                mismatches.append(h)

    return IntegrityReport(
        n_states=len(elements),
        n_source_hashes=len(source_hashes),
        orphan_source_hashes=orphans,
        reproducibility_mismatches=mismatches,
    )


def verify_surface_integrity(
    repo: ConflictEventsRepository,
    cache: FetchCache,
    *,
    check_reproducibility: bool = True,
) -> IntegrityReport:
    """Espejo de superficie: I1 referencial + I2 reproducibilidad del parseo de
    eventos de conflicto (ADR-0012)."""
    events = list(repo.iter_all())
    source_hashes = sorted({e.content_hash_source for e in events})

    orphans: list[str] = [h for h in source_hashes if not cache.has_blob(h)]

    mismatches: list[str] = []
    if check_reproducibility:
        by_source: dict[str, list[ConflictEvent]] = {}
        for e in events:
            by_source.setdefault(e.content_hash_source, []).append(e)
        for h in source_hashes:
            if h in orphans:
                continue
            artifact = cache.get_by_content_hash(h)
            if artifact is None:
                orphans.append(h)
                continue
            reproduced = normalize_conflict_events(artifact)
            expected = {_row_identity(e) for e in reproduced}
            persisted = {_row_identity(e) for e in by_source[h]}
            if expected != persisted:
                mismatches.append(h)

    return IntegrityReport(
        n_states=len(events),
        n_source_hashes=len(source_hashes),
        orphan_source_hashes=orphans,
        reproducibility_mismatches=mismatches,
    )


def verify_maritime_integrity(
    repo: VesselPositionsRepository,
    cache: FetchCache,
    *,
    check_reproducibility: bool = True,
) -> IntegrityReport:
    """Espejo marítimo: I1 referencial + I2 reproducibilidad del parseo AIS (ADR-0015)."""
    vessels = list(repo.iter_all())
    source_hashes = sorted({v.content_hash_source for v in vessels})

    orphans: list[str] = [h for h in source_hashes if not cache.has_blob(h)]

    mismatches: list[str] = []
    if check_reproducibility:
        by_source: dict[str, list[VesselPosition]] = {}
        for v in vessels:
            by_source.setdefault(v.content_hash_source, []).append(v)
        for h in source_hashes:
            if h in orphans:
                continue
            artifact = cache.get_by_content_hash(h)
            if artifact is None:
                orphans.append(h)
                continue
            reproduced = normalize_ais(artifact)
            expected = {_row_identity(v) for v in reproduced}
            persisted = {_row_identity(v) for v in by_source[h]}
            if expected != persisted:
                mismatches.append(h)

    return IntegrityReport(
        n_states=len(vessels),
        n_source_hashes=len(source_hashes),
        orphan_source_hashes=orphans,
        reproducibility_mismatches=mismatches,
    )


def verify_country_integrity(
    repo: CountryRepository,
    cache: FetchCache,
    *,
    check_reproducibility: bool = True,
) -> IntegrityReport:
    """Espejo de fichas país: I1 referencial + I2 reproducibilidad (ADR-0021)."""
    items = list(repo.iter_all())
    source_hashes = sorted({i.content_hash_source for i in items})
    orphans: list[str] = [h for h in source_hashes if not cache.has_blob(h)]
    mismatches: list[str] = []
    if check_reproducibility:
        by_source: dict[str, list[CountryProfile]] = {}
        for it in items:
            by_source.setdefault(it.content_hash_source, []).append(it)
        for h in source_hashes:
            if h in orphans:
                continue
            artifact = cache.get_by_content_hash(h)
            if artifact is None:
                orphans.append(h)
                continue
            reproduced = normalize_countries(artifact)
            if {_row_identity(i) for i in reproduced} != {_row_identity(i) for i in by_source[h]}:
                mismatches.append(h)
    return IntegrityReport(
        n_states=len(items), n_source_hashes=len(source_hashes),
        orphan_source_hashes=orphans, reproducibility_mismatches=mismatches,
    )


def verify_osint_integrity(
    repo: OsintRepository,
    cache: FetchCache,
    *,
    check_reproducibility: bool = True,
) -> IntegrityReport:
    """Espejo OSINT: I1 referencial + I2 reproducibilidad del parseo (ADR-0020)."""
    items = list(repo.iter_all())
    source_hashes = sorted({i.content_hash_source for i in items})
    orphans: list[str] = [h for h in source_hashes if not cache.has_blob(h)]
    mismatches: list[str] = []
    if check_reproducibility:
        by_source: dict[str, list[OsintItem]] = {}
        for it in items:
            by_source.setdefault(it.content_hash_source, []).append(it)
        for h in source_hashes:
            if h in orphans:
                continue
            artifact = cache.get_by_content_hash(h)
            if artifact is None:
                orphans.append(h)
                continue
            reproduced = normalize_osint(artifact)
            if {_row_identity(i) for i in reproduced} != {_row_identity(i) for i in by_source[h]}:
                mismatches.append(h)
    return IntegrityReport(
        n_states=len(items), n_source_hashes=len(source_hashes),
        orphan_source_hashes=orphans, reproducibility_mismatches=mismatches,
    )


def verify_installations_integrity(
    repo: InstallationsRepository,
    cache: FetchCache,
    *,
    check_reproducibility: bool = True,
) -> IntegrityReport:
    """Espejo de la capa de referencia: I1 referencial + I2 reproducibilidad
    del parseo de instalaciones (ADR-0017)."""
    items = list(repo.iter_all())
    source_hashes = sorted({i.content_hash_source for i in items})

    orphans: list[str] = [h for h in source_hashes if not cache.has_blob(h)]

    mismatches: list[str] = []
    if check_reproducibility:
        by_source: dict[str, list[Installation]] = {}
        for it in items:
            by_source.setdefault(it.content_hash_source, []).append(it)
        for h in source_hashes:
            if h in orphans:
                continue
            artifact = cache.get_by_content_hash(h)
            if artifact is None:
                orphans.append(h)
                continue
            reproduced = normalize_installations(artifact)
            expected = {_row_identity(i) for i in reproduced}
            persisted = {_row_identity(i) for i in by_source[h]}
            if expected != persisted:
                mismatches.append(h)

    return IntegrityReport(
        n_states=len(items),
        n_source_hashes=len(source_hashes),
        orphan_source_hashes=orphans,
        reproducibility_mismatches=mismatches,
    )
