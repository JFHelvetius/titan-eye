"""Modelo de la capa de referencia de instalaciones (ADR-0017).

NO es un dominio (no es actividad observable): es geografía de referencia estática
y pública, contexto sobre el que se leen los cinco dominios. Etiqueta `asserted`
(ubicación afirmada por fuente pública), que puede estar desactualizada o ser
aproximada (P2). El sistema no computa NADA operacional con estas instalaciones
(ADR-0017): solo las muestra como referencia, igual que un atlas público.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from titan_eye.core.epistemics import EpistemicLabel

INSTALLATION_SCHEMA_VERSION = "0.1.0"


class InstallationCategory(str, Enum):
    MILITARY = "military"
    CRITICAL_INFRASTRUCTURE = "critical_infrastructure"


class InstallationType(str, Enum):
    # Militar
    AIR_BASE = "air_base"
    NAVAL_BASE = "naval_base"
    ARMY_BASE = "army_base"
    MISSILE_SILO = "missile_silo"
    COMMAND_CENTER = "command_center"
    RADAR_SITE = "radar_site"
    STRATEGIC = "strategic"
    # Infraestructura crítica
    POWER_PLANT = "power_plant"
    NUCLEAR_PLANT = "nuclear_plant"
    REFINERY = "refinery"
    PORT = "port"
    AIRPORT = "airport"
    DAM = "dam"
    OTHER = "other"


# Tipos que pertenecen a la categoría militar (el resto -> infraestructura crítica).
_MILITARY_TYPES = {
    InstallationType.AIR_BASE, InstallationType.NAVAL_BASE, InstallationType.ARMY_BASE,
    InstallationType.MISSILE_SILO, InstallationType.COMMAND_CENTER,
    InstallationType.RADAR_SITE, InstallationType.STRATEGIC,
}


def category_for(t: InstallationType) -> InstallationCategory:
    return (InstallationCategory.MILITARY if t in _MILITARY_TYPES
            else InstallationCategory.CRITICAL_INFRASTRUCTURE)


class Installation(BaseModel):
    """Instalación de referencia (estática, pública, asserted)."""

    model_config = ConfigDict(frozen=True)

    installation_id: str
    name: str
    latitude: float
    longitude: float
    installation_type: InstallationType = InstallationType.OTHER
    category: InstallationCategory = InstallationCategory.CRITICAL_INFRASTRUCTURE
    country: str | None = None

    source: str = ""
    source_url: str = ""
    notes: str = ""

    content_hash_source: str
    epistemic_label: EpistemicLabel = EpistemicLabel.ASSERTED
    schema_version: str = INSTALLATION_SCHEMA_VERSION
