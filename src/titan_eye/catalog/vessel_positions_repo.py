"""Repositorio Parquet+DuckDB de la capa Normalized del dominio marítimo (ADR-0008/0015).

Persiste `VesselPosition` como Parquet inmutable, un archivo por snapshot de origen:
``root/year=YYYY/month=MM/day=DD/snap_<content_hash_source>.parquet``. Idempotente
por archivo (ADR-0006). Mismo patrón que el dominio aéreo.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from titan_eye.catalog.maritime import VesselPosition
from titan_eye.core.errors import CatalogError

_ARROW_SCHEMA = pa.schema([
    pa.field("mmsi", pa.string(), nullable=False),
    pa.field("name", pa.string(), nullable=True),
    pa.field("vessel_type", pa.string(), nullable=False),
    pa.field("flag", pa.string(), nullable=True),
    pa.field("latitude", pa.float64(), nullable=False),
    pa.field("longitude", pa.float64(), nullable=False),
    pa.field("course_deg", pa.float64(), nullable=True),
    pa.field("heading_deg", pa.float64(), nullable=True),
    pa.field("speed_knots", pa.float64(), nullable=True),
    pa.field("nav_status", pa.string(), nullable=True),
    pa.field("last_contact", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("last_contact_age_s", pa.float64(), nullable=True),
    pa.field("content_hash_source", pa.string(), nullable=False),
    pa.field("snapshot_time", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("epistemic_label", pa.string(), nullable=False),
    pa.field("schema_version", pa.string(), nullable=False),
])
_COLUMNS = [f.name for f in _ARROW_SCHEMA]


class VesselPositionsRepository:
    """Repositorio Parquet+DuckDB para `vessel_positions` (Normalized, marítimo)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def insert_snapshot(self, vessels: list[VesselPosition]) -> bool:
        if not vessels:
            return False
        hashes = {v.content_hash_source for v in vessels}
        if len(hashes) != 1:
            raise CatalogError(
                f"insert_snapshot requiere buques de un único Raw; vi {len(hashes)}"
            )
        path = self._snapshot_path(vessels[0])
        if path.exists():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        pq.write_table(self._to_arrow(vessels), tmp, compression="zstd")
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

    def iter_all(self) -> Iterator[VesselPosition]:
        if not self._has_any():
            return
        with self._connect() as conn:
            tbl = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM "
                f"read_parquet('{self._glob()}', hive_partitioning=false)"
            ).to_arrow_table()
        for rec in tbl.to_pylist():
            yield VesselPosition.model_validate(rec)

    def find_by_mmsi(self, mmsi: str) -> list[VesselPosition]:
        if not self._has_any():
            return []
        with self._connect() as conn:
            tbl = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM "
                f"read_parquet('{self._glob()}', hive_partitioning=false) "
                "WHERE mmsi = ? ORDER BY snapshot_time DESC",
                [mmsi],
            ).to_arrow_table()
        return [VesselPosition.model_validate(r) for r in tbl.to_pylist()]

    def _snapshot_path(self, v: VesselPosition) -> Path:
        ts = v.snapshot_time.astimezone(UTC)
        return (
            self.root / f"year={ts.year}" / f"month={ts.month:02d}" / f"day={ts.day:02d}"
            / f"snap_{v.content_hash_source}.parquet"
        )

    def _glob(self) -> str:
        return str(self.root / "**" / "*.parquet").replace("\\", "/")

    def _has_any(self) -> bool:
        return any(self.root.rglob("*.parquet"))

    def _connect(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(database=":memory:")
        conn.execute("SET TimeZone='UTC'")
        return conn

    def _to_arrow(self, vessels: list[VesselPosition]) -> pa.Table:
        cols: dict[str, list] = {name: [] for name in _COLUMNS}
        for v in vessels:
            d = v.model_dump()
            d["vessel_type"] = v.vessel_type.value
            d["epistemic_label"] = v.epistemic_label.value
            for name in _COLUMNS:
                cols[name].append(d[name])
        return pa.table(cols, schema=_ARROW_SCHEMA)
