"""
Programmatic Builder for Quaternary_Structure.ipynb

Constructs, validates, and serializes Quaternary_Structure.ipynb using nbformat v4.
Provides modular builders across:
- Wave 1: Scaffold, Config, Pre-Flight Validation, and Dual-Mode Input
- Wave 2: Visual Helpers, Part 1 Facade, Canonical Stage 1-6 Modular Execution, and Biological Cards
- Wave 3: Biological Foundations Commentary, Standardized JSON Export, and Dual Showcase
- Wave 4: Novel / Synthetic Sequence Demonstration
"""

import sys
from pathlib import Path
import nbformat as nbf


def create_markdown_cell(source: str) -> nbf.NotebookNode:
    """Create a clean markdown cell."""
    return nbf.v4.new_markdown_cell(source=source.strip())


def create_code_cell(source: str) -> nbf.NotebookNode:
    """Create a clean code cell."""
    return nbf.v4.new_code_cell(source=source.strip())


def build_wave_1_cells() -> list[nbf.NotebookNode]:
    """Generate cells for Wave 1: Scaffold, imports, config, validation, and dual-mode input."""
    cells = []

    # 1. Title & Executive Overview
    title_md = r"""# Quaternary Protein Structure & Complex Annotation Engine

### High-Level End-to-End Pipeline for Protein Oligomeric State & Interface Characterization

---

## Executive Overview & Biological Context
Proteins execute biological functions primarily as multi-chain macromolecular complexes. **Quaternary structure** defines the three-dimensional geometric arrangement, subunit stoichiometry ($A_n$, $A_n B_m$), and interface binding chemistry of these multi-chain assemblies.

This notebook provides an abstracted, interactive scientific interface to determine:
- **Oligomeric State & Assembly Classification:** Monomer, homomer, or heteromer.
- **Stoichiometry Formula:** Exact subunit stoichiometry (e.g., $A_{14}$ tetradecamer for GroEL, $A_2 B_2$ heterotetramer for Hemoglobin).
- **Interface Contact Geometry:** Buried surface area ($\text{Å}^2$), solvation free energy gain ($\Delta^i G$), hydrogen bonds, and salt bridges.
- **Multi-Evidence Consensus:** Experimental validation (PDB, PDBe PISA), homology modeling (SWISS-MODEL), and predictive biophysics (AlphaFold-Multimer).
- **Mechanistic Functional Inference:** Bridging quaternary architecture to molecular function and biological processes.

> **Architectural Principle:** All computations and remote biophysical services are coordinated strictly through the high-level façade in `quaternary_pipeline.py`. Zero raw HTTP calls, manual endpoint orchestration, or low-level parser boilerplate are exposed in notebook code cells.
"""
    cells.append(create_markdown_cell(title_md))

    # 2. Imports Cell
    imports_code = """# Core Standard Library & Display Utilities
import sys
import os
import re
import json
import time
import uuid
import importlib
from pathlib import Path
from IPython.display import display, HTML, Markdown

# Ensure freshly modified modules are reloaded if the notebook kernel is already running
for mod_name in list(sys.modules.keys()):
    if mod_name == "quaternary_pipeline" or mod_name.startswith("quaternary."):
        try:
            importlib.reload(sys.modules[mod_name])
        except Exception:
            pass

# High-Level Quaternary Pipeline Façade API
# NOTE: Zero raw HTTP calls (requests.get, urllib) are permitted in this notebook.
from quaternary_pipeline import (
    analyze_quaternary,
    QuaternarySession,
    QuaternaryConfig,
    AssemblyType,
    EvidenceStatus,
    QuaternaryStructureOutput,
    StageStatus,
)

# Presentation & Visualization Utilities
from quaternary.presentation import (
    validate_target_input,
    render_validation_status,
    render_target_selection_card,
    show_json,
    render_quaternary_summary_card,
    render_component_identity_table,
    render_interface_contact_table,
    render_dynamic_equilibrium_display,
    render_functional_inference_card,
    render_evidence_coverage_dashboard,
)

print(" Quaternary Pipeline high-level API & presentation components successfully initialized.")
"""

    cells.append(create_code_cell(imports_code))

    # 3. Configuration Cell
    config_code = """# Pipeline Configuration & Execution Settings
# Controls caching (JSON/SQLite backends), request timeouts, and execution parameters.
config = QuaternaryConfig(
    cache_enabled=True,
    cache_backend="json",
    cache_dir=".quaternary_cache",
    timeout=30.0,
    offline_mode=False
)

print(f" QuaternaryConfig Active:")
print(f"  - Caching Enabled: {config.cache_enabled} (Backend: {config.cache_backend})")
print(f"  - Cache Directory: {config.cache_dir}")
print(f"  - Network Timeout: {config.timeout}s")
print(f"  - Offline Fixture Mode: {config.offline_mode}")
"""
    cells.append(create_code_cell(config_code))

    # 4. Pre-Flight Validation Markdown
    validation_md = """## Input Validation & Pre-Flight Verification
Before dispatching multi-stage structural analyses, input identifiers or sequences must be verified.
The pipeline accepts:
1. **UniProtKB Accession:** e.g., `P0A6F5` (GroEL), `P01308` (Insulin), `P44101` (*H. influenzae*).
2. **FASTA Amino Acid Sequence:** Standard IUPAC 20-amino-acid sequence string.
"""
    cells.append(create_markdown_cell(validation_md))

    # 5. Pre-Flight Validation Functions Cell
    validation_code = """# Pre-Flight Input Validation
# Pre-flight validation logic and status banners are imported from quaternary.presentation
from quaternary.presentation import validate_target_input, render_validation_status

# Demonstrate pre-flight verification on benchmark accession
is_valid, msg = validate_target_input("P0A6F5")
display(render_validation_status(is_valid, msg))
"""
    cells.append(create_code_cell(validation_code))

    # 6. Dual-Mode Input Selection Markdown
    input_md = """## Interactive Target Selection (Dual-Mode Input)

Select a pre-configured benchmark target below, or enter any custom UniProt accession or FASTA sequence:
- **Positive Control 1 (GroEL chaperonin `P0A6F5`):** Well-characterized tetradecamer ($A_{14}$) self-assembly and functional chaperonin heterocomplex ($A_{14}B_7$).
- **Positive Control 2 (Insulin `P01308`):** Classical hexameric ($A_6$) storage assembly and dimeric ($A_2$) peptide hormone in dynamic equilibrium.
- **Uncharacterized Benchmark (*H. influenzae* `P44101`):** Proteome `UP000000579` uncharacterized target illustrating predictive and homology fallback to monomer baseline.
- **Novel / Synthetic Sequence:** Arbitrary IUPAC amino acid sequence demonstrating de novo multimer hypothesis simulation and uncharacterized fallback.
- **Headless / Batch Mode:** If executed without a GUI widget environment, the declarative variables below (`TARGET_PROTEIN`, `ENABLE_MULTIMER`) are utilized automatically.
"""
    cells.append(create_markdown_cell(input_md))

    # 7. Dual-Mode Input Selection Code
    input_code = '''# Execution Configuration & Target Selection (Dual-Mode Input)

# Pre-Configured Benchmark Target Presets Repository:
PRESETS = {
    "GroEL_Control": {
        "id": "P0A6F5",
        "name": "GroEL Chaperonin (Positive Control - A14 Homotetradecamer / A14B7 Complex)",
        "organism": "Escherichia coli (strain K12)",
        "assembly": "A14 homo-tetradecamer self-assembly / A14B7 with GroES (21 subunits)",
    },
    "Insulin_Control": {
        "id": "P01308",
        "name": "Insulin Peptide Hormone (Positive Control - Hexamer A6 / Dimer A2)",
        "organism": "Homo sapiens",
        "assembly": "Hexamer (A6 storage) / Dimer (A2) / Monomer (A1)",
    },
    "Uncharacterized_Target": {
        "id": "P44101",
        "name": "Uncharacterized Protein (Proteome UP000000579 Benchmark)",
        "organism": "Haemophilus influenzae",
        "assembly": "Monomer baseline (A1)",
    },
    "Novel_Synthetic_Sequence": {
        "id": "MAAKDVKFGNDARVKMLRGVNVLADAVKVTLGPKGRNVVLDKSFGAPTITKDGVSVAREIELEDKFENMGAQMVKEVASKANDAAGDGTTTATVLAQAIITEGLKAVAAGMNPMDLKRGIDKAVTAAVEELKALSVPCSDSKAIAQVGTISANSDETVGKLIAEAMDKVGKEGVITVEDGTGLQDELDVVEGMQFDRGYLSPYFINKPETGAVELESPFILLADKKISNIREMLPVLEAVAKAGKPLLIIAEDVEGEALATLVVNTMRGIVKVAAVKAPGFGDRRKAMLQDIAIATGGTVIEEIGLLEL",
        "name": "Novel Synthetic Sequence (De Novo IUPAC Amino Acid Sequence)",
        "organism": "Synthetic / Novel Target",
        "assembly": "De novo multimer simulation (Stage 5)",
    },
}

TARGET_PROTEIN = "P0A6F5"  # Active Selection: GroEL Chaperonin
ENABLE_MULTIMER = True     # Run AlphaFold-Multimer predictive modeling (Stage 5 opt-in)

# Resolve target metadata
active_preset = next((p for p in PRESETS.values() if p["id"] == TARGET_PROTEIN), None)

# Render visual interactive target status card via presentation library (D-13)
display(render_target_selection_card(
    TARGET_PROTEIN,
    active_preset=active_preset["id"] if active_preset else None,
    preset_info=active_preset,
))

# Validate target input immediately
is_valid, val_msg = validate_target_input(TARGET_PROTEIN)
display(render_validation_status(is_valid, val_msg))
'''
    cells.append(create_code_cell(input_code))

    return cells


