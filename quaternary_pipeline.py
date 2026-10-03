"""Quaternary Pipeline: Unified Public API Facade for Quaternary Structure Analysis.

This module provides the primary high-level entry point for interactive Jupyter
notebooks and external bioinformatic workflows, abstracting underlying database
clients, caching, rate-limiting, and multi-stage biological assembly qualification.

Quickstart:
    >>> import quaternary_pipeline as qp
    >>> engine = qp.QuaternaryEngine()
    >>> session = engine.create_session("P0A6F5")
    >>> session.run_stage_1_primary_evidence()
    >>> output = session.run_stage_6_synthesis()
    >>> print(session.to_ui(format="json"))
"""

from __future__ import annotations

from typing import Any, Optional

from quaternary.clients import (
    AlphaFoldClient,
    BaseBioClient,
    ComplexPortalClient,
    IntActClient,
    MultimerPredictorClient,
    PisaClient,
    RCSBSearchClient,
    SwissModelClient,
    UniProtClient,
)
from quaternary.config import QuaternaryConfig
from quaternary.engine import QuaternaryEngine
from quaternary.models import (
    AlphaFoldConfidence,
    AssemblyType,
    ConfidenceProvenance,
    ExperimentalConflict,
    InterfaceContact,
    MultimerConfidence,
    PisaConfidence,
    QuaternaryStructureOutput,
    ResidueRange,
    StageResult,
    StageStatus,
    Stoichiometry,
    SwissModelConfidence,
)
from quaternary.session import QuaternarySession


def analyze_quaternary(
    target_input: str,
    config: Optional[QuaternaryConfig] = None,
    enable_multimer: bool = False,
    hypothesis: Optional[str] = None,
    **kwargs: Any,
) -> QuaternaryStructureOutput:
    """Convenience one-liner executing full multi-stage quaternary analysis.

    Args:
        target_input: UniProt accession (e.g. 'P0A6F5') or raw amino acid sequence.
        config: Optional QuaternaryConfig instance.
        enable_multimer: Explicit opt-in for predictive multimer modeling (D-06).
        hypothesis: Multimer association hypothesis (e.g. 'A2', 'A4', 'AB').

    Returns:
        QuaternaryStructureOutput validated data model.
    """
    cfg = config or QuaternaryConfig(**kwargs)
    engine = QuaternaryEngine(cfg)
    return engine.analyze(
        target_input=target_input,
        enable_multimer=enable_multimer,
        hypothesis=hypothesis,
    )


__all__ = [
    # Top-Level Facade & Engine
    "QuaternaryEngine",
    "QuaternarySession",
    "QuaternaryConfig",
    "analyze_quaternary",
    # Domain Models
    "AssemblyType",
    "Stoichiometry",
    "ResidueRange",
    "InterfaceContact",
    "ExperimentalConflict",
    "PisaConfidence",
    "SwissModelConfidence",
    "AlphaFoldConfidence",
    "MultimerConfidence",
    "ConfidenceProvenance",
    "StageStatus",
    "StageResult",
    "QuaternaryStructureOutput",
    # Client Adapters
    "BaseBioClient",
    "UniProtClient",
    "ComplexPortalClient",
    "RCSBSearchClient",
    "PisaClient",
    "SwissModelClient",
    "IntActClient",
    "AlphaFoldClient",
    "MultimerPredictorClient",
]
