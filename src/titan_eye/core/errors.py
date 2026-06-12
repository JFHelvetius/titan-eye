"""Jerarquía de errores tipados de Titan Eye.

Todo error del sistema desciende de `TitanEyeError`. Los errores llevan,
cuando aplica, contexto suficiente para localizar la causa (fuente, línea,
campo) sin filtrar secretos ni payloads completos.

La jerarquía espeja la arquitectura de planos (ADR-0001): cada plano define
su rama de error, y los planos superiores capturan/encadenan los inferiores
sin aplanar la causa raíz (ADR-0000 P2: honestidad sobre lo que falló).
"""

from __future__ import annotations


class TitanEyeError(Exception):
    """Raíz de toda la jerarquía de errores del proyecto."""


# ── Ingestión ────────────────────────────────────────────────────────────
class IngestionError(TitanEyeError):
    """Fallo al adquirir, transportar o cachear un artefacto crudo."""


class TransportError(IngestionError):
    """Fallo de red/transporte al contactar una fuente pública."""


class SourceContractError(IngestionError):
    """La respuesta de una fuente no cumple su contrato declarado
    (formato, esquema, cabeceras de procedencia esperadas)."""


# ── Normalización / catálogo ─────────────────────────────────────────────
class NormalizationError(TitanEyeError):
    """Fallo al transformar un artefacto crudo a un modelo normalizado."""

    def __init__(self, message: str, *, source_hash: str | None = None,
                 line: int | None = None, column: int | None = None) -> None:
        super().__init__(message)
        self.source_hash = source_hash
        self.line = line
        self.column = column


class CatalogError(TitanEyeError):
    """Fallo al persistir/leer una capa del catálogo (Raw/Normalized/Derived)."""


# ── Analítica / propagación ──────────────────────────────────────────────
class AnalyticsError(TitanEyeError):
    """Fallo en una capa derivada (propagación, agregación, geometría)."""


class PropagationError(AnalyticsError):
    """Fallo al propagar una trayectoria (orbital SGP4, balística, gran círculo)."""


# ── Procedencia / integridad ─────────────────────────────────────────────
class ProvenanceError(TitanEyeError):
    """Fallo en la cadena de procedencia content-addressable."""


class IntegrityError(ProvenanceError):
    """Una invariante de integridad referencial o de hash no se cumple."""
