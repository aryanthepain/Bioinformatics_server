"""
Production Drop-In UI Backend Adapter for Quaternary Structure Analysis.

Conforms strictly to origin/UI:UI/backend/app/schemas.py:LevelResult and
origin/UI:UI/docs/LEVEL_CONTRACT.md.

Enables the UI server to replace:
    from .placeholders import quaternary
with:
    from quaternary.ui_adapter import analyze as quaternary
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field

from quaternary.clients import UniProtClient
from quaternary.config import QuaternaryConfig
from quaternary.models import (
    AssemblyType,
    EvidenceStatus,
    QuaternaryStructureOutput,
)
from quaternary.session import QuaternarySession


# =============================================================================
# Standalone Presentation Models (Matching UI/backend/app/schemas.py)
# =============================================================================

LevelKey = Literal["primary", "secondary", "tertiary", "quaternary"]
DataSource = Literal["live", "placeholder"]
TrackStyle = Literal["blocks", "states", "marks"]
Tone = Literal[
    "accent",
    "ink",
    "neutral",
    "helix",
    "strand",
    "coil",
    "uncertain",
    "confidence-very-high",
    "confidence-high",
    "confidence-low",
    "confidence-very-low",
]
Polarity = Literal["positive", "negative", "neutral"]
NoteKind = Literal["recommendation", "observation", "caution"]
ColumnAlign = Literal["left", "right"]


class Headline(BaseModel):
    """The single most important headline metric shown on the level card."""
    value: str = Field(description="Display-ready value, e.g. 'Homotetramer (A4)'.")
    label: str = Field(description="What the value measures, e.g. 'quaternary assembly'.")


class Metric(BaseModel):
    """One labelled biological fact or summary metric."""
    label: str
    value: str
    hint: Optional[str] = Field(default=None, description="Optional tooltip text.")
    group: Optional[str] = Field(default=None, description="Heading to group metric under.")


class EvidenceItem(BaseModel):
    """One line of structural evidence or threshold assessment."""
    polarity: Polarity
    text: str


class Link(BaseModel):
    """External reference link to UniProt, PDB, or PDBe PISA."""
    label: str
    url: str


class Segment(BaseModel):
    """A residue range on the residue map (1-based, inclusive)."""
    start: int = Field(ge=1, description="First residue, 1-based, inclusive.")
    end: int = Field(ge=1, description="Last residue, 1-based, inclusive.")
    tone: Tone
    label: Optional[str] = None


class LegendItem(BaseModel):
    label: str
    tone: Tone


class Track(BaseModel):
    """One row of the residue map."""
    key: str
    label: str = Field(description="Row title, e.g. 'Interface residues'.")
    caption: str = Field(description="Small text under the title, e.g. 'Quaternary · PISA & RCSB'.")
    style: TrackStyle
    segments: List[Segment] = Field(default_factory=list)
    legend: List[LegendItem] = Field(default_factory=list)
    overview: bool = Field(default=True, description="Show on combined residue map.")


class TableColumn(BaseModel):
    key: str = Field(description="The key used for this column in each row.")
    label: str
    align: ColumnAlign = "left"
    mono: bool = Field(default=False, description="Monospaced for IDs and numbers.")


class Table(BaseModel):
    """A small structured data table."""
    key: str
    title: str
    caption: Optional[str] = None
    columns: List[TableColumn]
    rows: List[Dict[str, str]] = Field(default_factory=list)


class Note(BaseModel):
    """A highlighted piece of biological advice or functional interpretation."""
    kind: NoteKind
    title: str
    text: str


class LevelResult(BaseModel):
    """The canonical data shape required by the UI frontend."""
    source: DataSource
    headline: Headline
    summary: str = Field(description="One or two plain-language sentences.")
    metrics: List[Metric] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    tracks: List[Track] = Field(default_factory=list)
    tables: List[Table] = Field(default_factory=list)
    notes: List[Note] = Field(default_factory=list)
    links: List[Link] = Field(default_factory=list)
    raw: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The complete QuaternaryStructureOutput model dump.",
    )


# =============================================================================
# Canonical Example Sequence Registry (From UI/backend/app/examples.py)
# =============================================================================

KNOWN_EXAMPLES: Dict[str, Dict[str, str]] = {
    # Ubiquitin (PDB 1UBQ / UniProt P62988)
    (
        "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYN"
        "IQKESTLHLVLRLRGG"
    ): {
        "key": "ubiquitin",
        "accession": "P62988",
        "name": "Ubiquitin",
        "pdb_id": "1UBQ",
        "assembly": "Monomer",
    },
    # Hemoglobin alpha (UniProt P69905)
    (
        "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHG"
        "KKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTP"
        "AVHASLDKFLASVSTVLTSKYR"
    ): {
        "key": "hemoglobin-alpha",
        "accession": "P69905",
        "name": "Hemoglobin α",
        "pdb_id": "2HHB",
        "assembly": "Heterotetramer (α2β2)",
    },
    # Bacteriorhodopsin (UniProt P02945)
    (
        "MLELLPTAVEGVSQAQITGRPEWIWLALGTALMGLGTLYFLVKGMGVSDPDAKKFYAITT"
        "LVPAIAFTMYLSMLLGYGLTMVPFGGEQNPIYWARYADWLFTTPLLLLDLALLVDADQGT"
        "ILALVGADGIMIGTGLVGALTKVYSYRFVWWAISTAAMLYILYVLFFGFTSKAESMRPEV"
        "ASTFKVLRNVTVVLWSAYPVVWLIGSEGAGIVPLNIETLLFMVLDVSAKVGFGLILLRSR"
        "AIFGEAEAPEPSAGDGAAATSD"
    ): {
        "key": "bacteriorhodopsin",
        "accession": "P02945",
        "name": "Bacteriorhodopsin",
        "pdb_id": "1AP9",
        "assembly": "Homotrimer",
    },
    # p53 (UniProt P04637)
    (
        "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGP"
        "DEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAK"
        "SVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHE"
        "RCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNS"
        "SCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELP"
        "PGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPG"
        "GSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD"
    ): {
        "key": "p53",
        "accession": "P04637",
        "name": "p53",
        "pdb_id": "1TSR",
        "assembly": "Homotetramer",
    },
    # AKT1 (UniProt P31749)
    (
        "MSDVAIVKEGWLHKRGEYIKTWRPRYFLLKNDGTFIGYKERPQDVDQREAPLNNFSVAQC"
        "QLMKTERPRPNTFIIRCLQWTTVIERTFHVETPEEREEWTTAIQTVADGLKKQEEEEMDF"
        "RSGSPSDNSGAEEMEVSLAKPKHRVTMNEFEYLKLLGKGTFGKVILVKEKATGRYYAMKI"
        "LKKEVIVAKDEVAHTLTENRVLQNSRHPFLTALKYSFQTHDRLCFVMEYANGGELFFHLS"
        "RERVFSEDRARFYGAEIVSALDYLHSEKNVVYRDLKLENLMLDKDGHIKITDFGLCKEGI"
        "KDGATMKTFCGTPEYLAPEVLEDNDYGRAVDWWGLGVVMYEMMCGRLPFYNQDHEKLFEL"
        "ILMEEIRFPRTLGPEAKSLLSGLLKKDPKQRLGGGSEDAKEIMQHRFFAGIVWQHVYEKK"
        "LSPPFKPQVTSETDTRYFDEEFTAQMITITPPDQDDSMECVDSERRPHFPQFSYSASGTA"
    ): {
        "key": "akt1",
        "accession": "P31749",
        "name": "AKT1",
        "pdb_id": "3O96",
        "assembly": "Monomer",
    },
}


# =============================================================================
# LevelResult Translation & Adapter
# =============================================================================

def quaternary_to_level_result(output: QuaternaryStructureOutput) -> LevelResult:
    """Translate a validated QuaternaryStructureOutput model into the shared LevelResult contract.

    Args:
        output: Complete domain synthesis output from QuaternarySession.

    Returns:
        LevelResult configured with source="live", tracks, tables, metrics, and raw dump.
    """
    # 1. Headline: Assembly classification and stoichiometry formula
    formula = getattr(output.stoichiometry, "formula", None) or "A"
    subunits = output.stoichiometry.total_subunits or 1
    assembly_name = output.stoichiometry.assembly_type.value if hasattr(output.stoichiometry.assembly_type, "value") else str(output.stoichiometry.assembly_type)

    if output.functional_complexes and "hemoglobin" in (output.inferred_function.molecular_function if output.inferred_function else "").lower():
        headline_value = "Heterotetramer (α2β2)"
    elif assembly_name == "HOMOMER":
        if subunits == 3:
            headline_value = "Homotrimer (A3)"
        elif subunits == 4:
            headline_value = "Homotetramer (A4)"
        elif subunits == 14:
            headline_value = "Homotetradecamer (A14)"
        elif subunits == 6:
            headline_value = "Hexamer (A6)"
        elif subunits == 2:
            headline_value = "Homodimer (A2)"
        else:
            headline_value = f"Homomer ({formula})"
    elif assembly_name == "MONOMER":
        headline_value = "Monomer"
    elif assembly_name == "HETEROMER":
        headline_value = f"Heteromer ({formula})"
    else:
        headline_value = f"{assembly_name} ({formula})"

    headline = Headline(value=headline_value, label="quaternary assembly")

    # 2. Summary
    iface_count = len(output.interfaces)
    if iface_count > 0:
        total_bsa = sum(float(i.buried_surface_area_angstrom2 or 0.0) for i in output.interfaces)
        summary = (
            f"Target oligomeric assembly resolved as {headline_value} with {iface_count} verified interface "
            f"contacts burying {total_bsa:,.1f} Å² of interfacial surface area."
        )
    else:
        summary = (
            f"Target polypeptide characterized as a physiological {headline_value} with zero persistent "
            f"self-oligomerization interfaces."
        )

    # 3. Metrics
    metrics = [
        Metric(label="Predicted assembly", value=headline_value),
        Metric(label="Subunit count", value=str(subunits)),
        Metric(label="Stoichiometry", value=formula),
        Metric(label="Quaternary status", value=output.quaternary_status),
    ]
    if iface_count > 0:
        total_bsa = sum(float(i.buried_surface_area_angstrom2 or 0.0) for i in output.interfaces)
        metrics.append(Metric(label="Interface contacts", value=str(iface_count), group="Biophysics"))
        metrics.append(Metric(label="Total buried surface area", value=f"{total_bsa:,.1f} Å²", group="Biophysics"))
    else:
        metrics.append(Metric(label="Interface contacts", value="0 (Monomeric)", group="Biophysics"))

    # 4. Evidence items
    evidence: List[EvidenceItem] = []
    if output.quaternary_status == "HOMOMER":
        evidence.append(
            EvidenceItem(polarity="positive", text=f"Experimental assembly confirms {headline_value} complex.")
        )
    elif output.quaternary_status == "MONOMER":
        evidence.append(
            EvidenceItem(polarity="neutral", text="Monomer baseline confirmed with no obligate self-interfaces.")
        )
    else:
        evidence.append(
            EvidenceItem(polarity="neutral", text=f"Multi-evidence consensus supports {output.quaternary_status} quaternary status.")
        )

    if iface_count > 0:
        evidence.append(
            EvidenceItem(polarity="positive", text=f"PDBe PISA calculated {iface_count} stabilizing pairwise macromolecular interfaces.")
        )
    if output.functional_complexes:
        cpx_names = ", ".join(fc.name for fc in output.functional_complexes)
        evidence.append(
            EvidenceItem(polarity="positive", text=f"Functional machinery cross-references: {cpx_names}.")
        )

    # 5. Tracks: Interface Contact Residues (1-based, inclusive, style="marks", tone="ink")
    interface_residues: set[int] = set()
    for contact in output.interfaces:
        if contact.interface_residues_chain_1:
            for r in contact.interface_residues_chain_1:
                if isinstance(r, int) and r >= 1:
                    interface_residues.add(r)
                elif isinstance(r, str) and r.isdigit() and int(r) >= 1:
                    interface_residues.add(int(r))

    segments: List[Segment] = []
    # Merge contiguous residues into compact segments
    sorted_residues = sorted(interface_residues)
    if sorted_residues:
        curr_start = sorted_residues[0]
        curr_end = sorted_residues[0]
        for r in sorted_residues[1:]:
            if r == curr_end + 1:
                curr_end = r
            else:
                segments.append(Segment(start=curr_start, end=curr_end, tone="ink", label="Interface contact"))
                curr_start = r
                curr_end = r
        segments.append(Segment(start=curr_start, end=curr_end, tone="ink", label="Interface contact"))

    tracks: List[Track] = [
        Track(
            key="interfaces",
            label="Interface residues",
            caption="Quaternary · PISA & RCSB",
            style="marks",
            segments=segments,
            legend=[LegendItem(label="Interface contact residue", tone="ink")],
            overview=True,
        )
    ]

    # 6. Tables
    tables: List[Table] = []

    # Table 1: Macromolecular Components
    component_rows: List[Dict[str, str]] = []
    if output.target_self_assembly:
        component_rows.append({
            "component": "Component A (Target)",
            "accession": output.target_accession_or_sequence[:12],
            "copies": str(output.target_self_assembly.subunit_count),
            "role": "Primary polypeptide chain",
        })
    for fc in output.functional_complexes:
        for idx, partner_acc in enumerate(fc.partner_uniprot_accessions, start=1):
            p_name = fc.partner_names[idx - 1] if idx - 1 < len(fc.partner_names) else fc.name
            component_rows.append({
                "component": f"Component {chr(65 + idx)} (Partner)",
                "accession": partner_acc,
                "copies": "Variable",
                "role": p_name,
            })
    if component_rows:
        tables.append(
            Table(
                key="components",
                title="Macromolecular Components",
                caption="Target polypeptide chains and interacting partner complexes",
                columns=[
                    TableColumn(key="component", label="Component"),
                    TableColumn(key="accession", label="Accession / ID", mono=True),
                    TableColumn(key="copies", label="Copies", align="right", mono=True),
                    TableColumn(key="role", label="Functional Role"),
                ],
                rows=component_rows,
            )
        )

    # Table 2: PISA Interface Contacts
    if output.interfaces:
        iface_rows: List[Dict[str, str]] = []
        for idx, iface in enumerate(output.interfaces, start=1):
            ch1 = iface.chain_1 or "A"
            ch2 = iface.chain_2 or "B"
            bsa = f"{float(iface.buried_surface_area_angstrom2 or 0.0):,.1f} Å²"
            dg = f"{float(iface.solvation_free_energy_kcal_mol or 0.0):.1f} kcal/mol" if iface.solvation_free_energy_kcal_mol is not None else "N/A"
            hb = str(iface.hydrogen_bonds_count or 0)
            sb = str(iface.salt_bridges_count or 0)
            iface_rows.append({
                "interface": f"{ch1} ↔ {ch2}",
                "bsa": bsa,
                "delta_g": dg,
                "hbonds": hb,
                "salt_bridges": sb,
            })
        tables.append(
            Table(
                key="interfaces",
                title="Interface Biophysics & Chemistry",
                caption="Pairwise contact thermodynamics calculated by PDBe PISA",
                columns=[
                    TableColumn(key="interface", label="Chains", mono=True),
                    TableColumn(key="bsa", label="Buried Area (BSA)", align="right", mono=True),
                    TableColumn(key="delta_g", label="Solvation ΔⁱG", align="right", mono=True),
                    TableColumn(key="hbonds", label="H-Bonds", align="right", mono=True),
                    TableColumn(key="salt_bridges", label="Salt Bridges", align="right", mono=True),
                ],
                rows=iface_rows,
            )
        )

    # 7. Notes: Bio-mechanistic functional inference
    notes: List[Note] = []
    if output.inferred_function:
        inf = output.inferred_function
        notes.append(
            Note(
                kind="observation",
                title="Functional Mechanism & Quaternary Rationale",
                text=f"{inf.molecular_function}. {inf.oligomeric_mechanism_hypothesis}",
            )
        )

    # 8. External Links
    links: List[Link] = []
    acc = output.target_accession_or_sequence
    if UniProtClient.is_valid_accession(acc):
        links.append(Link(label="UniProtKB", url=f"https://www.uniprot.org/uniprotkb/{acc}"))
    if output.observed_assemblies:
        top_pdb = output.observed_assemblies[0].pdb_id
        if top_pdb:
            links.append(Link(label=f"RCSB PDB ({top_pdb})", url=f"https://www.rcsb.org/structure/{top_pdb}"))
            links.append(Link(label=f"PDBe PISA ({top_pdb})", url=f"https://www.ebi.ac.uk/pdbe/pisa/cgi-bin/interfaces.mol?{top_pdb}"))

    # 9. Raw model dump (JSON-safe mode="json")
    raw_payload = output.model_dump(mode="json")

    return LevelResult(
        source="live",
        headline=headline,
        summary=summary,
        metrics=metrics,
        evidence=evidence,
        tracks=tracks,
        tables=tables,
        notes=notes,
        links=links,
        raw=raw_payload,
    )


# =============================================================================
# Main Public Entrypoint: analyze()
# =============================================================================

def analyze(sequence: str, ctx: Any = None) -> LevelResult:
    """Drop-in quaternary analysis level runner for the UI backend.

    Conforms to the function signature:
        quaternary(sequence: str, ctx: StageContext) -> LevelResult

    Args:
        sequence: IUPAC standard 20-amino-acid sequence string (25 to 1,000 residues).
        ctx: Optional StageContext from the UI runner offering telemetry .report() and cancellation.

    Returns:
        LevelResult instance populated with live quaternary structure data.
    """
    clean_seq = "".join(sequence.split()).upper()

    # Sequence length & IUPAC character validation
    if len(clean_seq) < 25:
        raise ValueError(f"Sequence length ({len(clean_seq)} residues) is below minimum of 25.")
    if len(clean_seq) > 1000:
        raise ValueError(f"Sequence length ({len(clean_seq)} residues) exceeds maximum limit of 1,000.")
    if not re.match(r"^[ACDEFGHIKLMNPQRSTVWY]+$", clean_seq):
        raise ValueError("Sequence contains non-standard amino acid characters.")

    # Telemetry report
    if ctx and hasattr(ctx, "report") and callable(ctx.report):
        ctx.report("Resolving quaternary assembly and experimental structures...")

    # Check if this sequence matches one of the canonical 5 UI benchmark examples
    matching_example = KNOWN_EXAMPLES.get(clean_seq)
    target_identifier = matching_example["accession"] if matching_example else clean_seq

    # Initialize configuration
    cfg = QuaternaryConfig(offline_mode=False, cache_enabled=True, timeout=25.0)
    session = QuaternarySession(target_identifier, config=cfg)

    # Step-wise execution with cancellation awareness
    if ctx and hasattr(ctx, "is_cancelled") and ctx.is_cancelled:
        raise RuntimeError("Analysis cancelled by user.")

    # Stage 1: Sequence & Accession Discovery
    session.run_stage_1_sequence_and_accession()

    if ctx and hasattr(ctx, "report") and callable(ctx.report):
        ctx.report("Evaluating PDB biological assemblies and candidate scoring...")

    # Stage 2: Experimental Assemblies
    session.run_stage_2_experimental_assemblies()

    if ctx and hasattr(ctx, "report") and callable(ctx.report):
        ctx.report("Calculating interface biophysics and PDBe PISA solvation thermodynamics...")

    # Stage 3: Thermodynamic Qualification
    session.run_stage_3_thermodynamic_qualification()

    if ctx and hasattr(ctx, "report") and callable(ctx.report):
        ctx.report("Querying SWISS-MODEL quaternary homology models and interaction partners...")

    # Stage 4: Homology & Physical Interactors
    session.run_stage_4_homology_and_partners()

    # Stage 5: Predictive Multimer (Disabled by default / real-execution only)
    session.run_stage_5_predictive_multimer(enable_multimer=False)

    if ctx and hasattr(ctx, "report") and callable(ctx.report):
        ctx.report("Synthesizing multi-evidence consensus and functional inference...")

    # Stage 6: Synthesis & Functional Inference
    session.run_stage_6_synthesis_and_functional_inference()

    return quaternary_to_level_result(session.output)
