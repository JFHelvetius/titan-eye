"""Caso de situación portable y verificable (ADR-0013).

Artefacto JSON autocontenido que empaqueta una instantánea de detecciones a través
de dominios, con su procedencia por hash y un `case_hash` content-addressable.
Permite a un tercero AUDITAR la instantánea sin acceso a la base de datos del
productor: recomputa el hash (auto-consistencia) y, reingiriendo la fuente pública,
reproduce los digests (procedencia profunda). Análogo del InvestigationCase de
Orbital Sentinel.

No contiene scores de amenaza ni veredictos de intención (ADR-0003): solo
detecciones con procedencia y su etiqueta epistémica preservada (P9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.identity import content_hash_obj

SITUATION_CASE_SCHEMA_VERSION = "0.1.0"


class SituationCaseEntry(BaseModel):
    """Una entrada del caso: las detecciones de un snapshot de un dominio."""

    model_config = ConfigDict(frozen=True)

    domain: Domain
    source_id: str
    content_hash_source: str   # ancla Raw (ADR-0005)
    epistemic_label: EpistemicLabel
    n_detections: int
    detections_digest: str     # hash invariante al orden del contenido de las detecciones


class SituationCase(BaseModel):
    """Instantánea situacional portable y auditable por hash."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    title: str
    created_at: datetime
    entries: list[SituationCaseEntry]
    case_hash: str
    schema_version: str = SITUATION_CASE_SCHEMA_VERSION

    def content_without_hash(self) -> dict:
        """Forma canónica del caso SIN el case_hash (lo que el hash cubre)."""
        d = self.model_dump(mode="json")
        d.pop("case_hash", None)
        return d


@dataclass(frozen=True)
class DetectionRef:
    """Entrada para el builder: una detección con su dominio y source_id."""

    domain: Domain
    source_id: str
    content_hash_source: str
    epistemic_label: EpistemicLabel
    canonical: dict   # model_dump(mode="json") de la detección


def detections_digest(canonicals: list[dict]) -> str:
    """Digest invariante al orden sobre el contenido de un conjunto de detecciones.

    Se hashea cada detección, se ordenan los hashes y se hashea la lista ordenada:
    así dos reconstrucciones del mismo dato (con distinto orden de lectura)
    producen el mismo digest (precondición de P1)."""
    per = sorted(content_hash_obj(c) for c in canonicals)
    return content_hash_obj(per)


def build_situation_case(
    *,
    case_id: str,
    title: str,
    created_at: datetime,
    refs: list[DetectionRef],
) -> SituationCase:
    """Ensambla un SituationCase agrupando las detecciones por (dominio, snapshot)."""
    groups: dict[tuple[str, str], list[DetectionRef]] = {}
    for r in refs:
        groups.setdefault((r.domain.value, r.content_hash_source), []).append(r)

    entries: list[SituationCaseEntry] = []
    for (domain_val, source_hash), group in groups.items():
        entries.append(SituationCaseEntry(
            domain=Domain(domain_val),
            source_id=group[0].source_id,
            content_hash_source=source_hash,
            epistemic_label=group[0].epistemic_label,
            n_detections=len(group),
            detections_digest=detections_digest([g.canonical for g in group]),
        ))
    # Orden estable de entradas (por dominio, luego por hash) para case_hash determinista.
    entries.sort(key=lambda e: (e.domain.value, e.content_hash_source))

    # Construye el caso con hash provisional y luego sella sobre su PROPIA forma
    # canónica (sin el hash). Así build y verify usan idéntica serialización
    # (la de Pydantic), evitando divergencias de formato (P1).
    provisional = SituationCase(
        case_id=case_id, title=title, created_at=created_at,
        entries=entries, case_hash="",
    )
    case_hash = content_hash_obj(provisional.content_without_hash())
    return provisional.model_copy(update={"case_hash": case_hash})


@dataclass(frozen=True)
class CaseVerificationReport:
    """Resultado de verificar la auto-consistencia de un caso."""

    case_id: str
    ok: bool
    expected_hash: str
    actual_hash: str
    n_entries: int
    issues: list[str] = field(default_factory=list)


def verify_situation_case(case: SituationCase) -> CaseVerificationReport:
    """Auto-consistencia (pura): recomputa el case_hash y comprueba que coincide."""
    recomputed = content_hash_obj(case.content_without_hash())
    issues: list[str] = []
    if recomputed != case.case_hash:
        issues.append("case_hash no coincide con el contenido (caso manipulado).")
    if not case.entries:
        issues.append("el caso no tiene entradas.")
    for e in case.entries:
        if not e.content_hash_source:
            issues.append(f"entrada {e.domain.value} sin content_hash_source (ancla Raw).")
    return CaseVerificationReport(
        case_id=case.case_id,
        ok=not issues,
        expected_hash=case.case_hash,
        actual_hash=recomputed,
        n_entries=len(case.entries),
        issues=issues,
    )