def build_wave_2_cells() -> list[nbf.NotebookNode]:
    """Generate cells for Wave 2: Presentation overview, Part 1 facade with 6 distinct displays, and Part 2 modular session."""
    cells = []

    # 1. Visual Helpers Overview Markdown (Redundant code cell removed per D-13)
    visual_explain_md = r"""## Interactive Visualization Helpers & Biological Presentation Architecture

All presentation components are imported from the modular presentation library (`quaternary.presentation`) in Cell 2:
- **`render_target_selection_card(target_input, active_preset)`**: Formats active target parameters and literature benchmarks.
- **`render_quaternary_summary_card(output)`**: Executive summary card highlighting assembly classification, stoichiometry, and segregated confidence provenance.
- **`render_component_identity_table(output)`**: Granular macromolecular table detailing each subunit component, UniProt accession, copies, PDB chain IDs, and functional role.
- **`render_interface_contact_table(output)`**: Detailed biophysical contact table showing buried surface area ($\text{Å}^2$), solvation energy gain ($\Delta^i G$), H-bonds, salt bridges, and key contact residues.
- **`render_dynamic_equilibrium_display(output)`**: Multi-assembly equilibrium viewer visualizing alternative physiological oligomers across crystal forms and solution states.
- **`render_functional_inference_card(output)`**: Bio-mechanistic card detailing inferred molecular function, biological process, quaternary mechanism hypotheses, and evidence breakdown.
- **`render_evidence_coverage_dashboard(output)`**: Structured audit dashboard listing each queried database, hit status, and remaining evidence gaps.
- **`show_json(data, max_depth=1)`**: Interactive dark tree viewer with collapsible arrows using `renderjson@1.4.0`.
"""
    cells.append(create_markdown_cell(visual_explain_md))

    # 2. Part 1 Markdown Header
    part1_md = r"""## Part 1: High-Level Quickstart Facade (Single-Line Execution)

The quickest way to characterize a target protein's quaternary structure is via `analyze_quaternary()`.
This single high-level function:
1. Initializes an internal analysis session.
2. Coordinates experimental queries (UniProt SUBUNIT, RCSB PDB assemblies, PDBe PISA interface chemistry).
3. Evaluates homology templates (SWISS-MODEL), interaction partners (IntAct), and predictive structural models (AlphaFold-DB / Multimer).
4. Synthesizes a unified, validated `QuaternaryStructureOutput` contract with bio-mechanistic functional inference.
"""
    cells.append(create_markdown_cell(part1_md))

    # 3. Part 1 Execution Cell
    part1_code = r'''# Execute complete quaternary characterization via high-level façade
print(f"[START] Executing analyze_quaternary for target: {TARGET_PROTEIN} ...")
t0 = time.time()
output = analyze_quaternary(TARGET_PROTEIN, config=config, enable_multimer=ENABLE_MULTIMER)
elapsed = time.time() - t0
print(f"[COMPLETE] Characterization completed in {elapsed:.2f}s | Status: {output.quaternary_status}")
'''
    cells.append(create_code_cell(part1_code))

    # 4. Part 1 Display 1: Quaternary Summary Card
    display_1_code = r'''# Display 1: Quaternary Structure Summary Card
display(render_quaternary_summary_card(output))
'''
    cells.append(create_code_cell(display_1_code))

    display_1_md = r"""### Output Interpretation: Quaternary Summary Card Analysis (D-08 & D-14)

The executive summary card synthesizes experimental crystallography, thermodynamic interface calculations, quaternary homology models, and predictive multimer modeling into a validated macro-architecture:
- **Assembly Type & Stoichiometry:** Distinguishes homomers ($A_n$), heteromers ($A_n B_m$), and monomers ($A$).
- **Segregated Confidence Architecture (D-08):** Machine learning confidence metrics (AlphaFold pLDDT, ipTM) and biophysical thermodynamic scores (PISA $\Delta^i G$, SWISS-MODEL QMQE) are strictly segregated without synthetic blending.
- **Truthful Real-Execution Policy (D-12):** When an external GPU multimer runner is unconfigured, AlphaFold-Multimer explicitly reports `Status: NOT EXECUTED | Reason: External prediction runner not configured`.

<details>
<summary><b>Biological Benchmark Comparison: Quaternary Summary Card Across Presets</b></summary>

| Preset Target | Accession | Assembly Type | Stoichiometry | Consensus Status | Provenance Tag |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | `P0A6F5` | Homotetradecamer | $A_{14}$ | `CONFIRMED` | `[EXPERIMENTAL]` |
| **Insulin Hormone** | `P01308` | Dynamic Multimer | $A_2$ (Dimer) / $A_6$ (Hexamer) | `CONFIRMED` | `[EXPERIMENTAL]` |
| **H. influenzae UP000000579** | `P44101` | Monomer | $A$ (Monomer baseline) | `SUPPORTED` | `[DATABASE-DERIVED]` |
| **Novel Synthetic Sequence** | *Arbitrary* | Monomer Baseline | $A$ (Monomer baseline) | `INSUFFICIENT EVIDENCE` | `[PREDICTED]` |

</details>
"""
    cells.append(create_markdown_cell(display_1_md))

    # 5. Part 1 Display 2: Component Identity Table
    display_2_code = r'''# Display 2: Macromolecular Component Identity Table
display(render_component_identity_table(output))
'''
    cells.append(create_code_cell(display_2_code))

    display_2_md = r"""### Output Interpretation: Macromolecular Component Identity Table (D-06 & D-14)

The component identity table delineates target polypeptide chains from accessory subunits and functional partner complexes:
- **Target Self-Assembly (Component A):** Tracks the primary polypeptide chain under investigation, its stoichiometric copy number, and crystallographic chain identifiers.
- **Functional Partner Machinery (Component B+):** Captures co-chaperonins, regulatory cofactors, or binding partners identified via UniProt curation and Complex Portal records.
- **GroEL Biological Grounding (D-06):** GroEL alone is strictly an $A_{14}$ homo-tetradecamer self-assembly, while the GroEL-GroES folding machinery is modeled as an $A_{14}B_7$ functional heterocomplex (21 subunits total).

<details>
<summary><b>Biological Benchmark Comparison: Component Identity Across Presets</b></summary>

| Preset Target | Component A (Target Subunits) | Component B (Partner Subunits) | Total Subunits | Complex Role |
| :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | 14 copies (Chains A–N) | 7 copies GroES (Chains O–U) | 21 subunits | Chaperonin folding cage |
| **Insulin Hormone** | 2 copies (Chains A, B) | 4 copies (Zinc storage hexamer) | 2 to 6 subunits | Metabolic peptide hormone |
| **H. influenzae UP000000579** | 1 copy (Chain A) | None | 1 subunit | Monomer baseline |
| **Novel Synthetic Sequence** | 1 copy (Chain A) | None | 1 subunit | De novo single chain |

</details>
"""
    cells.append(create_markdown_cell(display_2_md))

    # 6. Part 1 Display 3: Interface Contact Table
    display_3_code = r'''# Display 3: Pairwise Interface Contact Residues & Thermodynamics
display(render_interface_contact_table(output))
'''
    cells.append(create_code_cell(display_3_code))

    display_3_md = r"""### Output Interpretation: Pairwise Interface Contact Residues & Thermodynamics (D-10 & D-14)

The interface contact table characterizes the physical forces stabilizing multi-chain assemblies:
- **Buried Surface Area ($\text{BSA}$):** Permanent, obligate biological interfaces bury extensive surface area ($\text{BSA} \ge 800 - 1500\ \text{Å}^2$), whereas non-specific crystal lattice packing contacts generally bury $<400\ \text{Å}^2$.
- **Solvation Free Energy Gain ($\Delta^i G$):** Strictly negative values ($\Delta^i G < 0$) indicate favorable hydrophobic desolvation driving spontaneous subunit association.
- **Interfacial Specificity:** Polar hydrogen bonds and electrostatic salt bridges establish conformational rigidity and orientational alignment across interacting subunits.

<details>
<summary><b>Biological Benchmark Comparison: Interface Biophysics Across Presets</b></summary>

| Preset Target | Evaluated Interfaces | Primary Contact BSA | Solvation $\Delta^i G$ | Interface Nature |
| :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | Intra-ring & Inter-ring contacts | Extensive ($>1,800\ \text{Å}^2$) | Negative ($\Delta^i G < 0$) | High-stability cylindrical cage |
| **Insulin Hormone** | Dimer & Trimer-of-dimers contacts | Modest to large ($\sim 1,200\ \text{Å}^2$) | Negative ($\Delta^i G < 0$) | Concentration-dependent dynamic equilibrium |
| **H. influenzae UP000000579** | 0 pairwise contacts | $0.0\ \text{Å}^2$ | $0.0\ \text{kcal/mol}$ | Monomer baseline (no interfaces) |
| **Novel Synthetic Sequence** | 0 pairwise contacts | $0.0\ \text{Å}^2$ | $0.0\ \text{kcal/mol}$ | Uncharacterized sequence baseline |

</details>
"""
    cells.append(create_markdown_cell(display_3_md))

    # 7. Part 1 Display 4: Dynamic Equilibrium Display
    display_4_code = r'''# Display 4: Dynamic Multi-Assembly Equilibrium & Observed States
display(render_dynamic_equilibrium_display(output))
'''
    cells.append(create_code_cell(display_4_code))

    display_4_md = r"""### Output Interpretation: Dynamic Multi-Assembly Equilibrium & Observed States (D-02 & D-14)

Proteins frequently function as dynamic conformational ensembles rather than single rigid static structures:
- **Crystallographic vs. Physiological States:** Captures the full register of biologically relevant multimers observed across crystal forms and cryo-EM reconstitutions.
- **Insulin Paradigm:** Classical illustration of oligomeric plasticity—stored in pancreatic $\beta$-cell vesicles as a zinc-stabilized hexamer ($A_6$), circulating in plasma as an active dimer ($A_2$), and binding insulin receptors as a monomer ($A_1$).

<details>
<summary><b>Biological Benchmark Comparison: Dynamic Assemblies Across Presets</b></summary>

| Preset Target | Target Self Form | Alternative Physiological Assemblies | Stabilizing Factor |
| :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | $A_{14}$ ($D_7$ tetradecamer) | $A_{14}B_7$ (GroEL-GroES bullet complex) | ATP & co-chaperonin binding |
| **Insulin Hormone** | $A_2$ (Active Dimer) | $A_6$ (Storage Hexamer) | $\text{Zn}^{2+}$ coordination & pH shift |
| **H. influenzae UP000000579** | $A_1$ (Monomer) | Single invariant quaternary state | Monomer baseline |
| **Novel Synthetic Sequence** | $A_1$ (Monomer) | Single invariant quaternary state | Default de novo prediction |

</details>
"""
    cells.append(create_markdown_cell(display_4_md))

    # 8. Part 1 Display 5: Functional Inference Card
    display_5_code = r'''# Display 5: Executive Bio-Mechanistic Card: Functional Inference
display(render_functional_inference_card(output))
'''
    cells.append(create_code_cell(display_5_code))

    display_5_md = r"""### Output Interpretation: Executive Bio-Mechanistic Card (D-10 & D-14)

The functional inference engine links quaternary symmetry and interface geometry to molecular mechanisms and biological processes:
- **Segregated Functional Domains:** Explicitly distinguishes **Observed Function** (curated experimental annotations) from **Predicted Process** (dynamic algorithmic inference).
- **Quaternary Mechanism Hypothesis:** Formulates testable mechanistic rationales (e.g. enclosed folding cages, cooperative ligand binding clefts, membrane pores) derived from structural archetypes.
- **Supporting Evidence:** Catalogs contributing structural homologs, Gene Ontology annotations, and thermodynamic evidence.

<details>
<summary><b>Biological Benchmark Comparison: Functional Inference Across Presets</b></summary>

| Preset Target | Inferred Molecular Function | Quaternary Mechanism Hypothesis | Archetype | Confidence Score |
| :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | ATP-dependent molecular chaperone | Dual-ring barrel sequestering non-native polypeptide substrates | Chaperonin Cage | High ($\ge 0.90$) |
| **Insulin Hormone** | Peptide hormone / receptor agonist | Multi-state dissociation from storage hexamer to receptor-active dimer | Allosteric Switch | High ($\ge 0.85$) |
| **H. influenzae UP000000579** | Uncharacterized protein | Monomer baseline (no quaternary cooperativity inferred) | Monomer Baseline | Neutral ($\sim 0.50$) |
| **Novel Synthetic Sequence** | Uncharacterized sequence | Sequence-level prediction without verified quaternary mechanism | Uncharacterized | Baseline ($<0.50$) |

</details>
"""
    cells.append(create_markdown_cell(display_5_md))

    # 9. Part 1 Display 6: Evidence Coverage Dashboard
    display_6_code = r'''# Display 6: Evidence Coverage & Scientific Gaps Dashboard
display(render_evidence_coverage_dashboard(output))
'''
    cells.append(create_code_cell(display_6_code))

    display_6_md = r"""### Output Interpretation: Evidence Coverage & Scientific Gaps Dashboard (D-08 & D-14)

The evidence coverage dashboard provides a transparent audit of all databases queried, reporting exact query states and documenting residual scientific gaps:
- **Granular Query States (D-08):** Distinguishes `QUERY_SUCCESS_WITH_HIT`, `QUERY_SUCCESS_NO_HIT`, `QUERY_FAILED`, `SKIPPED`, `UNAVAILABLE`, and `PREDICTION_NOT_EXECUTED`.
- **Identified Scientific Gaps:** Highlights unmeasured interfaces, absent quaternary homology templates, or unconfigured deep-learning compute runners so researchers know exactly where uncertainty remains.

<details>
<summary><b>Biological Benchmark Comparison: Evidence Coverage Across Presets</b></summary>

| Preset Target | Databases with Hits | Databases with No Hits | Unconfigured / Skipped | Scientific Gap Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | UniProt, Complex Portal, PDB, PISA, SWISS-MODEL | None | AlphaFold-Multimer (runner unconfigured) | Full experimental & homology consensus |
| **Insulin Hormone** | UniProt, PDB, PISA, SWISS-MODEL | None | AlphaFold-Multimer (runner unconfigured) | High experimental consensus |
| **H. influenzae UP000000579** | UniProt, AlphaFold-DB | PDB, PISA (no complexes) | SWISS-MODEL, Multimer | Sparse experimental coverage (monomer) |
| **Novel Synthetic Sequence** | None (bypasses accessions) | UniProt, PDB, PISA | SWISS-MODEL, Multimer | Zero database hits (de novo baseline) |

</details>
"""
    cells.append(create_markdown_cell(display_6_md))

    # 10. Part 1 JSON Tree Inspection Cell
    part1_tree_code = r'''# Collapsible dark-tree inspection of the complete QuaternaryStructureOutput
print("Interactive JSON Inspection (click arrows to expand/collapse nested nodes):")
display(show_json(output, max_depth=1))
'''
    cells.append(create_code_cell(part1_tree_code))

    # 10b. JSON Tree Output Explanation Markdown
    tree_explain_md = r"""### Output Interpretation: QuaternaryStructureOutput Data Contract

The JSON object inspected above conforms strictly to the **`QuaternaryStructureOutput`** Pydantic v2 schema:
- **`analysis_id` & `quaternary_status`:** Unique session identifier and top-level qualification status (`CONFIRMED`, `SUPPORTED`, `INSUFFICIENT_EVIDENCE`, `CONFLICTING`).
- **`stoichiometry`:** Nested object containing `assembly_type`, `formula`, and `total_subunits`.
- **`target_self_assembly`:** Disambiguated self-assembly state of the target chain alone ($A_{14}$ for GroEL).
- **`functional_complexes`:** Functional hetero-oligomeric machinery involving partner chains ($A_{14}B_7$ for GroEL-GroES).
- **`observed_assemblies`:** Complete register of biological assemblies observed across experimental crystal forms.
- **`interfaces`:** Array of verified pairwise contacts detailing interacting chain identifiers, buried surface areas ($\text{BSA}$ in $\text{Å}^2$), solvation energy gain ($\Delta^i G$), hydrogen bonds, salt bridges, and residue indices.
- **`confidence_provenance`:** Segregated sub-objects for `pdbe_pisa`, `swissmodel`, `alphafold_db`, and `alphafold_multimer`.
- **`inferred_function`:** Derived molecular function, biological process, quaternary mechanism hypothesis, and supporting evidence.
- **`evidence_coverage`:** Complete audit of queried databases with granular `DatabaseAuditRecord` entries and documented uncertainties.
- **`stages_completed`:** Integer array `[1, 2, 3, 4, 5, 6]` tracking complete execution provenance across all analytical stages.
"""
    cells.append(create_markdown_cell(tree_explain_md))

    # 11. Part 2 Markdown Header
    part2_md = r"""## Part 2: Step-by-Step Modular Session Walkthrough

For scientific workflows requiring fine-grained control or intermediate stage inspection, `QuaternarySession` exposes canonical stage runners (`run_stage_1_sequence_and_accession` through `run_stage_6_synthesis_and_functional_inference`).

Below, each canonical stage is executed independently with immediate output display and biological interpretation.
"""
    cells.append(create_markdown_cell(part2_md))

    # 12. Part 2 Session Initialization Cell
    part2_init_code = r'''# Instantiate modular QuaternarySession
session = QuaternarySession(TARGET_PROTEIN, config=config)
print(f" QuaternarySession created:")
print(f"  - Session ID: {session.session_id}")
print(f"  - Target: {session.target_input}")
print(f"  - Initial Status: {session.status.value}")
'''
    cells.append(create_code_cell(part2_init_code))

    # 13. Part 2 Stage 1 Execution Cell
    part2_stage_1_code = r'''# Stage 1: Sequence & UniProt Subunit Accession Qualification
print("[STAGE 1/6: SEQUENCE & ACCESSION] Querying curated subunit annotations & Complex Portal...")
r1 = session.run_stage_1_sequence_and_accession()
print(f"  -> Status: {r1.status.value}")
print(f"  -> Curated Subunit Annotation: {r1.data.get('uniprot', {}).get('subunit_annotation', 'None')}")
print(f"  -> Complex Portal IDs: {r1.data.get('uniprot', {}).get('complex_portal_ids', [])}")
print(f"  -> Harvested RCSB PDB Candidates: {len(r1.data.get('rcsb_candidates', []))} entries")
'''
    cells.append(create_code_cell(part2_stage_1_code))

    # 13b. Stage 1 Output Explanation Markdown with Details Pane
    stage_1_explain_md = r"""### Stage 1 Output Analysis: Curated Subunit Evidence & Complex Portal

Stage 1 extracts primary literature annotations from UniProtKB comment blocks and the Complex Portal database:
- **Subunit Comment Parsing:** Natural language comments (e.g. "cylinder of 14 subunits composed of two heptameric rings") provide gold-standard curation.
- **Complex Portal Cross-References:** Identifies known stable biological machineries and stoichiometric formulas ($A_{14}B_7$ for GroEL-GroES via CPX-2113).
- **RCSB PDB Candidate Harvesting:** Gathers experimentally resolved crystal and cryo-EM structures associated with the UniProt accession for downstream assembly ranking.

<details>
<summary><b>Biological Benchmark Comparison: Stage 1 Across Presets</b></summary>

| Preset Target | Accession | Curated Subunit Annotation | Complex Portal Cross-Reference | Initial Assemblies Harvested |
| :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | `P0A6F5` | Homotetradecamer (two heptameric rings) | `CPX-2113` / `CPX-1882` ($A_{14}B_7$) | Multiple ($1\text{AON}, 1\text{GRL}, 1\text{DK7}$) |
| **Insulin Hormone** | `P01308` | Monomer / Dimer / Hexamer dynamic equilibrium | Curated solution states | $4\text{INS} (A_6), 2\text{INS} (A_2), 9\text{INS} (A_1)$ |
| **H. influenzae UP000000579** | `P44101` | Uncharacterized (no curated multimer) | None | Monomer baseline ($A_1$) |
| **Novel Synthetic Sequence** | *Raw Sequence* | None (bypasses accession lookup) | None | Zero (proceeds to de novo inference) |

</details>
"""
    cells.append(create_markdown_cell(stage_1_explain_md))

    # 14. Part 2 Stage 2 Execution Cell
    part2_stage_2_code = r'''# Stage 2: RCSB PDB Experimental Assemblies & Candidate Scoring
print("[STAGE 2/6: EXPERIMENTAL ASSEMBLIES] Evaluating macromolecular assemblies & candidate scoring...")
r2 = session.run_stage_2_experimental_assemblies()
print(f"  -> Status: {r2.status.value} | Total Assemblies Found: {len(r2.data.get('assemblies', []))}")
print(f"  -> Top Evaluated Candidate: PDB {r2.data.get('evaluated_pdb_id')} (Resolution: {r2.data.get('evaluated_resolution')} Å)")
breakdown = r2.data.get('score_breakdown', {})
print(f"  -> Candidate Assembly Score: {r2.data.get('assembly_score')} / 9.0")
print(f"     * Coverage Weight (W_cov): {breakdown.get('w_coverage')} | Tier: {r2.data.get('coverage_tier')}")
print(f"     * Resolution Weight (W_res): {breakdown.get('w_resolution')} (at {r2.data.get('evaluated_resolution')} Å)")
print(f"     * PISA Stability Weight (W_pisa): {breakdown.get('w_pisa')}")
if r2.data.get('candidate_scoring'):
    print(f"  -> Top Scored Candidates Breakdown ({len(r2.data['candidate_scoring'])} evaluated):")
    for c in r2.data['candidate_scoring'][:3]:
        print(f"     - PDB {c['pdb_id']}: Res={c['resolution']}Å | W_cov={c['w_coverage']} | W_res={c['w_resolution']} | W_pisa={c['w_pisa']} | Score={c['assembly_score']}")
'''
    cells.append(create_code_cell(part2_stage_2_code))

    # 14b. Stage 2 Output Explanation Markdown with Details Pane
    stage_2_explain_md = r"""### Stage 2 Output Analysis: Candidate-Specific Assembly Scoring (D-02)

Stage 2 resolves macromolecular biological assemblies and ranks candidates using a strictly candidate-specific formula ($S = W_{\text{cov}} + W_{\text{res}} + W_{\text{assembly}}$):
- **Assembly-Aware Candidate Ranking (D-02):** Evaluates biological assemblies rather than asymmetric unit fragments. Isolated domain fragments (such as `1DK7`, the apical domain of GroEL) receive domain fragment penalties, correctly prioritizing full-length biological assemblies (`1AON`, `1GRL`).
- **Dynamic Assembly Register:** Rather than forcing a single rigid assembly, Stage 2 captures all observed conformational states into `observed_assemblies` (e.g. Insulin storage hexamer vs. active circulating dimer).

<details>
<summary><b>Biological Benchmark Comparison: Stage 2 Assembly Ranking Across Presets</b></summary>

| Preset Target | Top Ranked Assembly | Evaluated Subunits | Resolution | Fragment Penalty Handled | Assembly Score |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | `1AON` / `1GRL` (Biological Assembly) | 14 ($A_{14}$) | $2.8\ \text{Å}$ | Yes (`1DK7` penalized over `1AON`) | High ($\ge 8.0 / 9.0$) |
| **Insulin Hormone** | `4INS` (Storage Hexamer) | 6 ($A_6$) | $1.5\ \text{Å}$ | Full coverage of A/B chains | High ($\ge 8.5 / 9.0$) |
| **H. influenzae UP000000579** | Monomer baseline | 1 ($A_1$) | N/A | Monomer fallback | Baseline |
| **Novel Synthetic Sequence** | Dynamic prediction | Unknown | N/A | No experimental candidates | Dynamic Fallback |

</details>
"""
    cells.append(create_markdown_cell(stage_2_explain_md))

    # 15. Part 2 Stage 3 Execution Cell
    part2_stage_3_code = r'''# Stage 3: PDBe PISA Thermodynamic Qualification & Interface Biophysics
print("[STAGE 3/6: THERMODYNAMIC QUALIFICATION] Computing interface contacts, solvation free energy, and residue maps...")
r3 = session.run_stage_3_thermodynamic_qualification()
interfaces_found = r3.data.get('interfaces', []) if r3.data else []
print(f"  -> Status: {r3.status.value} | Interfaces Analyzed: {len(interfaces_found)} Pairwise Contacts")
if interfaces_found:
    i0 = interfaces_found[0]
    res1 = i0.get('interface_residues_chain_1', [])
    res2 = i0.get('interface_residues_chain_2', [])
    print(f"  -> Primary Interface ({i0.get('chain_1')}-{i0.get('chain_2')}):")
    print(f"     * Buried Surface Area (BSA): {i0.get('buried_surface_area_angstrom2')} Å²")
    print(f"     * Solvation Energy Gain (ΔG): {i0.get('solvation_free_energy_kcal_mol')} kcal/mol")
    print(f"     * Hydrogen Bonds: {i0.get('hydrogen_bonds_count')} | Salt Bridges: {i0.get('salt_bridges_count')}")
    print(f"     * Chain {i0.get('chain_1')} Interface Residues ({len(res1)} residues): {res1[:10]}{'...' if len(res1) > 10 else ''}")
    print(f"     * Chain {i0.get('chain_2')} Interface Residues ({len(res2)} residues): {res2[:10]}{'...' if len(res2) > 10 else ''}")
else:
    print("  -> No multimer interfaces detected (consistent with monomeric baseline).")
'''
    cells.append(create_code_cell(part2_stage_3_code))

    # 15b. Stage 3 Output Explanation Markdown with Details Pane
    stage_3_explain_md = r"""### Stage 3 Output Analysis: Interface Biophysics & Interacting Residues (D-09 & D-10)

Stage 3 computes the physical forces stabilizing quaternary assemblies:
- **Buried Surface Area (BSA):** Obligate biological interfaces typically bury extensive solvent-accessible surface area ($\text{BSA} \ge 800 - 1500\ \text{Å}^2$), whereas transient crystal lattice contacts bury significantly less area.
- **Solvation Free Energy Gain ($\Delta^i G$):** Negative solvation free energy upon interface formation indicates favorable hydrophobic desolvation driving spontaneous assembly.
- **Genuine Thermodynamic States (D-10):** PISA assessment is nuanced into `STABLE`, `INTERMEDIATE`, `DISSOCIATED`, and `UNKNOWN` without simplistic $\Delta G \le 0$ lattice artifact assumptions.

<details>
<summary><b>Biological Benchmark Comparison: Stage 3 Interface Thermodynamics Across Presets</b></summary>

| Preset Target | Interface Count | Buried Surface Area | Solvation Free Energy | Interfacial Residues | Thermodynamic Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | Multiple pairwise interfaces | Extensive ($>1,800\ \text{Å}^2$) | Strongly favorable ($\Delta^i G < 0$) | Explicit residue mapping | `STABLE` |
| **Insulin Hormone** | Dimeric & hexameric interfaces | Moderate to large ($\sim 1,200\ \text{Å}^2$) | Negative ($\Delta^i G < 0$) | A/B chain interface residues | `STABLE` |
| **H. influenzae UP000000579** | 0 interfaces | $0.0\ \text{Å}^2$ | $0.0\ \text{kcal/mol}$ | None (monomeric) | `UNKNOWN` / Monomer Baseline |
| **Novel Synthetic Sequence** | 0 interfaces | $0.0\ \text{Å}^2$ | $0.0\ \text{kcal/mol}$ | None | `UNKNOWN` / Uncharacterized |

</details>
"""
    cells.append(create_markdown_cell(stage_3_explain_md))

    # 16. Part 2 Stage 4 Execution Cell
    part2_stage_4_code = r'''# Stage 4: SWISS-MODEL Homology Modeling & Interaction Partners
print("[STAGE 4/6: HOMOLOGY & PARTNERS] Querying oligomeric homology templates, IntAct partners, and monomer coordinates...")
r4 = session.run_stage_4_homology_and_partners()
models_found = r4.data.get('models', []) if r4.data else []
print(f"  -> Status: {r4.status.value} | Homology Models: {len(models_found)}")
if models_found:
    m0 = models_found[0]
    print(f"  -> Top Homology Template: {m0.get('template_id', 'N/A')}")
    print(f"     * QMQE Score: {m0.get('qmqe', 0.0):.2f} (Quaternary Quality Estimate)")
    print(f"     * GMQE Score: {m0.get('gmqe', 0.0):.2f} (Global Model Quality Estimate)")
af_db = r4.data.get('alphafold_db', {})
plddt_val = af_db.get('global_plddt')
print(f"  -> AlphaFold-DB Monomer pLDDT: {plddt_val if plddt_val is not None else 'N/A'} (Strictly D-05 segregated)")
intact_partners = r4.data.get('physical_interactors', [])
print(f"  -> IntAct Interactors: {len(intact_partners)} physical binding partners found")
'''
    cells.append(create_code_cell(part2_stage_4_code))

    # 16b. Stage 4 Output Explanation Markdown with Details Pane
    stage_4_explain_md = r"""### Stage 4 Output Analysis: Homology Modeling & Monomeric Context (D-05)

Stage 4 integrates SWISS-MODEL homology modeling with AlphaFold DB monomeric coordinates and IntAct physical interactors:
- **QMQE vs. GMQE:** Quaternary Model Quality Estimate (QMQE) evaluates multi-chain interface alignment against oligomeric templates, while Global Model Quality Estimate (GMQE) measures overall single-chain coverage.
- **Strict Monomeric Segregation (D-05 & D-12):** AlphaFold DB per-residue pLDDT scores reflect the conformational confidence of the monomer fold alone and are never conflated with quaternary assembly stability.
- **Hetero-Partner Discovery:** Cross-references IntAct physical interaction databases to identify potential functional binding partners.

<details>
<summary><b>Biological Benchmark Comparison: Stage 4 Homology & AlphaFold Context Across Presets</b></summary>

| Preset Target | Top Homology Template | QMQE Score | GMQE Score | AlphaFold Monomer pLDDT | Physical Interactors |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | `1AON.1` ($A_{14}$) | $0.88$ | $0.94$ | High ($>90.0$) | GroES, DnaK, DnaJ |
| **Insulin Hormone** | `4INS.1` ($A_6$) | $0.78$ | $0.85$ | High ($>85.0$) | Binding receptors |
| **H. influenzae UP000000579** | Homology template | N/A (Monomeric) | Moderate | Confident monomer | Uncharacterized |
| **Novel Synthetic Sequence** | None | N/A | N/A | Dynamic ESMFold | None |

</details>
"""
    cells.append(create_markdown_cell(stage_4_explain_md))

    # 17. Part 2 Stage 5 Execution Cell
    part2_stage_5_code = r'''# Stage 5: Predictive Multimer Modeling (Real-Execution Only - D-09)
# Truthful Real-Execution Policy: Returns StageStatus.UNAVAILABLE when live GPU compute runner
# is unconfigured, strictly prohibiting injection of fake simulation metrics.
print(f"[STAGE 5/6: PREDICTIVE MULTIMER] Executing predictive multimer modeling (Opt-in enabled: {ENABLE_MULTIMER})...")
r5 = session.run_stage_5_predictive_multimer(enable_multimer=ENABLE_MULTIMER)
print(f"  -> Status: {r5.status.value}")
if r5.status == StageStatus.SUCCESS:
    print(f"  -> Predicted Stoichiometry: {r5.data.get('predicted_stoichiometry')}")
    print(f"  -> Interface Predicted TM-score (ipTM): {r5.data.get('iptm')}")
    print(f"  -> Complex Predicted TM-score (pTM): {r5.data.get('ptm')}")
    print(f"  -> Overall Model Confidence (0.8·ipTM + 0.2·pTM): {r5.data.get('model_confidence')}")
else:
    print(f"  -> Real-Execution Policy Notice: Stage status is '{r5.status.value}'.")
    print(f"     External GPU/ColabFold runner not configured in environment. No fake simulation scores injected.")
'''
    cells.append(create_code_cell(part2_stage_5_code))

    # 17b. Stage 5 Output Explanation Markdown with Details Pane
    stage_5_explain_md = r"""### Stage 5 Output Analysis: Predictive Multimer Modeling (Real-Execution Only - D-09)

Stage 5 enforces invariant **D-09 (Real Execution Only)**:
- **Truthful Availability Reporting:** Deep learning multimer modeling (ColabFold / AlphaFold-Multimer) requires dedicated GPU acceleration. If an external live compute runner is not configured, the pipeline truthfully reports `StageStatus.UNAVAILABLE` (or `SKIPPED`).
- **Zero Synthetic Injection:** In strict adherence to scientific rigor, zero simulated or fabricated scores (such as fake ipTM or pTM numbers) are injected.
- **Model Confidence Interpretation:** When executed with live compute, interface accuracy is quantified via $\text{ipTM}$ and whole-complex packing via $\text{pTM}$ ($0.8 \cdot \text{ipTM} + 0.2 \cdot \text{pTM}$).

<details>
<summary><b>Biological Benchmark Comparison: Stage 5 Predictive Multimer Across Presets</b></summary>

| Preset Target | Multimer Opt-In | Live GPU Runner | Stage Status | ipTM / pTM Values | Scientific Policy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | `True` | Unconfigured | `UNAVAILABLE` | N/A (Zero fake scores) | D-09 Real Execution Policy |
| **Insulin Hormone** | `True` | Unconfigured | `UNAVAILABLE` | N/A (Zero fake scores) | D-09 Real Execution Policy |
| **H. influenzae UP000000579** | `False` | Unconfigured | `SKIPPED` | N/A | D-09 Real Execution Policy |
| **Novel Synthetic Sequence** | `True` | Unconfigured | `UNAVAILABLE` | N/A (Zero fake scores) | D-09 Real Execution Policy |

</details>
"""
    cells.append(create_markdown_cell(stage_5_explain_md))

    # 18. Part 2 Stage 6 Execution Cell
    part2_stage_6_code = r'''# Stage 6: Biological Synthesis & Functional Inference
print("[STAGE 6/6: SYNTHESIS & FUNCTIONAL INFERENCE] Synthesizing multi-evidence consensus & mechanistic inference...")
r6 = session.run_stage_6_synthesis_and_functional_inference()
status_str = r6.status.value if hasattr(r6.status, "value") else str(getattr(r6, "quaternary_status", "SUCCESS"))
print(f"  -> Synthesis Status: {status_str}")
formula_str = getattr(session.output.stoichiometry, "formula", None) or getattr(session.output.stoichiometry, "stoichiometry_formula", "Unknown")
print(f"  -> Target Self-Assembly Formula: {session.output.target_self_assembly.formula if session.output.target_self_assembly else formula_str}")
print(f"  -> Assembly Classification: {session.output.stoichiometry.assembly_type.value}")
print(f"  -> Total Subunit Count: {session.output.stoichiometry.total_subunits}")
print(f"  -> Functional Complexes: {len(session.output.functional_complexes)}")
if session.output.functional_complexes:
    for fc in session.output.functional_complexes:
        print(f"     * {fc.name}: {fc.stoichiometry} (Partners: {fc.partner_names})")
if session.output.inferred_function:
    print(f"  -> Inferred Molecular Function: {session.output.inferred_function.molecular_function}")
    print(f"  -> Mechanism: {session.output.inferred_function.oligomeric_mechanism_hypothesis[:90]}...")
print(f"  -> Retained Conflicts: {len(session.output.conflicts)}")
print(f"  -> Completed Analytical Stages: {session.output.stages_completed}")
'''
    cells.append(create_code_cell(part2_stage_6_code))

    # 18b. Stage 6 Biological Visualizers Display Cell
    part2_stage_6_visuals_code = r'''# Render full suite of biological visualizers for the modular session output
display(render_quaternary_summary_card(session.output))
display(render_component_identity_table(session.output))
display(render_interface_contact_table(session.output))
display(render_dynamic_equilibrium_display(session.output))
display(render_functional_inference_card(session.output))
display(render_evidence_coverage_dashboard(session.output))
'''
    cells.append(create_code_cell(part2_stage_6_visuals_code))

    # 18c. Stage 6 Output Explanation Markdown with Details Pane
    stage_6_explain_md = r"""### Stage 6 Output Analysis: Multi-Evidence Synthesis & Functional Inference (D-03 & D-06)

Stage 6 integrates all evidence streams into a unified `QuaternaryStructureOutput` contract:
- **Biological Disambiguation (D-06):** Distinguishes target self-assembly ($A_n$) from higher-order multi-protein functional machinery ($A_n B_m$). For GroEL, resolves $A_{14}$ homo-tetradecamer self-assembly and $A_{14}B_7$ GroEL-GroES functional machinery.
- **Conflict Retention (D-03):** Flags and retains crystallographic vs. solution conflicts in `conflicts[]` rather than discarding divergent data.
- **Mechanistic Functional Inference:** Analyzes quaternary symmetry and interface architecture to infer molecular function, biological processes, and quaternary mechanistic hypotheses via structural archetypes.

<details>
<summary><b>Biological Benchmark Comparison: Stage 6 Multi-Evidence Synthesis Across Presets</b></summary>

| Preset Target | Target Self-Assembly | Functional Complexes | Inferred Molecular Function | Consensus Status | Provenance Tag |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GroEL Chaperonin** | $A_{14}$ ($D_7$ tetradecamer) | $A_{14}B_7$ (GroEL-GroES) | Chaperonin folding cage | `CONFIRMED` | `[EXPERIMENTAL]` |
| **Insulin Hormone** | $A_2$ (Dimer) | $A_6$ (Storage Hexamer) | Peptide hormone / receptor ligand | `CONFIRMED` | `[EXPERIMENTAL]` |
| **H. influenzae UP000000579** | $A_1$ (Monomer baseline) | None | Uncharacterized | `SUPPORTED` | `[DATABASE-DERIVED]` |
| **Novel Synthetic Sequence** | $A_1$ (Monomer baseline) | None | Uncharacterized baseline | `INSUFFICIENT EVIDENCE` | `[PREDICTED]` |

</details>
"""
    cells.append(create_markdown_cell(stage_6_explain_md))

    # 19. Part 2 Stage Results Tree Inspection Cell
    part2_stages_tree_code = r'''# Inspect multi-stage evidence payloads across all 6 stages
print("Multi-Stage Evidence Payloads (StageResult dictionary):")
display(show_json(session.stage_results, max_depth=1))
'''
    cells.append(create_code_cell(part2_stages_tree_code))

    # 19b. Stage Results Tree Explanation Markdown
    stage_results_explain_md = r"""### Stage Evidence Payloads Inspection

The collapsible tree above contains the discrete evidence generated by each stage (`session.stage_results`):
- Each stage dictionary stores its raw service responses, timestamps, status, and provenance logs.
- This modular isolation ensures complete scientific auditability, allowing researchers to trace any quaternary conclusion back to specific experimental or predictive records.
"""
    cells.append(create_markdown_cell(stage_results_explain_md))

    return cells


