"""Experimental conflict tracking and resolution models (enforcing D-03)."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ConflictRecord(BaseModel):
    """Structured record of conflict between sources regarding quaternary state."""

    source_a: str
    source_b: str
    stoichiometry_a: str
    stoichiometry_b: str
    rationale: str
    resolution: Optional[str] = None


class ExperimentalConflict(BaseModel):
    """Retains conflicting assertions between crystal packing, biological assembly, and PISA."""

    rcsb_author_assembly: Optional[str] = None
    rcsb_annotated_assembly: Optional[str] = None
    pisa_predicted_assembly: Optional[str] = None
    pisa_thermodynamic_state: Optional[str] = None
    dissociation_energy_kcal_mol: Optional[float] = None
    conflict_detected: bool = False
    conflict_rationale: Optional[str] = None
    discrepancy_type: Optional[str] = None
