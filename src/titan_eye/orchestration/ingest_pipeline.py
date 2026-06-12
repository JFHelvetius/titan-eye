"""Pipeline de composición: ingesta del dominio aéreo con persistencia.

Encadena fetch (con cache CAS) → normalize → persist Normalized. Los workflows
de `orchestration/` pueden importar de cualquier plano (ADR-0001 enmienda).
"""

from __future__ import annotations

from dataclasses import dataclass

from titan_eye.catalog.aircraft import AircraftState
from titan_eye.catalog.aircraft_states_repo import AircraftStatesRepository
from titan_eye.catalog.normalizers.opensky_states import normalize_states
from titan_eye.ingestion.sources.opensky import OpenSkySource


@dataclass(frozen=True)
class AerialIngestResult:
    content_hash: str
    n_states: int
    n_with_position: int
    snapshot_written: bool
    states: list[AircraftState]


class AerialIngestPipeline:
    """fetch → normalize → persist para el dominio aéreo."""

    def __init__(self, source: OpenSkySource, repo: AircraftStatesRepository | None = None) -> None:
        self.source = source
        self.repo = repo

    def ingest(
        self, *, bbox: tuple[float, float, float, float] | None = None
    ) -> AerialIngestResult:
        artifact = self.source.fetch_states(bbox=bbox)
        states = normalize_states(artifact)
        written = False
        if self.repo is not None and states:
            written = self.repo.insert_snapshot(states)
        return AerialIngestResult(
            content_hash=artifact.content_hash,
            n_states=len(states),
            n_with_position=sum(1 for s in states if s.has_position),
            snapshot_written=written,
            states=states,
        )
