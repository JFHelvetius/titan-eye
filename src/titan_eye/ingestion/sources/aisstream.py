"""Adaptador de AISStream.io (buques en vivo vía AIS, dominio marítimo).

AISStream es un stream **WebSocket** de mensajes AIS en tiempo real. Es **gratis**
pero requiere un **token de registro** (no es de pago): se lee de los secrets de
Streamlit / variable de entorno, NUNCA se hardcodea (ADR de secretos).

Como el resto del panel trabaja con "snapshots", esta fuente se conecta, recoge
mensajes durante unos segundos y se desconecta, devolviendo un RawArtifact
`observed` con la última posición por MMSI (en el formato que ya entiende
`normalizers/ais.py`). Honestidad (ADR-0015): AIS es autodeclarado y falsificable;
los buques de guerra lo apagan y los submarinos sumergidos no transmiten.

Referencia: https://aisstream.io/documentation
"""

from __future__ import annotations

import json
from typing import Any

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.timebase import Clock, SystemClock
from titan_eye.ingestion.artifact import RawArtifact

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"
AISSTREAM_SOURCE_ID = "aisstream.v0"
AISSTREAM_LICENSE_NOTE = (
    "AISStream.io — AIS en tiempo real, gratis con registro (token). "
    "AIS autodeclarado y falsificable (ADR-0015)."
)
# NavigationalStatus AIS -> etiqueta legible (subconjunto habitual).
_NAV_STATUS = {
    0: "en navegación (motor)", 1: "fondeado", 2: "sin gobierno",
    3: "maniobrabilidad restringida", 5: "amarrado", 7: "pescando",
    8: "en navegación (vela)",
}


def aisstream_message_to_vessel(msg: Any) -> dict | None:
    """Transforma un mensaje AISStream PositionReport en una fila para normalize_ais.

    Pura y testeable (sin red). Devuelve None si el mensaje no es una posición
    utilizable."""
    if not isinstance(msg, dict) or msg.get("MessageType") != "PositionReport":
        return None
    meta = msg.get("MetaData") or {}
    report = (msg.get("Message") or {}).get("PositionReport") or {}
    mmsi = meta.get("MMSI") or report.get("UserID")
    lat = meta.get("latitude", report.get("Latitude"))
    lon = meta.get("longitude", report.get("Longitude"))
    if mmsi is None or lat is None or lon is None:
        return None
    heading = report.get("TrueHeading")
    if heading in (511, None):  # 511 = "no disponible" en AIS
        heading = None
    nav = report.get("NavigationalStatus")
    return {
        "mmsi": str(mmsi),
        "name": (str(meta.get("ShipName") or "").strip() or None),
        "latitude": float(lat),
        "longitude": float(lon),
        "course": _num(report.get("Cog")),
        "heading": _num(heading),
        "speed": _num(report.get("Sog")),
        "nav_status": _NAV_STATUS.get(nav) if isinstance(nav, int) else None,
    }


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


class AisStreamSource:
    """Fuente AISStream (WebSocket). El reloj es inyectable; la red no se testea."""

    def __init__(self, api_key: str, *, clock: Clock | None = None) -> None:
        if not api_key:
            raise ValueError("AisStreamSource requiere un api_key no vacío.")
        self.api_key = api_key
        self.clock = clock or SystemClock()

    def fetch_snapshot(
        self,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        seconds: float = 8.0,
        max_vessels: int = 800,
    ) -> RawArtifact:
        """Recoge mensajes AIS durante `seconds` y sella un RawArtifact `observed`.

        bbox = (lat_min, lat_max, lon_min, lon_max); None = todo el planeta."""
        import contextlib
        import time

        import websocket  # websocket-client (dep opcional, importada aquí)

        if bbox is None:
            boxes = [[[-90.0, -180.0], [90.0, 180.0]]]
        else:
            la0, la1, lo0, lo1 = bbox
            boxes = [[[la0, lo0], [la1, lo1]]]
        subscribe = {
            "APIKey": self.api_key,
            "BoundingBoxes": boxes,
            "FilterMessageTypes": ["PositionReport"],
        }
        now = self.clock.now()
        vessels: dict[str, dict] = {}
        ws = websocket.create_connection(AISSTREAM_URL, timeout=max(5.0, seconds))
        try:
            ws.send(json.dumps(subscribe))
            deadline = time.time() + seconds
            while time.time() < deadline and len(vessels) < max_vessels:
                ws.settimeout(max(0.2, deadline - time.time()))
                try:
                    raw = ws.recv()
                except Exception:  # timeout/cierre -> terminamos el snapshot
                    break
                try:
                    v = aisstream_message_to_vessel(json.loads(raw))
                except (ValueError, TypeError):
                    continue
                if v is not None:
                    vessels[v["mmsi"]] = v
        finally:
            with contextlib.suppress(Exception):
                ws.close()

        payload = json.dumps(
            {"time": now.timestamp(), "vessels": list(vessels.values())},
            separators=(",", ":"),
        ).encode("utf-8")
        return RawArtifact.seal(
            source_id=AISSTREAM_SOURCE_ID,
            domain=Domain.MARITIME,
            request_url=AISSTREAM_URL,
            fetched_at=now,
            payload=payload,
            media_type="application/json",
            epistemic_label=EpistemicLabel.OBSERVED,
            license_note=AISSTREAM_LICENSE_NOTE,
        )
