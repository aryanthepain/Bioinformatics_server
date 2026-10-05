"""Interface contacts and residue interaction models."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class ResidueRange(BaseModel):
    """Residue index range on a specific chain."""
    chain_id: str
    start: int
    end: int


class InterfaceContact(BaseModel):
    """Detailed biophysical and structural metrics for a pairwise interface."""

    chain_1: str
    chain_2: str
    buried_surface_area_angstrom2: float
    solvation_free_energy_kcal_mol: Optional[float] = None
    hydrogen_bonds_count: int = 0
    salt_bridges_count: int = 0
    interface_residues_chain_1: List[int] = Field(default_factory=list)
    interface_residues_chain_2: List[int] = Field(default_factory=list)
