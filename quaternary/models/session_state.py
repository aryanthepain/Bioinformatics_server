"""State tracking models for step-wise session execution and final output."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from quaternary.models.conflict import ExperimentalConflict
from quaternary.models.interface import InterfaceContact
from quaternary.models.provenance import ConfidenceProvenance
from quaternary.models.stoichiometry import Stoichiometry


class StageStatus(str, Enum):
    """Execution status for an individual analysis stage."""
    SUCCESS = "SUCCESS"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"


class StageResult(BaseModel):
    """Captured result and provenance for an individual analysis stage."""

    stage_number: int
    stage_name: str
    status: StageStatus = StageStatus.PENDING
    data: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class QuaternaryStructureOutput(BaseModel):
    """Canonical data contract for quaternary structure synthesis and UI export."""

    analysis_id: str
    target_accession_or_sequence: str
    quaternary_status: str
    stoichiometry: Stoichiometry
    interfaces: List[InterfaceContact] = Field(default_factory=list)
    experimental_conflict: ExperimentalConflict = Field(default_factory=ExperimentalConflict)
    confidence_provenance: ConfidenceProvenance = Field(default_factory=ConfidenceProvenance)
    stages_completed: List[int] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
