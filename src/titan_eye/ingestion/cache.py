"""Cache content-addressable (CAS) con índice append-only.

Política cache-first (ADR-0002): antes de pedir a una fuente, se comprueba si
una adquisición reciente del mismo request ya existe. Si existe y no ha
caducado (`max_age`), se reutiliza sin tocar la red.

Diseño:
- Los **bytes** (payload) se guardan como blob en `root/blobs/<h[:2]>/<h>.bin`,
  direccionados por su SHA-256 (`content_hash`). Idempotente: los mismos bytes
  ocupan un único blob.
- Los **metadatos** se anexan a `root/index.jsonl` (una línea JSON por
  adquisición), nunca se reescriben (ADR-0006 append-only). Cada registro lleva
  un `cache_key` (función determinista del request) para localizar la última
  adquisición de ese request.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.ingestion.artifact import RawArtifact


class FetchCache:
    """Cache CAS sobre el sistema de archivos local (P8 local-first)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.blobs_dir = self.root / "blobs"
        self.index_path = self.root / "index.jsonl"

    # ── escritura ────────────────────────────────────────────────────
    def put(self, artifact: RawArtifact, *, cache_key: str) -> None:
        """Guarda el blob (idempotente) y anexa el registro de índice."""
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        blob = self._blob_path(artifact.content_hash)
        if not blob.exists():
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(artifact.payload)
        record = {"cache_key": cache_key, **artifact.metadata()}
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")

    # ── lectura ──────────────────────────────────────────────────────
    def get_fresh(
        self, cache_key: str, *, max_age_seconds: float, now: datetime
    ) -> RawArtifact | None:
        """Devuelve la adquisición más reciente de `cache_key` si no ha caducado.

        Recorre el índice (append-only) y se queda con el registro de mayor
        `fetched_at` para ese `cache_key`. Si su antigüedad <= max_age y el blob
        sigue presente, reconstruye el RawArtifact; si no, devuelve None.
        """
        latest = self._latest_record(cache_key)
        if latest is None:
            return None
        fetched_at = datetime.fromisoformat(latest["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        age = (now - fetched_at).total_seconds()
        if age > max_age_seconds:
            return None
        blob = self._blob_path(latest["content_hash"])
        if not blob.exists():
            return None
        return RawArtifact(
            source_id=latest["source_id"],
            domain=Domain(latest["domain"]),
            request_url=latest["request_url"],
            request_params=json.loads(latest.get("request_params") or "{}"),
            fetched_at=fetched_at,
            payload=blob.read_bytes(),
            content_hash=latest["content_hash"],
            media_type=latest.get("media_type", "application/octet-stream"),
            epistemic_label=EpistemicLabel(latest.get("epistemic_label", "observed")),
            license_note=latest.get("license_note", ""),
        )

    def has_blob(self, content_hash: str) -> bool:
        """True si el blob Raw con ese hash sigue presente (ancla de procedencia)."""
        return self._blob_path(content_hash).exists()

    def get_by_content_hash(self, content_hash: str) -> RawArtifact | None:
        """Reconstruye un RawArtifact a partir del blob + su registro de índice.

        Útil para verificadores de reproducibilidad: permite re-normalizar el
        Raw original y comparar contra lo persistido (ADR-0005)."""
        blob = self._blob_path(content_hash)
        if not blob.exists() or not self.index_path.exists():
            return None
        rec: dict[str, str] | None = None
        with self.index_path.open(encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                r = json.loads(stripped)
                if r.get("content_hash") == content_hash:
                    rec = r  # se queda con el último (todos comparten payload)
        if rec is None:
            return None
        fetched_at = datetime.fromisoformat(rec["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return RawArtifact(
            source_id=rec["source_id"],
            domain=Domain(rec["domain"]),
            request_url=rec["request_url"],
            request_params=json.loads(rec.get("request_params") or "{}"),
            fetched_at=fetched_at,
            payload=blob.read_bytes(),
            content_hash=content_hash,
            media_type=rec.get("media_type", "application/octet-stream"),
            epistemic_label=EpistemicLabel(rec.get("epistemic_label", "observed")),
            license_note=rec.get("license_note", ""),
        )

    # ── internos ─────────────────────────────────────────────────────
    def _latest_record(self, cache_key: str) -> dict[str, str] | None:
        if not self.index_path.exists():
            return None
        latest: dict[str, str] | None = None
        latest_ts: datetime | None = None
        with self.index_path.open(encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                rec = json.loads(stripped)
                if rec.get("cache_key") != cache_key:
                    continue
                ts = datetime.fromisoformat(rec["fetched_at"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if latest_ts is None or ts >= latest_ts:
                    latest_ts, latest = ts, rec
        return latest

    def _blob_path(self, content_hash: str) -> Path:
        return self.blobs_dir / content_hash[:2] / f"{content_hash}.bin"
