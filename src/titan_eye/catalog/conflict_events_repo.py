"""Repositorio Parquet+DuckDB de la capa Normalized del dominio superficie (ADR-0008/0012).

Persiste `ConflictEvent` como Parquet inmutable, un archivo por snapshot de
origen: ``root/year=YYYY/month=MM/snap_<content_hash_source>.parquet`` (partición
por mes del primer evento del snapshot). Idempotente por archivo (ADR-0006).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from titan_eye.catalog.surface import ConflictEvent
from titan_eye.core.errors import CatalogError

_ARROW_SCHEMA = pa.schema([
    pa.field("event_id", pa.string(), nullable=False),
    pa.field("event_date", pa.date32(), nullable=False),
    pa.field("latitude", pa.float64(), nullable=False),
    pa.field("longitude", pa.float64(), nullable=False),
    pa.field("geoloc_resolution", pa.string(), nullable=False),
    pa.field("event_type", pa.string(), nullable=False),
    pa.field("location_name", pa.string(), nullable=False),
    pa.field("country", pa.string(), nullable=True),
    pa.field("reported_fatalities", pa.int64(), nullable=False),
    pa.field("source", pa.string(), nullable=False),
    pa.field("source_url", pa.string(), nullable=False),
    pa.field("notes", pa.string(), nullable=False),
    pa.field("content_hash_source", pa.string(), nullable=False),
    pa.field("epistemic_label", pa.string(), nullable=False),
    pa.field("schema_version", pa.string(), nullable=False),
])
_COLUMNS = [f.name for f in _ARROW_SCHEMA]


class ConflictEventsRepository:
    """Repositorio Parquet+DuckDB para `conflict_events` (Normalized, superficie)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def insert_snapshot(self, events: list[ConflictEvent]) -> bool:
        if not events:
            return False
        hashes = {e.content_hash_source for e in events}
        if len(hashes) != 1:
            raise CatalogError(
                f"insert_snapshot requiere eventos de un único Raw; vi {len(hashes)}"
            )
        path = self._snapshot_path(events[0])
        if path.exists():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        pq.write_table(self._to_arrow(events), tmp, compression="zstd")
        tmp.replace(path)
        return True

    def count(self) -> int:
        if not self._has_any():
            return 0
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM read_parquet('{self._glob()}', "
                "hive_partitioning=false)"
            ).fetchone()
        return int(row[0]) if row else 0

    def iter_all(self) -> Iterator[ConflictEvent]:
        if not self._has_any():
            return
        with self._connect() as conn:
            tbl = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM "
                f"read_parquet('{self._glob()}', hive_partitioning=false)"
            ).to_arrow_table()
        for rec in tbl.to_pylist():
            yield ConflictEvent.model_validate(rec)

    def _snapshot_path(self, event: ConflictEvent) -> Path:
        d: date = event.event_date
        return (
            self.root / f"year={d.year}" / f"month={d.month:02d}"
            / f"snap_{event.content_hash_source}.parquet"
        )

    def _glob(self) -> str:
        return str(self.root / "**" / "*.parquet").replace("\\", "/")

    def _has_any(self) -> bool:
        return any(self.root.rglob("*.parquet"))

    def _connect(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(database=":memory:")
        conn.execute("SET TimeZone='UTC'")
        return conn

    def _to_arrow(self, events: list[ConflictEvent]) -> pa.Table:
        cols: dict[str, list] = {name: [] for name in _COLUMNS}
        for e in events:
            d = e.model_dump()
            d["geoloc_resolution"] = e.geoloc_resolution.value
            d["epistemic_label"] = e.epistemic_label.value
            for name in _COLUMNS:
                cols[name].append(d[name])
        return pa.table(cols, schema=_ARROW_SCHEMA)
