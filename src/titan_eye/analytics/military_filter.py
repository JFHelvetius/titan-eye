"""Clasificación heurística 'probablemente militar' para el dominio aéreo.

Honestidad (P9, ADR-0003): la POSICIÓN de una aeronave es `observed` (ADS-B). La
etiqueta «militar» que añade este módulo es una **inferencia heurística basada en
patrones públicos**, NO un dato verificado ni una afirmación de bando o amenaza.
Puede dar falsos positivos (un vuelo civil con un indicativo coincidente) y falsos
negativos (un vuelo militar con el transpondedor apagado o un indicativo neutro).
Ausencia ≠ inexistencia.

Es exactamente la técnica que usa la comunidad de seguimiento ADS-B (tar1090 /
readsb / militaryspotting): dos señales públicas y abiertas combinadas:

1. **Prefijo de indicativo (callsign).** Las fuerzas aéreas usan radio-callsigns
   con prefijos conocidos y documentados (p. ej. ``RCH`` = Reach, transporte de la
   USAF; ``RRR`` = Royal Air Force). No es secreto: aparece en cualquier feed ADS-B.
2. **Rango ICAO24 (dirección hex del transpondedor).** La OACI asigna bloques de
   direcciones por país, y dentro de varios países hay sub-bloques usados por
   aeronaves de Estado/militares. Es la misma lista que usa ``readsb`` para su flag
   ``is_military`` (pública en su código fuente).

Determinista, sin red.
"""

from __future__ import annotations

# ── 1) Prefijos de indicativo (callsign) → operador militar conocido ──────────
# Documentado y público; lista de los más frecuentes en Europa/OTAN + grandes
# fuerzas. Se compara por prefijo en mayúsculas, ignorando espacios.
MILITARY_CALLSIGN_PREFIXES: dict[str, str] = {
    "RCH": "USAF Air Mobility (Reach)",
    "RRR": "Royal Air Force",
    "ASCOT": "RAF (Ascot)",
    "CFC": "Royal Canadian Air Force",
    "CTM": "Armée de l'air (France · Cotam)",
    "FAF": "Armée de l'air (France)",
    "GAF": "Luftwaffe (Alemania)",
    "IAM": "Aeronautica Militare (Italia)",
    "AME": "Ejército del Aire (España)",
    "HOSPITAL": "MEDEVAC militar",
    "NATO": "OTAN/NATO",
    "MAGMA": "OTAN AWACS",
    "BART": "USAF",
    "DOOM": "USAF B-52",
    "NAF": "US Navy",
    "CNV": "US Navy (Convoy)",
    "VV": "US Navy",
    "VM": "US Marines",
    "PAT": "US Army (Priority Air Transport)",
    "BAF": "Belgian Air Force",
    "NOW": "Royal Netherlands AF",
    "PLF": "Polish Air Force",
    "HUAF": "Hungarian Air Force",
    "SVF": "Swedish Air Force",
    "NOAF": "Norwegian Air Force",
    "TUAF": "Turkish Air Force",
    "UAF": "Ukrainian Air Force",
    "RFF": "Russian Air Force",
    "JAF": "Japan ASDF",
    "ROF": "Republic of Korea AF",
    "IAF": "Israeli Air Force",
    "AIO": "Indian Air Force",
    "PAK": "Pakistan Air Force",
    "CHN": "PLA Air Force (China)",
}

# ── 2) Rangos ICAO24 (hex) usados por aeronaves militares/de Estado ───────────
# Subconjunto de la lista pública de readsb/dump1090 (`is_military`). Cada par es
# un rango [lo, hi] inclusivo de direcciones de 24 bits.
MILITARY_ICAO24_RANGES: tuple[tuple[int, int, str], ...] = (
    (0xADF7C8, 0xAFFFFF, "US"),
    (0x010070, 0x01008F, "Egipto"),
    (0x0A4000, 0x0A4FFF, "Argelia"),
    (0x33FF00, 0x33FFFF, "Italia"),
    (0x350000, 0x37FFFF, "España"),
    (0x3AA000, 0x3AFFFF, "Francia"),
    (0x3B7000, 0x3BFFFF, "Francia"),
    (0x3EA000, 0x3EBFFF, "Alemania"),
    (0x3F4000, 0x3FBFFF, "Alemania"),
    (0x43C000, 0x43CFFF, "Reino Unido"),
    (0x444000, 0x446FFF, "Austria/OTAN"),
    (0x44F000, 0x44FFFF, "Bélgica"),
    (0x457000, 0x457FFF, "Bulgaria"),
    (0x45F400, 0x45F4FF, "Dinamarca"),
    (0x468000, 0x4683FF, "Grecia"),
    (0x473C00, 0x473C0F, "Hungría"),
    (0x478100, 0x4781FF, "Noruega"),
    (0x480000, 0x480FFF, "Países Bajos"),
    (0x48D800, 0x48D87F, "Polonia"),
    (0x497C00, 0x497CFF, "Portugal"),
    (0x4B7000, 0x4B7FFF, "Suiza"),
    (0x4B8200, 0x4B82FF, "Turquía"),
    (0xC20000, 0xC3FFFF, "Canadá"),
    (0xE40000, 0xE41FFF, "Brasil"),
)


def _callsign_prefix_match(callsign: str | None) -> str | None:
    if not callsign:
        return None
    cs = callsign.strip().upper().replace(" ", "")
    for prefix, operator in MILITARY_CALLSIGN_PREFIXES.items():
        if cs.startswith(prefix):
            return operator
    return None


def _icao24_range_match(icao24: str | None) -> str | None:
    if not icao24:
        return None
    try:
        addr = int(icao24.strip(), 16)
    except ValueError:
        return None
    for lo, hi, country in MILITARY_ICAO24_RANGES:
        if lo <= addr <= hi:
            return f"rango ICAO24 mil ({country})"
    return None


def military_match(callsign: str | None, icao24: str | None) -> str | None:
    """Devuelve una razón corta si la aeronave parece militar, o None.

    Combina prefijo de indicativo y rango ICAO24. El indicativo es más específico,
    así que tiene prioridad en el texto de la razón."""
    by_callsign = _callsign_prefix_match(callsign)
    by_icao = _icao24_range_match(icao24)
    if by_callsign and by_icao:
        return f"{by_callsign} · {by_icao}"
    return by_callsign or by_icao
