"""Repositorio Parquet+DuckDB de la capa Normalized del dominio aéreo (ADR-0008).

Persiste `AircraftState` (ADR-0009) como Parquet inmutable. Layout:
``root/year=YYYY/month=MM/day=DD/snap_<content_hash_source>.parquet``, un
archivo por snapshot de origen, con todas las filas derivadas de ese Raw.

Inserción idempotente por archivo (ADR-0006): si el snapshot ya está, no-op.
Lectura via DuckDB read-only sobre el glob recursivo, con sesión en UTC (P1).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from titan_eye.catalog.aircraft import AircraftState
from titan_eye.core.errors import CatalogError

_ARROW_SCHEMA = pa.schema([
    pa.field("icao24", pa.string(), nullable=False),
    pa.field("callsign", pa.string(), nullable=True),
    pa.field("origin_country", pa.string(), nullable=True),
    pa.field("longitude", pa.float64(), nullable=True),
    pa.field("latitude", pa.float64(), nullable=True),
    pa.field("baro_altitude_m", pa.float64(), nullable=True),
    pa.field("geo_altitude_m", pa.float64(), nullable=True),
    pa.field("on_ground", pa.bool_(), nullable=False),
    pa.field("velocity_ms", pa.float64(), nullable=True),
    pa.field("true_track_deg", pa.float64(), nullable=True),
    pa.field("vertical_rate_ms", pa.float64(), nullable=True),
    pa.field("time_position", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("last_contact", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("last_contact_age_s", pa.float64(), nullable=True),
    pa.field("position_source", pa.string(), nullable=False),
    pa.field("squawk", pa.string(), nullable=True),
    pa.field("spi", pa.bool_(), nullable=False),
    pa.field("content_hash_source", pa.string(), nullable=False),
    pa.field("snapshot_time", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("epistemic_label", pa.string(), nullable=False),
    pa.field("schema_version", pa.string(), nullable=False),
])

_COLUMNS = [f.name for f in _ARROW_SCHEMA]


class AircraftStatesRepository:
    """Repositorio Parquet+DuckDB para `aircraft_states` (Normalized, aéreo)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ── Escritura ────────────────────────────────────────────────────
    def insert_snapshot(self, states: list[AircraftState]) -> bool:
        """Persiste todas las filas de un snapshot. Idempotente por archivo.

        Devuelve True si escribió, False si el snapshot ya existía. Todas las
        filas deben compartir `content_hash_source` y `snapshot_time` (provienen
        del mismo Raw)."""
        if not states:
            return False
        source_hashes = {s.content_hash_source for s in states}
        if len(source_hashes) != 1:
            raise CatalogError(
                "insert_snapshot requiere filas de un único Raw; vi "
                f"{len(source_hashes)} hashes distintos"
            )
        path = self._snapshot_path(states[0])
        if path.exists():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        table = self._to_arrow(states)
        tmp = path.with_suffix(".tmp")
        pq.write_table(table, tmp, compression="zstd")
        tmp.replace(path)
        return True

    # ── Lectura ──────────────────────────────────────────────────────
    def count(self) -> int:
        if not self._has_any():
            return 0
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM read_parquet('{self._glob()}', "
                "hive_partitioning=false)"
            ).fetchone()
        return int(row[0]) if row else 0

    def distinct_source_hashes(self) -> set[str]:
        if not self._has_any():
            return set()
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT content_hash_source FROM "
                f"read_parquet('{self._glob()}', hive_partitioning=false)"
            ).fetchall()
        return {r[0] for r in rows}

    def iter_all(self) -> Iterator[AircraftState]:
        if not self._has_any():
            return
        with self._connect() as conn:
            tbl = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM "
                f"read_parquet('{self._glob()}', hive_partitioning=false)"
            ).to_arrow_table()
        for rec in tbl.to_pylist():
            yield AircraftState.model_validate(rec)

    def find_by_icao24(self, icao24: str) -> list[AircraftState]:
        if not self._has_any():
            return []
        with self._connect() as conn:
            tbl = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM "
                f"read_parquet('{self._glob()}', hive_partitioning=false) "
                "WHERE icao24 = ? ORDER BY snapshot_time DESC",
                [icao24],
            ).to_arrow_table()
        return [AircraftState.model_validate(r) for r in tbl.to_pylist()]

    # ── Internos ─────────────────────────────────────────────────────
    def _snapshot_path(self, state: AircraftState) -> Path:
        ts = state.snapshot_time.astimezone(UTC)
        return (
            self.root / f"year={ts.year}" / f"month={ts.month:02d}" / f"day={ts.day:02d}"
            / f"snap_{state.content_hash_source}.parquet"
        )

    def _glob(self) -> str:
        return str(self.root / "**" / "*.parquet").replace("\\", "/")

    def _has_any(self) -> bool:
        return any(self.root.rglob("*.parquet"))

    def _connect(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(database=":memory:")
        conn.execute("SET TimeZone='UTC'")  # ADR-0008: UTC declarado, no TZ del SO
        return conn

    def _to_arrow(self, states: list[AircraftState]) -> pa.Table:
        cols: dict[str, list] = {name: [] for name in _COLUMNS}
        for s in states:
            d = s.model_dump()
            d["epistemic_label"] = s.epistemic_label.value
            for name in _COLUMNS:
                cols[name].append(d[name])
        return pa.table(cols, schema=_ARROW_SCHEMA)
