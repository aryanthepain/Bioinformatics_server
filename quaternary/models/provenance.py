"""Confidence provenance models strictly segregating source metrics (enforcing D-08)."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class PisaConfidence(BaseModel):
    """Biophysical thermodynamic confidence from PDBe PISA."""
    dissociation_energy_kcal_mol: Optional[float] = None
    buried_surface_area_angstrom2: Optional[float] = None


class SwissModelConfidence(BaseModel):
    """Homology modeling confidence metrics from SWISS-MODEL."""
    qmqe: Optional[float] = None
    gmqe: Optional[float] = None
    coverage: Optional[float] = None


class AlphaFoldConfidence(BaseModel):
    """Monomeric coordinate confidence from AlphaFold DB."""
    global_plddt: Optional[float] = None


class MultimerConfidence(BaseModel):
    """Predictive multimer interface and complex confidence from AlphaFold-Multimer / ColabFold."""
    iptm: Optional[float] = None
    ptm: Optional[float] = None
    model_confidence: Optional[float] = None


class ConfidenceProvenance(BaseModel):
    """Segregated confidence metrics across all evidence sources.

    Strictly prohibits synthetic mathematical blending or weighted averaging of
    incommensurable biophysical and machine-learning scores (enforcing D-08).
    """

    pdbe_pisa: Optional[PisaConfidence] = None
    swissmodel: Optional[SwissModelConfidence] = None
    alphafold_db: Optional[AlphaFoldConfidence] = None
    alphafold_multimer: Optional[MultimerConfidence] = None


from enum import Enum


class ProvenanceSource(str, Enum):
    """Provenance origin tag for evidence records."""
    EXPERIMENTAL = "EXPERIMENTAL"
    DATABASE_DERIVED = "DATABASE-DERIVED"
    PREDICTED = "PREDICTED"
    HEURISTIC = "HEURISTIC"
    HARDCODED_BENCHMARK = "HARDCODED_BENCHMARK"

