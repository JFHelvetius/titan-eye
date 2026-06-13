"""Repositorio Parquet+DuckDB de fichas país (ADR-0008/0021).

Un archivo por snapshot de origen: ``root/snap_<content_hash_source>.parquet``.
Las alianzas (lista) se serializan como JSON en una columna. Idempotente por archivo.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from titan_eye.catalog.country import CountryProfile
from titan_eye.core.errors import CatalogError

_ARROW_SCHEMA = pa.schema([
    pa.field("country", pa.string(), nullable=False),
    pa.field("iso_code", pa.string(), nullable=True),
    pa.field("region", pa.string(), nullable=True),
    pa.field("military_budget_usd", pa.float64(), nullable=True),
    pa.field("budget_year", pa.int64(), nullable=True),
    pa.field("active_personnel", pa.int64(), nullable=True),
    pa.field("reserve_personnel", pa.int64(), nullable=True),
    pa.field("alliances_json", pa.string(), nullable=False),
    pa.field("source", pa.string(), nullable=False),
    pa.field("source_url", pa.string(), nullable=False),
    pa.field("notes", pa.string(), nullable=False),
    pa.field("content_hash_source", pa.string(), nullable=False),
    pa.field("epistemic_label", pa.string(), nullable=False),
    pa.field("schema_version", pa.string(), nullable=False),
])


class CountryRepository:
    """Repositorio Parquet+DuckDB para `countries` (referencia)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def insert_snapshot(self, items: list[CountryProfile]) -> bool:
        if not items:
            return False
        hashes = {i.content_hash_source for i in items}
        if len(hashes) != 1:
            raise CatalogError(
                f"insert_snapshot requiere fichas de un único Raw; vi {len(hashes)}"
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

    def iter_all(self) -> Iterator[CountryProfile]:
        if not self._has_any():
            return
        with self._connect() as conn:
            tbl = conn.execute(
                f"SELECT * FROM read_parquet('{self._glob()}', hive_partitioning=false)"
            ).to_arrow_table()
        for rec in tbl.to_pylist():
            yield _from_record(rec)

    def _glob(self) -> str:
        return str(self.root / "**" / "*.parquet").replace("\\", "/")

    def _has_any(self) -> bool:
        return any(self.root.rglob("*.parquet"))

    def _connect(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(database=":memory:")
        conn.execute("SET TimeZone='UTC'")
        return conn

    def _to_arrow(self, items: list[CountryProfile]) -> pa.Table:
        cols: dict[str, list] = {f.name: [] for f in _ARROW_SCHEMA}
        for c in items:
            cols["country"].append(c.country)
            cols["iso_code"].append(c.iso_code)
            cols["region"].append(c.region)
            cols["military_budget_usd"].append(c.military_budget_usd)
            cols["budget_year"].append(c.budget_year)
            cols["active_personnel"].append(c.active_personnel)
            cols["reserve_personnel"].append(c.reserve_personnel)
            cols["alliances_json"].append(json.dumps(c.alliances, separators=(",", ":")))
            cols["source"].append(c.source)
            cols["source_url"].append(c.source_url)
            cols["notes"].append(c.notes)
            cols["content_hash_source"].append(c.content_hash_source)
            cols["epistemic_label"].append(c.epistemic_label.value)
            cols["schema_version"].append(c.schema_version)
        return pa.table(cols, schema=_ARROW_SCHEMA)


def _from_record(rec: dict) -> CountryProfile:
    return CountryProfile(
        country=rec["country"], iso_code=rec["iso_code"], region=rec["region"],
        military_budget_usd=rec["military_budget_usd"], budget_year=rec["budget_year"],
        active_personnel=rec["active_personnel"], reserve_personnel=rec["reserve_personnel"],
        alliances=json.loads(rec["alliances_json"]),
        source=rec["source"], source_url=rec["source_url"], notes=rec["notes"],
        content_hash_source=rec["content_hash_source"], schema_version=rec["schema_version"],
    )
