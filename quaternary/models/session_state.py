"""State tracking models for step-wise session execution and final output."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from quaternary.models.conflict import ConflictRecord, ExperimentalConflict
from quaternary.models.interface import InterfaceContact
from quaternary.models.provenance import ConfidenceProvenance
from quaternary.models.stoichiometry import (
    EvidenceCoverage,
    EvidenceStatus,
    FunctionalComplex,
    InferredFunction,
    ObservedAssembly,
    Stoichiometry,
    TargetSelfAssembly,
)


class StageStatus(str, Enum):
    """Execution status for an individual analysis stage."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    # Backward compatibility alias
    PENDING = "not_started"

    @classmethod
    def _missing_(cls, value: object):
        # Case-insensitive resolution so legacy uppercase works smoothly
        if isinstance(value, str):
            val_lower = value.lower()
            for member in cls:
                if member.value == val_lower or member.name.lower() == val_lower:
                    return member
        return super()._missing_(value)


class StageResult(BaseModel):
    """Captured result and provenance for an individual analysis stage."""

    stage_number: int
    stage_name: str
    status: StageStatus = StageStatus.NOT_STARTED
    data: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None

    @property
    def details(self) -> Dict[str, Any]:
        """Convenience property alias to self.data."""
        return self.data


class QuaternaryStructureOutput(BaseModel):
    """Canonical data contract for quaternary structure synthesis and UI export."""

    analysis_id: str
    target_accession_or_sequence: str
    quaternary_status: str
    stoichiometry: Stoichiometry
    target_self_assembly: Optional[TargetSelfAssembly] = None
    functional_complexes: List[FunctionalComplex] = Field(default_factory=list)
    observed_assemblies: List[ObservedAssembly] = Field(default_factory=list)
    interfaces: List[InterfaceContact] = Field(default_factory=list)
    conflicts: List[ConflictRecord] = Field(default_factory=list)
    experimental_conflict: Optional[ExperimentalConflict] = Field(default_factory=ExperimentalConflict)
    confidence_provenance: ConfidenceProvenance = Field(default_factory=ConfidenceProvenance)
    inferred_function: Optional[InferredFunction] = None
    evidence_coverage: Optional[EvidenceCoverage] = None
    status: EvidenceStatus = EvidenceStatus.UNCHARACTERIZED
    experimental_oligomeric_state: Optional[str] = None
    predicted_oligomeric_state: Optional[str] = None
    fallback_representation: Optional[str] = None
    stages_completed: List[int] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

