"""Wrapper del globo Cesium de Titan Eye.

Misma arquitectura validada en Orbital Sentinel (ADR-0004): el HTML real del
globo vive en `docs/cesium/index.html` y se sirve desde GitHub Pages con un
origin real. Un wrapper Streamlit lo carga en un `<iframe>` y le pasa el payload
multidominio por `window.postMessage`, esquivando el bloqueo de Workers
cross-origin que sufre el `srcdoc` de los componentes de Streamlit.

Hasta que GitHub Pages esté activo para el repo, el iframe muestra el mensaje de
espera (igual que Orbital Sentinel antes de su primer deploy). Configura la URL
con la variable de entorno `TITAN_EYE_PAGES_URL` si tu usuario/repo difieren.
"""

from __future__ import annotations

import json
import os
from typing import Any

# URL de GitHub Pages donde vive el HTML real. Override por env var.
_PAGES_URL = os.environ.get(
    "TITAN_EYE_PAGES_URL",
    "https://jfhelvetius.github.io/titan-eye/cesium/",
)

# Cache buster — incrementar al cambiar docs/cesium/index.html para invalidar
# el CDN de GitHub Pages.
_CACHE_BUSTER = "2026.06.14.5"


def html(payload: dict[str, Any], *, height: int = 880) -> str:
    """Genera el wrapper HTML que carga el iframe y le inyecta el payload.

    `payload` es el contrato de render del globo (ADR-0004):
        {
          "domains": {
            "orbital":    [ {id, name, lon, lat, alt_km, incl, period_min, track, err_km, owner}, ... ],
            "aerial":     [ {id, callsign, lon, lat, alt_km, heading, speed_kt, age_s, origin}, ... ],
            "suborbital": [ {id, name, source, launch:[lon,lat], impact:[lon,lat],
                             arc:[[lon,lat,alt_km],...], apogee_km, range_km, band_km,
                             impact_dispersion_km}, ... ],
            "surface":    [ {id, name, lon, lat, source, event_type, date,
                             events_count, geoloc_res}, ... ],
          },
          "heatmap": [ {lon, lat, weight}, ... ],   # densidad de eventos REPORTADOS
          "layers":  { "orbital": True, ... },       # estado inicial de capas (opcional)
          "series":  { "<entity_key>": {"times":[iso...], "positions":[[lon,lat,alt_km],...]} },
          "clock":   { "start_iso", "stop_iso", "current_iso", "multiplier" },
        }

    Las claves de `series` deben coincidir con las que el globo asigna a cada
    entidad: `orb_<id>`, `air_<id>`, `sub_<id|name>`, `srf_<id|name>`.
    """
    payload_json = json.dumps(payload, separators=(",", ":"), allow_nan=False)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <style>
    html, body {{ margin:0; padding:0; overflow:hidden; background:#04060a;
      width:100%; height:100%; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
    #titan-frame {{ width:100%; height:100%; border:0; border-radius:14px; display:block; background:#04060a; }}
    .err {{ position:absolute; top:14px; left:14px; right:14px; padding:14px 18px; border-radius:8px;
      background:rgba(70,25,25,.95); color:#ffd6cf; border:1px solid rgba(230,57,70,.5);
      font-size:13px; line-height:1.5; display:none; }}
    .err.show {{ display:block; }}
    .err b {{ color:#ff9b8f; }}
    .err code {{ font-family:'JetBrains Mono',monospace; font-size:12px;
      background:rgba(0,0,0,.4); padding:1px 5px; border-radius:3px; }}
  </style>
</head>
<body>
  <iframe id="titan-frame" src="{_PAGES_URL}?v={_CACHE_BUSTER}" allow="fullscreen" loading="eager"></iframe>
  <div class="err" id="errMsg">
    <b>⚠ GitHub Pages no responde aún.</b><br>
    El iframe intentó cargar <code>{_PAGES_URL}</code> pero no obtuvo respuesta.<br>
    Activa GitHub Pages en el repo (<i>Settings → Pages → main + /docs</i>) o define
    <code>TITAN_EYE_PAGES_URL</code> apuntando a tu deploy.
  </div>
  <script>
    const PAYLOAD = {payload_json};
    const frame = document.getElementById('titan-frame');
    window.addEventListener('message', function(ev) {{
      if (ev.data && ev.data.type === 'titan-eye-ready') {{
        frame.contentWindow.postMessage({{ type: 'titan-eye-tracks', payload: PAYLOAD }}, '*');
      }}
    }});
    setTimeout(function() {{
      try {{ frame.contentWindow.postMessage({{ type: 'titan-eye-tracks', payload: PAYLOAD }}, '*'); }} catch (e) {{}}
    }}, 6000);
    let loaded = false;
    frame.addEventListener('load', function() {{ loaded = true; }});
    setTimeout(function() {{ if (!loaded) document.getElementById('errMsg').classList.add('show'); }}, 12000);
  </script>
</body>
</html>
"""
