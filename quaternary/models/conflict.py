"""Experimental conflict tracking and resolution models (enforcing D-03)."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ExperimentalConflict(BaseModel):
    """Retains conflicting assertions between crystal packing, biological assembly, and PISA."""

    conflict_detected: bool = False
    rcsb_annotated_assembly: Optional[str] = None
    pisa_thermodynamic_state: Optional[str] = None
    dissociation_energy_kcal_mol: Optional[float] = None
    conflict_rationale: Optional[str] = None
