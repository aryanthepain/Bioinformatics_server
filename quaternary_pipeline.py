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
    ConflictRecord,
    EvidenceCoverage,
    EvidenceStatus,
    ExperimentalConflict,
    FunctionalComplex,
    InferredFunction,
    InterfaceContact,
    MultimerConfidence,
    ObservedAssembly,
    PisaConfidence,
    QuaternaryStructureOutput,
    ResidueRange,
    StageResult,
    StageStatus,
    Stoichiometry,
    SwissModelConfidence,
    TargetSelfAssembly,
)
from quaternary.session import QuaternarySession


def analyze_quaternary(
    target_input: str,
    config: Optional[QuaternaryConfig] = None,
    enable_multimer: bool = True,
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
    "EvidenceStatus",
    "TargetSelfAssembly",
    "FunctionalComplex",
    "ObservedAssembly",
    "InferredFunction",
    "EvidenceCoverage",
    "Stoichiometry",
    "ResidueRange",
    "InterfaceContact",
    "ConflictRecord",
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


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Quaternary Pipeline: Characterize protein quaternary structure and biological assemblies."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--accession",
        type=str,
        help="Target UniProt accession code (e.g. P0A6F5, P01308)",
    )
    group.add_argument(
        "--fasta",
        type=str,
        help="Path to FASTA file or raw sequence to characterize",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="quaternary_output.json",
        help="Filepath to write the synthesized JSON output (default: quaternary_output.json)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print progress and summary output to stdout",
    )
    args = parser.parse_args()

    target = args.accession
    if args.fasta:
        fasta_path = Path(args.fasta)
        if fasta_path.is_file():
            target = fasta_path.read_text(encoding="utf-8").strip()
        else:
            target = args.fasta

    if args.verbose:
        print(f"[*] Starting quaternary structure analysis for target: {target}")

    result = analyze_quaternary(target)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    print(f"[OK] Quaternary analysis complete. Saved to: {out_path.resolve()}")
    if args.verbose:
        print(f"     - Accession: {result.target_accession_or_sequence}")
        print(f"     - Quaternary Status: {result.quaternary_status}")
        if result.stoichiometry:
            print(f"     - Stoichiometry Formula: {result.stoichiometry.formula}")
            print(f"     - Total Subunits: {result.stoichiometry.total_subunits}")
            print(f"     - Symmetry: {result.stoichiometry.symmetry}")
            atype = result.stoichiometry.assembly_type
            print(f"     - Assembly Type: {atype.value if hasattr(atype, 'value') else atype}")
        if result.target_self_assembly:
            conf = result.target_self_assembly.confidence_status
            print(f"     - Confidence Status: {conf.value if hasattr(conf, 'value') else conf}")
        if result.confidence_provenance and result.confidence_provenance.alphafold_db:
            print(f"     - AlphaFold pLDDT: {result.confidence_provenance.alphafold_db.global_plddt}")

