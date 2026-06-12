"""Sellado de reportes locales como RawArtifact (ADR-0002/0005).

Algunos dominios (suborbital, ADR-0011) no tienen una API pública: su entrada es
un reporte JSON estructurado que el operador compone desde fuentes públicas. Este
helper sella los bytes EXACTOS del fichero como RawArtifact, anclando la
procedencia igual que cualquier otra fuente. No interpreta el contenido.
"""

from __future__ import annotations

from pathlib import Path

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.timebase import Clock, SystemClock
from titan_eye.ingestion.artifact import RawArtifact


def seal_report_file(
    path: Path | str,
    *,
    domain: Domain,
    source_id: str,
    epistemic_label: EpistemicLabel = EpistemicLabel.ASSERTED,
    license_note: str = "",
    clock: Clock | None = None,
) -> RawArtifact:
    """Sella los bytes de un fichero de reporte local como RawArtifact."""
    p = Path(path)
    payload = p.read_bytes()
    now = (clock or SystemClock()).now()
    return RawArtifact.seal(
        source_id=source_id,
        domain=domain,
        request_url=p.resolve().as_uri(),
        fetched_at=now,
        payload=payload,
        media_type="application/json",
        epistemic_label=epistemic_label,
        license_note=license_note,
    )
