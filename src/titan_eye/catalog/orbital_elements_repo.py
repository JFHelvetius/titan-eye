"""Repositorio Parquet+DuckDB de la capa Normalized del dominio orbital (ADR-0008/0010).

Persiste `OrbitalElement` como Parquet inmutable, un archivo por snapshot de
origen: ``root/year=YYYY/month=MM/snap_<content_hash_source>.parquet``.
Idempotente por archivo (ADR-0006). Partición mensual (los TLE cambian a
cadencia horaria/diaria, no por segundo como ADS-B).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from titan_eye.catalog.orbital import OrbitalElement
from titan_eye.core.errors import CatalogError

_ARROW_SCHEMA = pa.schema([
    pa.field("norad_cat_id", pa.int64(), nullable=False),
    pa.field("object_name", pa.string(), nullable=True),
    pa.field("intl_designator", pa.string(), nullable=True),
    pa.field("line1", pa.string(), nullable=False),
    pa.field("line2", pa.string(), nullable=False),
    pa.field("epoch", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("inclination_deg", pa.float64(), nullable=False),
    pa.field("raan_deg", pa.float64(), nullable=False),
    pa.field("eccentricity", pa.float64(), nullable=False),
    pa.field("arg_perigee_deg", pa.float64(), nullable=False),
    pa.field("mean_anomaly_deg", pa.float64(), nullable=False),
    pa.field("mean_motion_rev_per_day", pa.float64(), nullable=False),
    pa.field("content_hash_source", pa.string(), nullable=False),
    pa.field("tle_content_hash", pa.string(), nullable=False),
    pa.field("epistemic_label", pa.string(), nullable=False),
    pa.field("schema_version", pa.string(), nullable=False),
])
_COLUMNS = [f.name for f in _ARROW_SCHEMA]


class OrbitalElementsRepository:
    """Repositorio Parquet+DuckDB para `orbital_elements` (Normalized, orbital)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def insert_snapshot(self, elements: list[OrbitalElement]) -> bool:
        if not elements:
            return False
        hashes = {e.content_hash_source for e in elements}
        if len(hashes) != 1:
            raise CatalogError(
                f"insert_snapshot requiere elementos de un único Raw; vi {len(hashes)}"
            )
        path = self._snapshot_path(elements[0])
        if path.exists():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        pq.write_table(self._to_arrow(elements), tmp, compression="zstd")
        tmp.replace(path)
        return True

    def count(self) -> int:
        if not self._has_any():
            return 0
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM read_parquet('{self._glob()}', hive_partitioning=false)"
            ).fetchone()
        return int(row[0]) if row else 0

    def iter_all(self) -> Iterator[OrbitalElement]:
        if not self._has_any():
            return
        with self._connect() as conn:
            tbl = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM "
                f"read_parquet('{self._glob()}', hive_partitioning=false)"
            ).to_arrow_table()
        for rec in tbl.to_pylist():
            yield OrbitalElement.model_validate(rec)

    def find_by_norad(self, norad_cat_id: int) -> list[OrbitalElement]:
        if not self._has_any():
            return []
        with self._connect() as conn:
            tbl = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM "
                f"read_parquet('{self._glob()}', hive_partitioning=false) "
                "WHERE norad_cat_id = ? ORDER BY epoch DESC",
                [norad_cat_id],
            ).to_arrow_table()
        return [OrbitalElement.model_validate(r) for r in tbl.to_pylist()]

    def _snapshot_path(self, element: OrbitalElement) -> Path:
        ts = element.epoch.astimezone(UTC)
        return (
            self.root / f"year={ts.year}" / f"month={ts.month:02d}"
            / f"snap_{element.content_hash_source}.parquet"
        )

    def _glob(self) -> str:
        return str(self.root / "**" / "*.parquet").replace("\\", "/")

    def _has_any(self) -> bool:
        return any(self.root.rglob("*.parquet"))

    def _connect(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(database=":memory:")
        conn.execute("SET TimeZone='UTC'")
        return conn

    def _to_arrow(self, elements: list[OrbitalElement]) -> pa.Table:
        cols: dict[str, list] = {name: [] for name in _COLUMNS}
        for e in elements:
            d = e.model_dump()
            d["epistemic_label"] = e.epistemic_label.value
            for name in _COLUMNS:
                cols[name].append(d[name])
        return pa.table(cols, schema=_ARROW_SCHEMA)
