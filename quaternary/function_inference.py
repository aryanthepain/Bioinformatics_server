"""Quaternary-to-Function Inference Engine with extensible archetypes and tiered confidence scoring."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from quaternary.models import (
    ConfidenceProvenance,
    ConflictRecord,
    EvidenceStatus,
    ExperimentalConflict,
    InferredFunction,
    InterfaceContact,
    ObservedAssembly,
    Stoichiometry,
    TargetSelfAssembly,
)

logger = logging.getLogger(__name__)


@dataclass
class MechanisticArchetype:
    """Pre-built or user-registered quaternary functional archetype."""

    name: str
    stoichiometry_pattern: str  # Regex pattern for formula (e.g. '^A14', '^A2$')
    symmetry_pattern: Optional[str] = None  # Regex pattern for symmetry (e.g. 'D7', 'C2')
    molecular_function: str = ""
    biological_process: str = ""
    mechanism_template: str = ""
    example_complexes: List[str] = field(default_factory=list)


class FunctionInferenceEngine:
    """Hybrid rule engine mapping quaternary geometry, symmetry, thermodynamics, and homologs to biological function."""

    def __init__(self) -> None:
        self.archetypes: Dict[str, MechanisticArchetype] = {}
        self._load_prebuilt_archetypes()

    def register_archetype(self, archetype: MechanisticArchetype) -> None:
        """Register a new mechanistic archetype into the inference engine."""
        self.archetypes[archetype.name] = archetype
        logger.debug(f"Registered functional archetype: {archetype.name}")

    def _load_prebuilt_archetypes(self) -> None:
        """Initialize canonical biophysical quaternary archetypes."""
        self.register_archetype(
            MechanisticArchetype(
                name="chaperonin_barrel",
                stoichiometry_pattern=r"^A14.*|^A7.*",
                symmetry_pattern=r"D7|C7",
                molecular_function="ATP-dependent protein folding chaperone",
                biological_process="Cellular protein refolding under stress conditions",
                mechanism_template="Double-ring tetradecameric cylindrical cavity enclosing misfolded polypeptide substrates during ATP hydrolysis cycles",
                example_complexes=["GroEL", "Cpn60", "Hsp60", "GroEL-GroES"],
            )
        )
        self.register_archetype(
            MechanisticArchetype(
                name="homodimer_regulatory",
                stoichiometry_pattern=r"^A2$",
                symmetry_pattern=r"C2|D2",
                molecular_function="DNA-binding transcription regulation or receptor signaling",
                biological_process="Transcriptional activation/repression and signal transduction",
                mechanism_template="Twofold symmetric dyad axis presenting paired DNA recognition helices or symmetrical catalytic dyad clefts",
                example_complexes=["bZIP transcription factors", "Nuclear receptors", "EcoRI"],
            )
        )
        self.register_archetype(
            MechanisticArchetype(
                name="ring_helicase_pore",
                stoichiometry_pattern=r"^A6$",
                symmetry_pattern=r"C6|D6|C3",
                molecular_function="ATP-dependent nucleic acid translocation or transmembrane pore transport",
                biological_process="DNA replication, transcription termination, or solute transport",
                mechanism_template="Hexameric torus enclosing nucleic acid or ion channel, coupling conformational ring pulsing to directional translocation",
                example_complexes=["MCM helicase", "DnaB", "Rho factor", "AAA+ ring proteases"],
            )
        )
        self.register_archetype(
            MechanisticArchetype(
                name="heterotetramer_allosteric",
                stoichiometry_pattern=r"^A2B2$",
                symmetry_pattern=r"C2|D2",
                molecular_function="Cooperative ligand transport and allosteric enzyme regulation",
                biological_process="Gas exchange, metabolic regulation, and cooperative allostery",
                mechanism_template="Heterotetrameric interface cross-talk communicating quaternary T-to-R state transitions upon ligand binding",
                example_complexes=["Hemoglobin", "Phosphofructokinase", "Lactate dehydrogenase"],
            )
        )
        self.register_archetype(
            MechanisticArchetype(
                name="icosahedral_nanocage",
                stoichiometry_pattern=r"^A24$|^A60$",
                symmetry_pattern=r"O|I|T",
                molecular_function="Iron storage, biomolecular compartmentalization, or viral capsid protection",
                biological_process="Mineral homeostasis and genome encapsulation",
                mechanism_template="High-symmetry hollow spherical shell sequestering reactive payloads or packaging viral genome",
                example_complexes=["Ferritin", "Viral capsids", "Encapsulins"],
            )
        )

    def match_archetype(
        self,
        formula: str,
        symmetry: Optional[str] = None,
    ) -> Optional[MechanisticArchetype]:
        """Match stoichiometry formula and optional symmetry against registered archetypes."""
        clean_formula = formula.strip().upper()
        clean_symm = symmetry.strip().upper() if symmetry else None

        for arch in self.archetypes.values():
            if re.search(arch.stoichiometry_pattern, clean_formula, re.IGNORECASE):
                if arch.symmetry_pattern and clean_symm:
                    if re.search(arch.symmetry_pattern, clean_symm, re.IGNORECASE):
                        return arch
                elif not arch.symmetry_pattern:
                    return arch
                else:
                    # Weak formula match without symmetry contradiction
                    return arch
        return None

    def infer_function(
        self,
        target_self_assembly: TargetSelfAssembly,
        interfaces: List[InterfaceContact],
        confidence_provenance: ConfidenceProvenance,
        go_terms: Optional[List[Dict[str, str]]] = None,
        function_text: Optional[str] = None,
        homologs: Optional[List[Dict[str, Any]]] = None,
    ) -> InferredFunction:
        """Synthesize quaternary architecture into an InferredFunction report with tiered confidence."""
        formula = target_self_assembly.formula
        symmetry = target_self_assembly.symmetry
        matched_arch = self.match_archetype(formula, symmetry)

        all_go = list(go_terms or [])
        all_homologs = list(homologs or [])
        clean_fn_text = (function_text or "").lower()

        # Check for unannotated / novel sequence
        is_unannotated = (
            formula.upper() in ("UNCHARACTERIZED", "UNKNOWN", "NONE")
            and not all_go
            and not clean_fn_text
            and not all_homologs
        )

        if is_unannotated:
            return InferredFunction(
                molecular_function="Uncharacterized molecular function",
                biological_process="Uncharacterized biological process",
                oligomeric_mechanism_hypothesis="Insufficient experimental or homology evidence to establish functional oligomeric mechanism",
                archetype_name=None,
                go_terms=[],
                functional_homologs=[],
                confidence=0.1,
                status=EvidenceStatus.UNCHARACTERIZED,
            )

        # 1. Base Evidence Tier (up to 0.40)
        score = 0.10  # Baseline prior
        has_experimental_pisa = (
            confidence_provenance.pdbe_pisa is not None
            and confidence_provenance.pdbe_pisa.dissociation_energy_kcal_mol is not None
            and confidence_provenance.pdbe_pisa.dissociation_energy_kcal_mol > 0
        )
        has_homology = (
            confidence_provenance.swissmodel is not None
            and (confidence_provenance.swissmodel.qmqe or 0.0) >= 0.70
        )

        if has_experimental_pisa:
            score += 0.30  # Total 0.40
        elif has_homology:
            score += 0.15  # Total 0.25

        # 2. Thermodynamic Corroboration (+0.30)
        favorable_interfaces = [
            i for i in interfaces
            if i.solvation_free_energy_kcal_mol < 0 and i.buried_surface_area_angstrom2 >= 1000.0
        ]
        if favorable_interfaces:
            score += 0.30
        elif any(i.solvation_free_energy_kcal_mol < 0 for i in interfaces):
            score += 0.15

        # 3. Functional / Annotation Concordance (+0.30)
        has_concordance = False
        if matched_arch:
            arch_keywords = set(matched_arch.molecular_function.lower().split() + matched_arch.biological_process.lower().split())
            text_to_check = clean_fn_text + " " + " ".join(t.get("name", "").lower() for t in all_go)
            if any(k in text_to_check for k in arch_keywords if len(k) > 4):
                has_concordance = True
                score += 0.30
            elif all_go or clean_fn_text:
                score += 0.15
        elif all_go or clean_fn_text:
            score += 0.20

        final_confidence = round(min(1.0, max(0.1, score)), 2)

        # Evidence status determination
        if final_confidence >= 0.80 and has_experimental_pisa:
            status = EvidenceStatus.CONFIRMED
        elif final_confidence >= 0.50:
            status = EvidenceStatus.SUPPORTED
        elif final_confidence >= 0.25:
            status = EvidenceStatus.PREDICTED
        else:
            status = EvidenceStatus.UNCHARACTERIZED

        if matched_arch:
            molecular_func = matched_arch.molecular_function
            bio_proc = matched_arch.biological_process
            mechanism = matched_arch.mechanism_template
            archetype_name = matched_arch.name
        else:
            archetype_name = None
            if target_self_assembly.subunit_count > 1:
                molecular_func = "Oligomeric enzyme or structural complex"
                bio_proc = "Multimeric cellular machinery"
                mechanism = f"Self-associating {formula} assembly providing multivalent interaction interfaces"
            else:
                molecular_func = "Monomeric enzyme or binding module"
                bio_proc = "Cellular biochemical pathway"
                mechanism = "Single polypeptide chain functional unit without permanent quaternary interfaces"

        observed_fn = clean_fn_text or (all_go[0]["name"] if all_go else "Unknown")
        supporting_ev: List[str] = []
        if archetype_name:
            supporting_ev.append(f"Mechanistic Archetype: {archetype_name}")
        if has_experimental_pisa:
            supporting_ev.append("Experimental PDBe PISA quaternary interface corroboration")
        if all_go:
            supporting_ev.append(f"Validated Gene Ontology: {all_go[0].get('name', 'GO annotation')}")

        return InferredFunction(
            molecular_function=molecular_func,
            biological_process=bio_proc,
            oligomeric_mechanism_hypothesis=mechanism,
            archetype_name=archetype_name,
            go_terms=all_go,
            functional_homologs=all_homologs,
            confidence=final_confidence,
            status=status,
            observed_function=observed_fn,
            predicted_function=molecular_func,
            quaternary_mechanism_hypothesis=mechanism,
            supporting_evidence=supporting_ev,
        )


    # Alias for synthesize
    synthesize = infer_function

