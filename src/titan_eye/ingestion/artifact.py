"""RawArtifact — los bytes exactos de una fuente pública, sellados por hash.

Es el primer eslabón de la cadena de procedencia (ADR-0005). El adaptador de
fuente NO interpreta el payload: solo lo adquiere y lo sella. La interpretación
es trabajo de la capa Normalized (ADR-0001).

Contrato de procedencia mínimo (ADR-0002): source_id, dominio, url, fetched_at,
payload, content_hash, etiqueta epistémica por defecto del dominio, y la nota de
licencia/atribución de la fuente.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.identity import content_hash_bytes

RAW_ARTIFACT_SCHEMA_VERSION = "0.1.0"


class RawArtifact(BaseModel):
    """Artefacto crudo inmutable, identificado por el SHA-256 de su payload."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    domain: Domain
    request_url: str
    request_params: dict[str, str] = {}
    fetched_at: datetime
    payload: bytes
    content_hash: str
    media_type: str = "application/octet-stream"
    epistemic_label: EpistemicLabel = EpistemicLabel.OBSERVED
    license_note: str = ""
    schema_version: str = RAW_ARTIFACT_SCHEMA_VERSION

    @classmethod
    def seal(
        cls,
        *,
        source_id: str,
        domain: Domain,
        request_url: str,
        fetched_at: datetime,
        payload: bytes,
        request_params: dict[str, str] | None = None,
        media_type: str = "application/octet-stream",
        epistemic_label: EpistemicLabel = EpistemicLabel.OBSERVED,
        license_note: str = "",
    ) -> RawArtifact:
        """Construye un artefacto computando su content_hash sobre el payload."""
        return cls(
            source_id=source_id,
            domain=domain,
            request_url=request_url,
            request_params=request_params or {},
            fetched_at=fetched_at,
            payload=payload,
            content_hash=content_hash_bytes(payload),
            media_type=media_type,
            epistemic_label=epistemic_label,
            license_note=license_note,
        )

    def metadata(self) -> dict[str, str]:
        """Forma serializable de los metadatos (sin el payload), para el índice
        de la cache. El payload se guarda aparte como blob (CAS)."""
        return {
            "source_id": self.source_id,
            "domain": self.domain.value,
            "request_url": self.request_url,
            "request_params": _params_to_str(self.request_params),
            "fetched_at": self.fetched_at.isoformat(),
            "content_hash": self.content_hash,
            "media_type": self.media_type,
            "epistemic_label": self.epistemic_label.value,
            "license_note": self.license_note,
            "schema_version": self.schema_version,
        }


def _params_to_str(params: dict[str, str]) -> str:
    import json

    return json.dumps(params, sort_keys=True, separators=(",", ":"))