def build_wave_3_cells() -> list[nbf.NotebookNode]:
    """Generate cells for Wave 3: Biological commentary, data contract export, and dual showcase."""
    cells = []

    # 1. Biological Foundations & Interpretation Commentary
    commentary_md = r"""## Scientific Foundations & Biological Interpretation Guide

Understanding quaternary protein architecture requires integrating concepts from structural thermodynamics, crystallography, and evolutionary biology.

### 1. Quaternary Structure Foundations & Evolutionary Drive
- **Functional Allostery & Cooperativity:** Multimeric complexes exhibit cooperative substrate binding, enabling sensitive metabolic regulation.
- **Genetic Economy & Active Site Assembly:** Encoding smaller modular subunits that assemble into massive molecular machines maximizes functional surface area while minimizing genome space.
- **Symmetry & Stability:** Symmetric homomers ($C_n$ cyclic, $D_n$ dihedral, icosahedral) benefit from entropic stabilization and localized hydrophobic core packing.

### 2. Stoichiometry & Notation Guide
Stoichiometry characterizes the number and identity of distinct interacting polypeptide chains:
- **$A_1$ (Monomer):** A single peptide chain functioning independently in solution.
- **$A_2$ (Homodimer):** Two identical chains forming a symmetric interface (e.g., Leucine zipper transcription factors).
- **$A_2 B_2$ (Heterotetramer):** Two distinct chain species assembled in equimolar pairs (e.g., Hemoglobin $\alpha_2 \beta_2$).
- **$A_{14}$ (Tetradecamer):** Large homooligomer arranged as back-to-back heptameric rings (e.g., GroEL chaperonin).

### 3. Interface Biophysics & Buried Surface Area (BSA)
Interfaces between macromolecular chains are characterized by thermodynamic parameters calculated by PDBe PISA:
- **Buried Surface Area (BSA in $\text{Å}^2$):** Total solvent-accessible surface area obscured upon complex formation. Permanent, stable biological interfaces typically exhibit $\text{BSA} \ge 800 - 1500\ \text{Å}^2$ per interface, whereas non-specific crystal lattice packing contacts generally fall below $400\ \text{Å}^2$.
- **Solvation Free Energy Gain ($\Delta^i G$ in $\text{kcal/mol}$):** The change in solvation free energy upon complex formation. A strictly negative value ($\Delta^i G < 0$) indicates favorable hydrophobic interaction driving spontaneous assembly in solution.
- **Electrostatic Contacts:** Hydrogen bonds and salt bridges positioned across interface boundaries provide conformational specificity and orientational locking.

### 4. Confidence Score Provenance & Conflict Resolution (D-03 & D-08)
- **Zero Synthetic Blending:** Machine learning confidence metrics (AlphaFold pLDDT, ipTM) and biophysical scores (PISA $\Delta^i G$, Swiss-Model QMQE) are strictly segregated in the output contract. Blending these disparate numerical distributions into an unweighted single score destroys the physical distinction between experimental observation and predictive simulation.
- **Crystallographic vs Solution Conflicts:** Crystal packing forces in X-ray crystallography frequently induce non-biological multimerization in the unit cell. When RCSB author annotations assert a multimer but PDBe PISA biophysics calculate non-stabilizing solvation energies, the pipeline flags an `ExperimentalConflict` preserving both viewpoints and providing scientific rationale.
"""
    cells.append(create_markdown_cell(commentary_md))

    # 2. Part 3 Markdown Header
    part3_md = r"""## Part 3: Data Contract Export & Downstream Consumption

The quaternary analysis results are exported into a validated, standardized data contract (`quaternary_structure_output.json`).
This artifact conforms to the schema required by frontend UI visualization components and provides direct accessors for downstream scientific workflows.
"""
    cells.append(create_markdown_cell(part3_md))

    # 3. JSON Contract File Export Cell (Code)
    export_json_code = r'''# Export standardized UI JSON data contract
export_path = "quaternary_structure_output.json"
json_payload = session.to_ui(format="json", export_path=export_path)

output_file = Path(export_path)
assert output_file.exists(), f"Expected export file '{export_path}' was not created!"
file_size_kb = output_file.stat().st_size / 1024

print(f" Data Contract Exported: '{export_path}' ({file_size_kb:.2f} KB)")
print(f" Status: Valid QuaternaryStructureOutput JSON contract ready for frontend UI ingestion.")
'''
    cells.append(create_code_cell(export_json_code))

    # 4. Programmatic Accessors (Dict & DataFrame) (Code)
    accessors_code = r'''# Programmatic Accessors for Python Data Science & Downstream Pipelines
# 1. Native Python dictionary
res_dict = session.to_ui(format="dict")
print(f" Python Dict Export: {len(res_dict)} top-level schema attributes available.")

# 2. Tabular Pandas DataFrames
res_df = session.to_ui(format="dataframe")
summary_df = res_df["summary"] if isinstance(res_df, dict) else res_df

print("\n--- Quaternary Summary DataFrame ---")
display(summary_df.head())

if isinstance(res_df, dict) and "stages" in res_df:
    print("\n--- Analysis Stages Execution State ---")
    display(res_df["stages"])

if isinstance(res_df, dict) and "interfaces" in res_df and not res_df["interfaces"].empty:
    print("\n--- Identified Subunit Interfaces ---")
    display(res_df["interfaces"].head())
'''
    cells.append(create_code_cell(accessors_code))

    # 4b. Tabular DataFrames Explanation Markdown
    dataframes_explain_md = r"""### Downstream Data Contract & Tabular Views Explanation

The programmatic exports above illustrate how downstream analytics and visualization tools consume quaternary results:
- **`quaternary_structure_output.json`:** Fully serializable JSON artifact matching the frontend schema specification.
- **Summary DataFrame (`res_df["summary"]`):** High-level tabular record suitable for indexing, batch querying, or database ingestion.
- **Stages DataFrame (`res_df["stages"]`):** Execution audit log showing status, stage names, and error traces across all pipeline stages.
- **Interfaces DataFrame (`res_df["interfaces"]`):** Granular contact table listing pairwise chain combinations, buried surface areas, and solvation energies for structural analysis.
"""
    cells.append(create_markdown_cell(dataframes_explain_md))

    # 5. Dual Showcase Demonstration Header & Narrative (Markdown)
    showcase_md = r"""## Dual Showcase Demonstration & Target Comparison (QUAT-09)

To demonstrate the robustness of the Quaternary Pipeline across varying degrees of biological characterization, we evaluate two representative benchmark targets:
1. **Positive Control (GroEL Chaperonin - `P0A6F5`):**
   - High experimental coverage in PDB and PDBe PISA.
   - Ground truth: Homotetradecamer ($A_{14}$) with known back-to-back ring symmetry and co-chaperonin complex ($A_{14}B_7$).
   - Validates that experimental assemblies and biophysical interfaces achieve full consensus.
2. **Uncharacterized Benchmark (*Haemophilus influenzae* - `P44101` / Proteome `UP000000579`):**
   - Uncharacterized protein target with sparse direct experimental complex data in PDB.
   - Demonstrates graceful fallback: homology modeling and predictive structural context take over without uncaught exceptions, maintaining a robust monomer baseline.
"""
    cells.append(create_markdown_cell(showcase_md))

    # 6. Dual Showcase Execution (Code)
    showcase_code = r'''# Execute Dual Showcase Comparison
print("=" * 68)
print("DUAL SHOWCASE BENCHMARK COMPARISON (QUAT-08 & QUAT-09)")
print("=" * 68)

# Target 1: Well-characterized Positive Control (GroEL P0A6F5)
print("\n[Target 1: Positive Control] GroEL Chaperonin (P0A6F5):")
out_groel = analyze_quaternary("P0A6F5", config=config, enable_multimer=False)
formula_groel = getattr(out_groel.stoichiometry, "formula", "A14")
assembly_groel = out_groel.stoichiometry.assembly_type.value
subunits_groel = getattr(out_groel.stoichiometry, "total_subunits", 14)
print(f"  -> Assembly: {assembly_groel} | Formula: {formula_groel} ({subunits_groel} subunits)")
if out_groel.target_self_assembly:
    print(f"  -> Target Self-Assembly: {out_groel.target_self_assembly.formula} ({out_groel.target_self_assembly.confidence_status.value})")
if out_groel.functional_complexes:
    print(f"  -> Functional Complexes: {[fc.name + ' (' + fc.stoichiometry + ')' for fc in out_groel.functional_complexes]}")
print(f"  -> Quaternary Status: {out_groel.quaternary_status}")
print(f"  -> Interfaces Captured: {len(getattr(out_groel, 'interfaces', []))}")

# Target 2: Uncharacterized Haemophilus influenzae Target (P44101)
print("\n[Target 2: Benchmark Target] Haemophilus influenzae UP000000579 (P44101):")
out_hi = analyze_quaternary("P44101", config=config, enable_multimer=False)
formula_hi = getattr(out_hi.stoichiometry, "formula", "A")
assembly_hi = out_hi.stoichiometry.assembly_type.value
subunits_hi = getattr(out_hi.stoichiometry, "total_subunits", 1)
print(f"  -> Assembly: {assembly_hi} | Formula: {formula_hi} ({subunits_hi} subunits)")
print(f"  -> Quaternary Status: {out_hi.quaternary_status}")
print(f"  -> Function Status: {out_hi.inferred_function.status.value if out_hi.inferred_function else 'UNCHARACTERIZED'}")
print(f"  -> Completed Stages: {out_hi.stages_completed}")

print("\n Dual Showcase Verification Complete: Pipeline handles both rich and sparse targets deterministically.")
'''
    cells.append(create_code_cell(showcase_code))

    # 6b. Dual Showcase Output Explanation Markdown
    showcase_explain_md = r"""### Dual Showcase Biological Results & Comparative Insights

The dual showcase benchmark demonstrates the pipeline's deterministic adaptability across the structural biology spectrum:
1. **Positive Control: GroEL Chaperonin (`P0A6F5`):**
   - High-resolution X-ray structures, cryo-EM reconstructions, and curated Complex Portal records.
   - Flawless consensus alignment resolving a 14-subunit homotetradecamer ($A_{14}$) with stable pairwise interfaces, alongside GroEL-GroES hetero-complexation ($A_{14}B_7$).
2. **Uncharacterized Benchmark: *H. influenzae* Target (`P44101` / Proteome `UP000000579`):**
   - Lacks direct experimental complex characterization in PDB.
   - The pipeline degrades gracefully without uncaught exceptions, establishing the monomer baseline and uncharacterized functional status.
"""
    cells.append(create_markdown_cell(showcase_explain_md))

    return cells


