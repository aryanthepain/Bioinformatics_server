"""Stoichiometry and oligomeric assembly state models."""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field


class AssemblyType(str, Enum):
    """Classification of quaternary arrangement."""
    MONOMER = "MONOMER"
    HOMOMER = "HOMOMER"
    HETEROMER = "HETEROMER"
    UNCHARACTERIZED = "UNCHARACTERIZED"


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
