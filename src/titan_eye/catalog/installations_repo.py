"""Repositorio Parquet+DuckDB de la capa de referencia de instalaciones (ADR-0008/0017).

Un archivo por snapshot de origen: ``root/snap_<content_hash_source>.parquet``.
Las instalaciones son estáticas (sin partición temporal). Idempotente por archivo.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from titan_eye.catalog.installations import Installation
from titan_eye.core.errors import CatalogError

_ARROW_SCHEMA = pa.schema([
    pa.field("installation_id", pa.string(), nullable=False),
    pa.field("name", pa.string(), nullable=False),
    pa.field("latitude", pa.float64(), nullable=False),
    pa.field("longitude", pa.float64(), nullable=False),
    pa.field("installation_type", pa.string(), nullable=False),
    pa.field("category", pa.string(), nullable=False),
    pa.field("country", pa.string(), nullable=True),
    pa.field("source", pa.string(), nullable=False),
    pa.field("source_url", pa.string(), nullable=False),
    pa.field("notes", pa.string(), nullable=False),
    pa.field("content_hash_source", pa.string(), nullable=False),
    pa.field("epistemic_label", pa.string(), nullable=False),
    pa.field("schema_version", pa.string(), nullable=False),
])
_COLUMNS = [f.name for f in _ARROW_SCHEMA]


class InstallationsRepository:
    """Repositorio Parquet+DuckDB para `installations` (capa de referencia)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def insert_snapshot(self, items: list[Installation]) -> bool:
        if not items:
            return False
        hashes = {i.content_hash_source for i in items}
        if len(hashes) != 1:
            raise CatalogError(
                f"insert_snapshot requiere instalaciones de un único Raw; vi {len(hashes)}"
            )
        path = self.root / f"snap_{items[0].content_hash_source}.parquet"
        if path.exists():
            return False
        tmp = path.with_suffix(".tmp")
        pq.write_table(self._to_arrow(items), tmp, compression="zstd")
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

    def iter_all(self) -> Iterator[Installation]:
        if not self._has_any():
            return
        with self._connect() as conn:
            tbl = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM "
                f"read_parquet('{self._glob()}', hive_partitioning=false)"
            ).to_arrow_table()
        for rec in tbl.to_pylist():
            yield Installation.model_validate(rec)

    def _glob(self) -> str:
        return str(self.root / "**" / "*.parquet").replace("\\", "/")

    def _has_any(self) -> bool:
        return any(self.root.rglob("*.parquet"))

    def _connect(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(database=":memory:")
        conn.execute("SET TimeZone='UTC'")
        return conn

    def _to_arrow(self, items: list[Installation]) -> pa.Table:
        cols: dict[str, list] = {name: [] for name in _COLUMNS}
        for it in items:
            d = it.model_dump()
            d["installation_type"] = it.installation_type.value
            d["category"] = it.category.value
            d["epistemic_label"] = it.epistemic_label.value
            for name in _COLUMNS:
                cols[name].append(d[name])
        return pa.table(cols, schema=_ARROW_SCHEMA)