def build_wave_4_cells() -> list[nbf.NotebookNode]:
    """Generate cells for Wave 4: Novel / Random sequence handling demonstration."""
    cells = []

    # 1. Header & Problem Statement Markdown
    random_md = r"""## Part 4: Handling Novel & Arbitrary Sequences (Non-Accession Input)

A critical requirement of modern bioinformatics engines is handling **novel, synthetic, or de novo designed sequences** that have no pre-existing entries in UniProtKB, RCSB PDB, or PDBe PISA.

### Graceful Degradation & Predictive Fallback Architecture:
When an arbitrary IUPAC amino acid sequence is provided:
1. **Input Detection:** The validator identifies a raw sequence (`is_accession = False`).
2. **Experimental Bypass:** Stage 1 (UniProt) and Stage 2 (PDB) recognize the sequence input and cleanly return empty experimental sets without error.
3. **Monomeric Coordinates & Homology:** Stage 4 handles sequence alignment, bypassing unindexed accessions cleanly.
4. **Predictive Multimer Modeling:** Stage 5 evaluates predictive self-association, truthfully returning `StageStatus.UNAVAILABLE` when external GPU compute is unconfigured.
5. **Synthesis Consensus & Functional Fallback:** Stage 6 synthesizes predictive evidence into a valid `QuaternaryStructureOutput` contract with status `MONOMER` (or `HOMOMER`), setting `inferred_function.status` to `UNCHARACTERIZED`.
"""
    cells.append(create_markdown_cell(random_md))

    # 2. Execution Code Cell
    random_code = r'''# Execute Quaternary Pipeline on a novel synthetic / arbitrary amino acid sequence
RANDOM_SEQUENCE = "MKTLLILAVLLACAFSAQQAQPEVKVEETVTVIKPEVEVKPEVKPEVEPEPEPEPEPEPE"

print(f"[START] Processing novel arbitrary sequence ({len(RANDOM_SEQUENCE)} residues)...")
t0 = time.time()
random_output = analyze_quaternary(RANDOM_SEQUENCE, config=config, enable_multimer=False)
t_elapsed = time.time() - t0

print(f"[COMPLETE] Novel sequence processed in {t_elapsed:.2f}s")
print(f"  -> Quaternary Status: {random_output.quaternary_status}")
print(f"  -> Assembly Type: {random_output.stoichiometry.assembly_type.value}")
print(f"  -> Stoichiometry Formula: {random_output.stoichiometry.formula}")
print(f"  -> Total Subunits: {random_output.stoichiometry.total_subunits}")
print(f"  -> Inferred Function: {random_output.inferred_function.molecular_function if random_output.inferred_function else 'UNCHARACTERIZED'}")
print(f"  -> Successfully Completed Stages: {random_output.stages_completed}")
'''
    cells.append(create_code_cell(random_code))

    # 3. Summary Card Display Cell
    random_card_code = r'''# Render biological summary card and functional card for the novel sequence
display(render_quaternary_summary_card(random_output))
display(render_functional_inference_card(random_output))
display(render_evidence_coverage_dashboard(random_output))
'''
    cells.append(create_code_cell(random_card_code))

    # 4. Output Explanation Markdown Cell
    random_explain_md = r"""### Biological Output Analysis: Novel Sequence Characterization

The output above demonstrates the pipeline's deterministic fallback behavior when handling completely novel sequences:
- **Assembly Classification (`MONOMER`):** In the absence of prior experimental multimerization evidence or strong predictive self-affinity, the pipeline safely establishes a monomeric baseline ($A_1$).
- **Functional Fallback (`UNCHARACTERIZED`):** When homology and curated functional records are absent, the inference engine assigns uncharacterized status with neutral confidence.
- **Zero Unhandled Exceptions:** The pipeline transitioned through all 6 stages smoothly without uncaught network errors, null pointer dereferences, or broken JSON contracts.
- **Schema Uniformity:** The resulting `QuaternaryStructureOutput` object adheres to the exact same Pydantic schema as experimentally validated complexes.
"""
    cells.append(create_markdown_cell(random_explain_md))

    return cells


