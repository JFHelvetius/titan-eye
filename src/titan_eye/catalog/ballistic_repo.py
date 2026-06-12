"""Repositorio Parquet+DuckDB de trayectorias balísticas (ADR-0008/0011).

A diferencia de la propagación orbital (masiva, on-demand), una
`BallisticTrajectory` es un Derived **raro y valioso**: un evento, no millones de
muestras. Su pérdida rompería el registro histórico, así que se persiste
(justificación de ADR-0006/0011).

Identidad content-addressable: `traj_<content_hash>` donde el hash cubre el
contenido semántico de la trayectoria (incluye el FK al reporte + el modelo). Las
listas anidadas (`arc`, `launch`, `impact`) se serializan como JSON en una columna.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from titan_eye.catalog.ballistic import BallisticTrajectory
from titan_eye.core.identity import content_hash_obj

_ARROW_SCHEMA = pa.schema([
    pa.field("event_id", pa.string(), nullable=False),
    pa.field("trajectory_hash", pa.string(), nullable=False),
    pa.field("arc_json", pa.string(), nullable=False),
    pa.field("launch_json", pa.string(), nullable=False),
    pa.field("impact_json", pa.string(), nullable=False),
    pa.field("apogee_km", pa.float64(), nullable=False),
    pa.field("range_km", pa.float64(), nullable=False),
    pa.field("semi_major_axis_km", pa.float64(), nullable=False),
    pa.field("eccentricity", pa.float64(), nullable=False),
    pa.field("band_km", pa.float64(), nullable=False),
    pa.field("impact_dispersion_km", pa.float64(), nullable=False),
    pa.field("model_name", pa.string(), nullable=False),
    pa.field("model_uncertainty_km", pa.float64(), nullable=False),
    pa.field("content_hash_source", pa.string(), nullable=False),
    pa.field("epistemic_label", pa.string(), nullable=False),
    pa.field("schema_version", pa.string(), nullable=False),
])


def trajectory_hash(t: BallisticTrajectory) -> str:
    """Hash content-addressable de la trayectoria (FK reporte + modelo + geometría)."""
    return content_hash_obj(t.model_dump(mode="json"))


class BallisticTrajectoryRepository:
    """Repositorio Parquet para trayectorias balísticas. Un archivo por trayectoria."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def insert(self, trajectory: BallisticTrajectory) -> bool:
        """Persiste la trayectoria. Idempotente por hash. True si escribió."""
        h = trajectory_hash(trajectory)
        path = self.root / f"traj_{h}.parquet"
        if path.exists():
            return False
        tmp = path.with_suffix(".tmp")
        pq.write_table(self._to_arrow(trajectory, h), tmp, compression="zstd")
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

    def iter_all(self) -> Iterator[BallisticTrajectory]:
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

    def _to_arrow(self, t: BallisticTrajectory, h: str) -> pa.Table:
        return pa.table({
            "event_id": [t.event_id],
            "trajectory_hash": [h],
            "arc_json": [json.dumps(t.arc, separators=(",", ":"))],
            "launch_json": [json.dumps(t.launch, separators=(",", ":"))],
            "impact_json": [json.dumps(t.impact, separators=(",", ":"))],
            "apogee_km": [t.apogee_km],
            "range_km": [t.range_km],
            "semi_major_axis_km": [t.semi_major_axis_km],
            "eccentricity": [t.eccentricity],
            "band_km": [t.band_km],
            "impact_dispersion_km": [t.impact_dispersion_km],
            "model_name": [t.model_name],
            "model_uncertainty_km": [t.model_uncertainty_km],
            "content_hash_source": [t.content_hash_source],
            "epistemic_label": [t.epistemic_label.value],
            "schema_version": [t.schema_version],
        }, schema=_ARROW_SCHEMA)


def _from_record(rec: dict) -> BallisticTrajectory:
    return BallisticTrajectory(
        event_id=rec["event_id"],
        arc=json.loads(rec["arc_json"]),
        launch=json.loads(rec["launch_json"]),
        impact=json.loads(rec["impact_json"]),
        apogee_km=rec["apogee_km"],
        range_km=rec["range_km"],
        semi_major_axis_km=rec["semi_major_axis_km"],
        eccentricity=rec["eccentricity"],
        band_km=rec["band_km"],
        impact_dispersion_km=rec["impact_dispersion_km"],
        model_name=rec["model_name"],
        model_uncertainty_km=rec["model_uncertainty_km"],
        content_hash_source=rec["content_hash_source"],
        schema_version=rec["schema_version"],
    )
