"""Stoichiometry and oligomeric assembly state models."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AssemblyType(str, Enum):
    """Classification of quaternary arrangement."""
    MONOMER = "MONOMER"
    HOMOMER = "HOMOMER"
    HETEROMER = "HETEROMER"
    UNCHARACTERIZED = "UNCHARACTERIZED"


class EvidenceStatus(str, Enum):
    """Tiered evidence status for quaternary structure and functional predictions."""
    CONFIRMED = "CONFIRMED"
    SUPPORTED = "SUPPORTED"
    PREDICTED = "PREDICTED"
    UNCHARACTERIZED = "UNCHARACTERIZED"
    CONFLICTING = "CONFLICTING"
    NO_EVIDENCE = "NO_EVIDENCE"


class TargetSelfAssembly(BaseModel):
    """Oligomeric state of the target protein alone (homomer or monomer)."""
    formula: str
    assembly_type: AssemblyType = AssemblyType.UNCHARACTERIZED
    subunit_count: int = 1
    symmetry: Optional[str] = None
    confidence_status: EvidenceStatus = EvidenceStatus.UNCHARACTERIZED


class FunctionalComplex(BaseModel):
    """Hetero-oligomeric functional machinery involving target and partner proteins."""
    name: str
    stoichiometry: str
    partner_uniprot_accessions: List[str] = Field(default_factory=list)
    partner_names: List[str] = Field(default_factory=list)
    complex_portal_id: Optional[str] = None
    evidence: str = ""

    from pydantic import field_validator

    @field_validator("partner_uniprot_accessions", mode="before")
    @classmethod
    def _normalize_accessions(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            return []
        res = []
        for item in v:
            if isinstance(item, dict):
                acc = item.get("identifier") or item.get("accession") or item.get("id") or ""
                if acc:
                    res.append(str(acc))
            elif item is not None:
                res.append(str(item))
        return res


class ObservedAssembly(BaseModel):
    """Specific biological or asymmetric assembly observed in an experimental structure."""
    pdb_id: str
    assembly_id: str
    stoichiometry: str
    biological_assembly_type: str
    conditions: Optional[str] = None
    is_target_self: bool = False
    delta_g_diss_kcal_mol: Optional[float] = None


class InferredFunction(BaseModel):
    """Biological and mechanistic functional inference derived from quaternary architecture."""
    molecular_function: str
    biological_process: str
    oligomeric_mechanism_hypothesis: str
    archetype_name: Optional[str] = None
    go_terms: List[Dict[str, str]] = Field(default_factory=list)
    functional_homologs: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    status: EvidenceStatus = EvidenceStatus.UNCHARACTERIZED


class EvidenceCoverage(BaseModel):
    """Audit of evidence databases queried and remaining evidence gaps."""
    databases_queried: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)


class Stoichiometry(BaseModel):
    """Symbolic and quantitative representation of oligomeric stoichiometry."""

    formula: str
    chains: Dict[str, int] = Field(default_factory=dict)
    total_subunits: int = 0
    assembly_type: AssemblyType = AssemblyType.UNCHARACTERIZED
    symmetry: Optional[str] = None

    @classmethod
    def from_formula(cls, formula: str, symmetry: Optional[str] = None) -> Stoichiometry:
        """Parse a stoichiometry formula string (e.g. 'A', 'A2', 'A2B2', 'A4B4C2') into a Stoichiometry object."""
        cleaned = formula.strip()
        if not cleaned or cleaned.upper() in ("UNKNOWN", "UNCHARACTERIZED", "NONE"):
            return cls(
                formula=cleaned or "UNCHARACTERIZED",
                chains={},
                total_subunits=0,
                assembly_type=AssemblyType.UNCHARACTERIZED,
                symmetry=symmetry,
            )

        pattern = re.compile(r"([A-Za-z]+)(\d*)")
        matches = pattern.findall(cleaned)

        if not matches:
            return cls(
                formula=cleaned,
                chains={},
                total_subunits=0,
                assembly_type=AssemblyType.UNCHARACTERIZED,
                symmetry=symmetry,
            )

        chains: Dict[str, int] = {}
        total = 0
        for chain_id, count_str in matches:
            count = int(count_str) if count_str else 1
            chains[chain_id] = chains.get(chain_id, 0) + count
            total += count

        # Determine assembly type
        if total == 1:
            assembly_type = AssemblyType.MONOMER
        elif len(chains) == 1:
            assembly_type = AssemblyType.HOMOMER
        elif len(chains) > 1:
            assembly_type = AssemblyType.HETEROMER
        else:
            assembly_type = AssemblyType.UNCHARACTERIZED

        return cls(
            formula=cleaned,
            chains=chains,
            total_subunits=total,
            assembly_type=assembly_type,
            symmetry=symmetry,
        )