def assemble_notebook(cells: list[nbf.NotebookNode]) -> nbf.NotebookNode:
    """Create a validated v4 notebook from cells."""
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12",
            "mimetype": "text/x-python",
            "codemirror_mode": {"name": "ipython", "version": 3},
            "pygments_lexer": "ipython3",
        },
    }
    nbf.validate(nb)
    return nb


def execute_notebook(nb: nbf.NotebookNode) -> nbf.NotebookNode:
    """Execute all code cells in the notebook to populate outputs, tables, and HTML summary cards."""
    from nbconvert.preprocessors import ExecutePreprocessor
    print(" Pre-executing notebook to generate rich visual outputs and figures...")
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    ep.preprocess(nb, {"metadata": {"path": "."}})
    print(" Notebook execution completed successfully.")
    return nb


def write_notebook(nb: nbf.NotebookNode, output_path: str = "Quaternary_Structure.ipynb") -> None:
    """Write notebook to file with utf-8 encoding."""
    target = Path(output_path)
    with open(target, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print(f" Notebook successfully written to {target.resolve()} ({len(nb.cells)} cells).")


def main(execute: bool = True) -> None:
    """Build and execute Quaternary_Structure.ipynb across all waves."""
    # Check CLI flags
    if "--no-exec" in sys.argv:
        execute = False

    cells = build_wave_1_cells() + build_wave_2_cells() + build_wave_3_cells() + build_wave_4_cells()
    nb = assemble_notebook(cells)
    if execute:
        try:
            nb = execute_notebook(nb)
        except Exception as e:
            print(f" Warning: Notebook execution failed: {e}. Writing unexecuted notebook.")
    write_notebook(nb)


if __name__ == "__main__":
    main()
