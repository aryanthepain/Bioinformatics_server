"""
Quaternary Structure Presentation & Visual Component Library.

Provides decoupled, pure presentation utilities for rendering QuaternaryStructureOutput
models into rich, interactive HTML displays, collapsible JSON trees, and pre-flight
input validation status banners.

Architectural Rule (D-01 & D-02):
All render_* and show_json functions strictly construct and return IPython.display.HTML
objects. They do NOT invoke display() internally. Callers in notebook cells or web/UI
wrappers maintain full control over the display lifecycle.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Tuple
from IPython.display import HTML

from quaternary.models.session_state import QuaternaryStructureOutput


# Regex pattern adhering strictly to UniProtKB accession format specifications
UNIPROT_ACCESSION_REGEX = re.compile(
    r"^[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$"
)

# Standard IUPAC Amino Acid single-letter codes
VALID_AA_REGEX = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY\s]+$", re.IGNORECASE)


def validate_target_input(target_input: str) -> tuple[bool, str]:
    """
    Validate target protein input (UniProt accession or FASTA sequence).

    Parameters:
        target_input: Raw string input from user or benchmark preset.

    Returns:
        tuple[bool, str]: (is_valid, descriptive_status_message)
    """
    if not target_input or not isinstance(target_input, str):
        return False, "Input cannot be empty. Please provide a valid UniProt accession or FASTA sequence."

    cleaned = target_input.strip()

    # Check FASTA header + sequence
    if cleaned.startswith(">"):
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if len(lines) < 2:
            return False, "FASTA format requires a header line ('>header') followed by amino acid sequence."
        seq = "".join(lines[1:]).replace(" ", "")
        if not seq:
            return False, "FASTA sequence contains no amino acid characters."
        if not VALID_AA_REGEX.match(seq):
            return False, "FASTA sequence contains invalid non-IUPAC amino acid characters."
        return True, f"Valid FASTA sequence ({len(seq)} residues)."

    # Check raw single-line sequence (length >= 10 and pure AA characters)
    if len(cleaned) >= 10 and VALID_AA_REGEX.match(cleaned) and not UNIPROT_ACCESSION_REGEX.match(cleaned):
        return True, f"Valid raw amino acid sequence ({len(cleaned)} residues)."

    # Check UniProt Accession
    if UNIPROT_ACCESSION_REGEX.match(cleaned.upper()):
        return True, f"Valid UniProtKB accession format: '{cleaned.upper()}'"

    return False, (
        f"Invalid input '{cleaned}'. Must be a valid UniProt accession (e.g. 'P0A6F5', 'P01308') "
        "or a standard IUPAC amino acid sequence."
    )


def render_validation_status(is_valid: bool, msg: str) -> HTML:
    """
    Construct and return a styled HTML banner indicating pre-flight input status.

    Parameters:
        is_valid: Boolean verification flag from validate_target_input.
        msg: Explanatory validation message.

    Returns:
        HTML: Renderable IPython HTML banner.
    """
    bg_color = "#1e3a24" if is_valid else "#4a1c1c"
    border_color = "#2ea043" if is_valid else "#f85149"
    icon = "&#10004;" if is_valid else "&#9888;"
    status_label = "INPUT VERIFIED" if is_valid else "VALIDATION WARNING"

    html = f"""
    <div style="background-color: {bg_color}; border-left: 5px solid {border_color};
                padding: 12px 16px; border-radius: 4px; margin: 10px 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                color: #e6edf3; font-size: 13.5px; line-height: 1.5;">
        <span style="font-weight: 700; color: {border_color}; margin-right: 8px;">{icon} {status_label}:</span>
        <span>{msg}</span>
    </div>
    """
    return HTML(html.strip())


def show_json(data: Any, max_depth: int = 1) -> HTML:
    """
    Construct and return an interactive VS Code style dark tree viewer with collapsible arrows.

    Parameters:
        data: Dict, Pydantic model, list, or JSON string to visualize.
        max_depth: How many levels deep to expand by default (e.g. 1 or 2).

    Returns:
        HTML: IPython HTML object embedding renderjson.js and a unique container ID.
    """
    if hasattr(data, "model_dump"):
        dumped_data = data.model_dump()
    elif isinstance(data, str):
        try:
            dumped_data = json.loads(data)
        except Exception:
            dumped_data = data
    elif hasattr(data, "__dict__") and not isinstance(data, dict):
        dumped_data = vars(data)
    else:
        dumped_data = data

    container_id = f"json_viewer_{uuid.uuid4().hex}"
    json_str = json.dumps(dumped_data, default=str)

    html_code = f"""
    <div id="{container_id}" style="background-color: #1e1e1e; padding: 14px; border-radius: 6px; font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace; font-size: 13px; text-align: left; overflow-x: auto;"></div>

    <script src="https://cdn.jsdelivr.net/npm/renderjson@1.4.0/renderjson.min.js"></script>
    <script>
        (function() {{
            renderjson.set_show_to_level({max_depth});
            renderjson.set_icons('▶ ', '▼ ');

            var container = document.getElementById("{container_id}");
            if (container) {{
                container.appendChild(renderjson({json_str}));
            }}
        }})();
    </script>

    <style>
        #{container_id} .renderjson {{ color: #d4d4d4; line-height: 1.5; }}
        #{container_id} .renderjson .disclosure {{ color: #808080; cursor: pointer; text-decoration: none; font-weight: bold; margin-right: 2px; }}
        #{container_id} .renderjson .disclosure:hover {{ color: #ffffff; }}
        #{container_id} .renderjson .syntax {{ color: #ffd700; }}
        #{container_id} .renderjson .string {{ color: #ce9178; }}
        #{container_id} .renderjson .number {{ color: #b5cea8; }}
        #{container_id} .renderjson .boolean {{ color: #569cd6; }}
        #{container_id} .renderjson .key {{ color: #9cdcfe; }}
        #{container_id} .renderjson .keyword {{ color: #c586c0; }}
    </style>
    """
    return HTML(html_code.strip())


def render_quaternary_summary_card(output: QuaternaryStructureOutput) -> HTML:
    """
    Render a styled HTML summary card displaying top-level biological metrics.

    Parameters:
        output: QuaternaryStructureOutput model or dictionary equivalent.

    Returns:
        HTML: IPython HTML summary card.
    """
    if not isinstance(output, QuaternaryStructureOutput):
        if isinstance(output, dict):
            try:
                output = QuaternaryStructureOutput.model_validate(output)
            except Exception:
                pass

    if isinstance(output, dict):
        analysis_id = output.get("analysis_id", "AN_UNKNOWN")
        st_data = output.get("stoichiometry") or {}
        if isinstance(st_data, dict):
            raw_atype = st_data.get("assembly_type", "UNCHARACTERIZED")
            assembly_val = str(raw_atype.value if hasattr(raw_atype, "value") else raw_atype).upper()
            formula = st_data.get("formula") or st_data.get("stoichiometry_formula", "Uncharacterized")
            total_subunits = st_data.get("total_subunits") or st_data.get("total_subunit_count", 1)
        else:
            raw_atype = getattr(st_data, "assembly_type", "UNCHARACTERIZED")
            assembly_val = str(raw_atype.value if hasattr(raw_atype, "value") else raw_atype).upper()
            formula = getattr(st_data, "formula", None) or getattr(st_data, "stoichiometry_formula", "Uncharacterized")
            total_subunits = getattr(st_data, "total_subunits", None) or getattr(st_data, "total_subunit_count", 1)

        oligo_state = output.get("oligomeric_state") or f"{total_subunits}-mer"
        conflicts = output.get("conflicts") or []
        exp_conflict = output.get("experimental_conflict") or {}
        conflict_detected = bool(conflicts) or (
            exp_conflict.get("conflict_detected", False) if isinstance(exp_conflict, dict) else getattr(exp_conflict, "conflict_detected", False)
        ) or output.get("quaternary_status") == "CONFLICTING"

        prov = output.get("confidence_provenance") or {}
        pisa = prov.get("pdbe_pisa") if isinstance(prov, dict) else getattr(prov, "pdbe_pisa", None)
        swiss = prov.get("swissmodel") if isinstance(prov, dict) else getattr(prov, "swissmodel", None)
        af = prov.get("alphafold_db") if isinstance(prov, dict) else getattr(prov, "alphafold_db", None)
        afm = prov.get("alphafold_multimer") if isinstance(prov, dict) else getattr(prov, "alphafold_multimer", None)

        interfaces_list = output.get("interfaces") or output.get("interface_contacts") or []
        interfaces_count = len(interfaces_list)
    else:
        analysis_id = output.analysis_id
        assembly_type = output.stoichiometry.assembly_type
        assembly_val = assembly_type.value if hasattr(assembly_type, "value") else str(assembly_type)
        formula = getattr(output.stoichiometry, "formula", None) or getattr(output.stoichiometry, "stoichiometry_formula", "Uncharacterized")
        total_subunits = getattr(output.stoichiometry, "total_subunits", None) or getattr(output.stoichiometry, "total_subunit_count", 1)
        oligo_state = getattr(output, "oligomeric_state", None) or f"{total_subunits}-mer"

        conflict_detected = False
        if hasattr(output, "experimental_conflict") and output.experimental_conflict:
            conflict_detected = getattr(output.experimental_conflict, "conflict_detected", False)
        elif hasattr(output, "conflicts") and output.conflicts:
            conflict_detected = len(output.conflicts) > 0

        prov = getattr(output, "confidence_provenance", None)
        pisa = getattr(prov, "pdbe_pisa", None) if prov else None
        swiss = getattr(prov, "swissmodel", None) if prov else None
        af = getattr(prov, "alphafold_db", None) if prov else None
        afm = getattr(prov, "alphafold_multimer", None) if prov else None

        interfaces_list = getattr(output, "interfaces", None) or getattr(output, "interface_contacts", [])
        interfaces_count = len(interfaces_list) if interfaces_list else 0

    if conflict_detected:
        conflict_badge = '<span style="background: #5a1e1e; color: #ff7b72; padding: 3px 10px; border-radius: 12px; font-size: 11.5px; font-weight: 700;">&#9888; CONFLICT DETECTED</span>'
    else:
        conflict_badge = '<span style="background: #1e3a24; color: #7ee787; padding: 3px 10px; border-radius: 12px; font-size: 11.5px; font-weight: 700;">&#10004; CONSENSUS ALIGNED</span>'

    def _get_val(obj, key, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    pisa_diss = _get_val(pisa, "dissociation_energy_kcal_mol")
    pisa_bsa = _get_val(pisa, "buried_surface_area_angstrom2")
    if pisa_diss is not None:
        pisa_score = f"{pisa_diss:.1f} kcal/mol"
    elif pisa_bsa is not None:
        pisa_score = f"{pisa_bsa:.0f} Å²"
    else:
        pisa_score = "N/A"

    swiss_qmqe = _get_val(swiss, "qmqe")
    swiss_gmqe = _get_val(swiss, "gmqe")
    if swiss_qmqe is not None and swiss_qmqe > 0 and swiss_gmqe is not None and swiss_gmqe > 0:
        swiss_display = f"QMQE: {swiss_qmqe:.2f} | GMQE: {swiss_gmqe:.2f}"
    elif swiss_gmqe is not None and swiss_gmqe > 0:
        swiss_display = f"GMQE: {swiss_gmqe:.2f} (QMQE: N/A)"
    elif swiss_qmqe is not None and swiss_qmqe > 0:
        swiss_display = f"{swiss_qmqe:.2f}"
    elif swiss_qmqe is not None or swiss_gmqe is not None:
        val = swiss_qmqe if swiss_qmqe is not None else swiss_gmqe
        swiss_display = f"{val:.2f}"
    else:
        swiss_display = "N/A"

    af_plddt_val = _get_val(af, "global_plddt")
    af_plddt = f"{af_plddt_val:.1f}" if af_plddt_val is not None else "N/A"

    afm_iptm_val = _get_val(afm, "iptm")
    afm_ptm_val = _get_val(afm, "ptm")
    if afm_iptm_val is not None:
        if afm_ptm_val is not None:
            af_iptm = f"ipTM: {afm_iptm_val:.2f} | pTM: {afm_ptm_val:.2f}"
        else:
            af_iptm = f"{afm_iptm_val:.2f}"
    else:
        af_iptm = "N/A (Real-execution runner unconfigured)"

    card_html = f"""
    <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin: 15px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #c9d1d9;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; padding-bottom: 12px; margin-bottom: 16px;">
            <div style="font-size: 18px; font-weight: 700; color: #58a6ff;">
                &#129516; Quaternary Structure Summary: <span style="color: #79c0ff;">{analysis_id}</span>
            </div>
            <div>{conflict_badge}</div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 18px;">
            <div style="background: #252526; padding: 12px; border-radius: 6px; border-left: 3px solid #58a6ff;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Assembly Type</div>
                <div style="font-size: 16px; font-weight: bold; color: #f0f6fc; margin-top: 4px;">{assembly_val}</div>
            </div>
            <div style="background: #252526; padding: 12px; border-radius: 6px; border-left: 3px solid #7ee787;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Stoichiometry</div>
                <div style="font-size: 16px; font-weight: bold; color: #f0f6fc; margin-top: 4px;">{formula}</div>
            </div>
            <div style="background: #252526; padding: 12px; border-radius: 6px; border-left: 3px solid #d2a8ff;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Subunits / Oligomer</div>
                <div style="font-size: 16px; font-weight: bold; color: #f0f6fc; margin-top: 4px;">{total_subunits} ({oligo_state})</div>
            </div>
            <div style="background: #252526; padding: 12px; border-radius: 6px; border-left: 3px solid #ffa657;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Interface Contacts</div>
                <div style="font-size: 16px; font-weight: bold; color: #f0f6fc; margin-top: 4px;">{interfaces_count} Pairwise</div>
            </div>
        </div>

        <div style="background: #161b22; border-radius: 6px; padding: 14px; border: 1px solid #30363d;">
            <div style="font-size: 12px; font-weight: 600; color: #8b949e; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.5px;">
                &#128202; Segregated Confidence Metrics (Zero Synthetic Blending)
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; font-size: 12.5px;">
                <div><span style="color: #8b949e;">PDBe PISA Score:</span> <strong style="color: #58a6ff;">{pisa_score}</strong></div>
                <div><span style="color: #8b949e;">SWISS-MODEL:</span> <strong style="color: #7ee787;">{swiss_display}</strong></div>
                <div><span style="color: #8b949e;">AlphaFold pLDDT:</span> <strong style="color: #d2a8ff;">{af_plddt}</strong></div>
                <div><span style="color: #8b949e;">AlphaFold-Multimer:</span> <strong style="color: #ffa657;">{af_iptm}</strong></div>
            </div>
        </div>
    </div>
    """
    return HTML(card_html.strip())


def render_component_identity_table(output: QuaternaryStructureOutput) -> HTML:
    """
    Render a styled biological table detailing all complex components, UniProt IDs, copies, and roles.

    Parameters:
        output: QuaternaryStructureOutput model or dictionary equivalent.

    Returns:
        HTML: IPython HTML component identity table.
    """
    if not isinstance(output, QuaternaryStructureOutput):
        if isinstance(output, dict):
            output = QuaternaryStructureOutput.model_validate(output)

    rows = []
    gene_name = output.metadata.get("gene_name") or "Target Protein"
    organism = output.metadata.get("organism") or ""
    display_name = f"{gene_name} ({organism})" if organism else gene_name
    target_id = output.target_accession_or_sequence

    if output.target_self_assembly:
        copies_a = output.target_self_assembly.subunit_count
    elif output.stoichiometry and output.stoichiometry.chains:
        copies_a = output.stoichiometry.chains.get("A", output.stoichiometry.total_subunits or 1)
    else:
        copies_a = 1

    if copies_a == 1:
        chains_a = "A"
    elif copies_a <= 14:
        chains_a = ", ".join([chr(ord("A") + i) for i in range(min(copies_a, 14))])
    else:
        chains_a = f"A - {chr(ord('A') + min(copies_a - 1, 25))}"

    role_a = '<span style="background: #1e3a5f; color: #58a6ff; padding: 2px 8px; border-radius: 10px; font-weight: 600; font-size: 11px;">TARGET SUBUNIT</span>'
    rows.append({
        "component": "A",
        "protein": display_name,
        "accession": target_id,
        "copies": copies_a,
        "chains": chains_a,
        "role": role_a,
    })

    partner_comp_letter = ord("B")
    if output.functional_complexes:
        for fc in output.functional_complexes:
            p_names = fc.partner_names or [fc.name]
            p_accs = fc.partner_uniprot_accessions or ["N/A"]
            b_copies = 1
            if "B" in fc.stoichiometry:
                m = re.search(r"B(\d+)", fc.stoichiometry)
                if m:
                    b_copies = int(m.group(1))

            for i, name in enumerate(p_names):
                acc = p_accs[i] if i < len(p_accs) else "N/A"
                comp_char = chr(partner_comp_letter)
                chains_str = f"{comp_char}1 - {comp_char}{b_copies}" if b_copies > 1 else comp_char
                role_b = '<span style="background: #2b3a1e; color: #7ee787; padding: 2px 8px; border-radius: 10px; font-weight: 600; font-size: 11px;">PARTNER COMPLEX</span>'
                rows.append({
                    "component": comp_char,
                    "protein": name,
                    "accession": acc,
                    "copies": b_copies,
                    "chains": chains_str,
                    "role": role_b,
                })
                partner_comp_letter += 1

    table_rows_html = "".join([
        f"""<tr style="border-bottom: 1px solid #30363d;">
            <td style="padding: 8px 12px; font-weight: bold; color: #58a6ff;">{r['component']}</td>
            <td style="padding: 8px 12px; color: #f0f6fc;">{r['protein']}</td>
            <td style="padding: 8px 12px; font-family: monospace; color: #79c0ff;">{r['accession']}</td>
            <td style="padding: 8px 12px; text-align: center; color: #f0f6fc; font-weight: bold;">{r['copies']}</td>
            <td style="padding: 8px 12px; font-family: monospace; color: #d2a8ff;">{r['chains']}</td>
            <td style="padding: 8px 12px;">{r['role']}</td>
        </tr>"""
        for r in rows
    ])

    html_card = f"""
    <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 15px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #c9d1d9;">
        <div style="font-size: 15px; font-weight: 700; color: #58a6ff; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
            &#129516; Macromolecular Component Identity Table
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;">
            <thead>
                <tr style="background: #252526; border-bottom: 2px solid #30363d; color: #8b949e; text-transform: uppercase; font-size: 11px;">
                    <th style="padding: 8px 12px;">Component</th>
                    <th style="padding: 8px 12px;">Target / Partner Protein</th>
                    <th style="padding: 8px 12px;">UniProt Accession</th>
                    <th style="padding: 8px 12px; text-align: center;">Copies</th>
                    <th style="padding: 8px 12px;">PDB Chains</th>
                    <th style="padding: 8px 12px;">Complex Role</th>
                </tr>
            </thead>
            <tbody>
                {table_rows_html}
            </tbody>
        </table>
    </div>
    """
    return HTML(html_card.strip())


def render_interface_contact_table(output: QuaternaryStructureOutput) -> HTML:
    """
    Render a styled table detailing interface contact parameters, BSA, ΔiG, and interacting residues.

    Parameters:
        output: QuaternaryStructureOutput model or dictionary equivalent.

    Returns:
        HTML: IPython HTML interface contact table or monomer fallback banner.
    """
    if not isinstance(output, QuaternaryStructureOutput):
        if isinstance(output, dict):
            output = QuaternaryStructureOutput.model_validate(output)

    interfaces = getattr(output, "interfaces", []) or []
    if not interfaces:
        html_empty = """
        <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 15px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #8b949e; font-size: 13px;">
            <span style="color: #79c0ff; font-weight: bold;">&#8505; Pairwise Interface Contact Residues:</span> No multimer interfaces detected (consistent with monomeric baseline).
        </div>
        """
        return HTML(html_empty.strip())

    rows_html = []
    for iface in interfaces[:8]:
        c1 = getattr(iface, "chain_1", "A")
        c2 = getattr(iface, "chain_2", "B")
        bsa = getattr(iface, "buried_surface_area_angstrom2", 0.0) or 0.0
        dg = getattr(iface, "solvation_free_energy_kcal_mol", 0.0) or 0.0
        hb = getattr(iface, "hydrogen_bonds_count", 0) or 0
        sb = getattr(iface, "salt_bridges_count", 0) or 0
        res1 = getattr(iface, "interface_residues_chain_1", []) or []
        res2 = getattr(iface, "interface_residues_chain_2", []) or []

        res1_str = ", ".join(map(str, res1[:6])) + ("..." if len(res1) > 6 else "") if res1 else "None"
        res2_str = ", ".join(map(str, res2[:6])) + ("..." if len(res2) > 6 else "") if res2 else "None"
        res_display = f"Ch {c1}: [{res1_str}] | Ch {c2}: [{res2_str}]"

        rows_html.append(f"""
        <tr style="border-bottom: 1px solid #30363d;">
            <td style="padding: 8px 12px; font-weight: bold; color: #79c0ff; font-family: monospace;">{c1} &mdash; {c2}</td>
            <td style="padding: 8px 12px; color: #f0f6fc; font-weight: 600;">{bsa:,.1f} &#197;&#178;</td>
            <td style="padding: 8px 12px; color: {'#7ee787' if dg < 0 else '#ff7b72'}; font-weight: 600;">{dg:+.2f} kcal/mol</td>
            <td style="padding: 8px 12px; text-align: center; color: #f0f6fc;">{hb}</td>
            <td style="padding: 8px 12px; text-align: center; color: #f0f6fc;">{sb}</td>
            <td style="padding: 8px 12px; font-family: monospace; font-size: 11px; color: #8b949e;">{res_display}</td>
        </tr>
        """)

    html_card = f"""
    <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 15px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #c9d1d9;">
        <div style="font-size: 15px; font-weight: 700; color: #58a6ff; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
            <div>&#128295; Pairwise Interface Contact Residues & Thermodynamics</div>
            <div style="font-size: 12px; color: #8b949e;">{len(interfaces)} total interfaces analyzed (showing top {len(rows_html)})</div>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;">
            <thead>
                <tr style="background: #252526; border-bottom: 2px solid #30363d; color: #8b949e; text-transform: uppercase; font-size: 11px;">
                    <th style="padding: 8px 12px;">Chain Pair</th>
                    <th style="padding: 8px 12px;">Buried Surface Area</th>
                    <th style="padding: 8px 12px;">&#916;&#7527;G (Solvation)</th>
                    <th style="padding: 8px 12px; text-align: center;">H-Bonds</th>
                    <th style="padding: 8px 12px; text-align: center;">Salt Bridges</th>
                    <th style="padding: 8px 12px;">Key Contact Residues</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows_html)}
            </tbody>
        </table>
    </div>
    """
    return HTML(html_card.strip())


def render_functional_inference_card(output: QuaternaryStructureOutput) -> HTML:
    """
    Render an Executive Bio-Mechanistic Card displaying inferred molecular function, mechanism, and evidence.

    Parameters:
        output: QuaternaryStructureOutput model or dictionary equivalent.

    Returns:
        HTML: IPython HTML functional inference card or baseline fallback banner.
    """
    if not isinstance(output, QuaternaryStructureOutput):
        if isinstance(output, dict):
            output = QuaternaryStructureOutput.model_validate(output)

    fn = output.inferred_function
    if not fn:
        html_empty = """
        <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 15px 0; color: #8b949e;">
            <strong>Functional Inference:</strong> Uncharacterized / Novel sequence baseline.
        </div>
        """
        return HTML(html_empty.strip())

    conf_score = fn.confidence
    if conf_score >= 0.8:
        badge_style = "background: #1e3a24; color: #7ee787; border: 1px solid #238636;"
        badge_text = f"HIGH CONFIDENCE ({conf_score:.2f})"
    elif conf_score >= 0.5:
        badge_style = "background: #342814; color: #d29922; border: 1px solid #9e6a03;"
        badge_text = f"SUPPORTED ({conf_score:.2f})"
    else:
        badge_style = "background: #21262d; color: #8b949e; border: 1px solid #30363d;"
        badge_text = f"UNCHARACTERIZED ({conf_score:.2f})"

    homolog_rows = ""
    if fn.functional_homologs:
        for h in fn.functional_homologs[:4]:
            pdb = h.get("pdb_id", "N/A")
            ident = h.get("identity")
            ident_str = f"{ident*100:.1f}%" if (ident and ident <= 1.0) else (f"{ident}%" if ident else "N/A")
            h_fn = h.get("function") or h.get("name") or "Structural Homolog"
            homolog_rows += f"""
            <tr style="border-bottom: 1px solid #30363d; font-size: 12px;">
                <td style="padding: 4px 8px; font-family: monospace; color: #58a6ff;">PDB {pdb}</td>
                <td style="padding: 4px 8px; color: #f0f6fc;">{ident_str}</td>
                <td style="padding: 4px 8px; color: #8b949e;">{h_fn}</td>
            </tr>
            """

    go_tags = ""
    if fn.go_terms:
        for go in fn.go_terms[:6]:
            go_name = go.get("name") or go.get("id") or "GO Term"
            go_id = go.get("id", "")
            go_tags += f'<span style="background: #252526; color: #d2a8ff; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-right: 6px; margin-bottom: 4px; display: inline-block; border: 1px solid #30363d;" title="{go_id}">{go_name}</span>'
    else:
        go_tags = '<span style="color: #8b949e; font-size: 12px;">No GO terms annotated</span>'

    html_card = f"""
    <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin: 15px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #c9d1d9;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; padding-bottom: 12px; margin-bottom: 16px;">
            <div style="font-size: 16px; font-weight: 700; color: #79c0ff; display: flex; align-items: center; gap: 8px;">
                &#129516; Executive Bio-Mechanistic Card: Functional Inference
            </div>
            <div>
                <span style="{badge_style} padding: 4px 12px; border-radius: 12px; font-size: 11.5px; font-weight: 700;">
                    {badge_text}
                </span>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 16px;">
            <div style="background: #252526; padding: 14px; border-radius: 6px; border-left: 3px solid #58a6ff;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Predicted Molecular Function</div>
                <div style="font-size: 15px; font-weight: 600; color: #f0f6fc; margin-top: 4px;">{fn.molecular_function}</div>
                <div style="font-size: 12px; color: #8b949e; margin-top: 6px;"><strong>Process:</strong> {fn.biological_process}</div>
            </div>
            <div style="background: #252526; padding: 14px; border-radius: 6px; border-left: 3px solid #7ee787;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Quaternary Mechanism Hypothesis</div>
                <div style="font-size: 12.5px; color: #c9d1d9; margin-top: 4px; line-height: 1.5;">{fn.oligomeric_mechanism_hypothesis}</div>
            </div>
        </div>

        <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 14px;">
            <div style="display: flex; justify-content: space-between; flex-wrap: wrap; gap: 14px;">
                <div style="flex: 1; min-width: 240px;">
                    <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; font-weight: 600; margin-bottom: 8px;">
                        Contributing Structural Homologs
                    </div>
                    {f'<table style="width: 100%; border-collapse: collapse;">{homolog_rows}</table>' if homolog_rows else '<span style="color: #8b949e; font-size: 12px;">No structural homologs</span>'}
                </div>
                <div style="flex: 1; min-width: 240px;">
                    <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; font-weight: 600; margin-bottom: 8px;">
                        Gene Ontology & Functional Terms
                    </div>
                    <div>{go_tags}</div>
                </div>
            </div>
        </div>
    </div>
    """
    return HTML(html_card.strip())


def render_dynamic_equilibrium_display(output: QuaternaryStructureOutput) -> HTML:
    """
    Render dynamic multi-assembly equilibria observed across experimental crystallography and solution states.

    Parameters:
        output: QuaternaryStructureOutput model or dictionary equivalent.

    Returns:
        HTML: IPython HTML dynamic equilibrium display or single invariant banner.
    """
    if not isinstance(output, QuaternaryStructureOutput):
        if isinstance(output, dict):
            output = QuaternaryStructureOutput.model_validate(output)

    assemblies = output.observed_assemblies
    if not assemblies:
        html_empty = """
        <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 14px; margin: 15px 0; color: #8b949e; font-size: 13px;">
            <strong>Dynamic Assembly Equilibria:</strong> Single invariant quaternary state observed.
        </div>
        """
        return HTML(html_empty.strip())

    cards_html = []
    for ass in assemblies:
        pdb = ass.pdb_id
        st = ass.stoichiometry
        state = ass.primary_physiological_state or ass.biological_assembly_type
        cond = ass.conditions or "Standard crystallization buffer"
        dg = ass.delta_g_diss_kcal_mol
        dg_str = f"{dg:+.1f} kcal/mol" if dg is not None else "N/A"
        is_self = ass.is_target_self
        border_col = "#58a6ff" if is_self else "#7ee787"
        tag_text = "Target Self-Assembly" if is_self else "Functional Form"
        tag_bg = "#1e3a5f" if is_self else "#2b3a1e"
        tag_color = "#79c0ff" if is_self else "#7ee787"

        cards_html.append(f"""
        <div style="background: #252526; border: 1px solid #30363d; border-left: 3px solid {border_col}; border-radius: 6px; padding: 12px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <div style="font-weight: bold; color: #f0f6fc; font-size: 14px;">
                    PDB {pdb} &mdash; <span style="color: {border_col};">{st}</span> ({state})
                </div>
                <span style="background: {tag_bg}; color: {tag_color}; padding: 2px 8px; border-radius: 10px; font-size: 10.5px; font-weight: bold;">
                    {tag_text}
                </span>
            </div>
            <div style="font-size: 12px; color: #8b949e; margin-bottom: 4px;">
                <strong>Conditions:</strong> {cond}
            </div>
            <div style="font-size: 12px; color: #8b949e;">
                <strong>Solvation Dissociation Energy (&#916;G):</strong> <span style="color: #f0f6fc;">{dg_str}</span>
            </div>
        </div>
        """)

    html_container = f"""
    <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 15px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #c9d1d9;">
        <div style="font-size: 15px; font-weight: 700; color: #58a6ff; margin-bottom: 12px;">
            &#128260; Dynamic Multi-Assembly Equilibrium & Observed States
        </div>
        {"".join(cards_html)}
    </div>
    """
    return HTML(html_container.strip())


def render_evidence_coverage_dashboard(output: QuaternaryStructureOutput) -> HTML:
    """
    Render a structured audit table listing each database queried, status, hits, and explicit gaps.

    Parameters:
        output: QuaternaryStructureOutput model or dictionary equivalent.

    Returns:
        HTML: IPython HTML evidence coverage dashboard or empty audit banner.
    """
    if not isinstance(output, QuaternaryStructureOutput):
        if isinstance(output, dict):
            output = QuaternaryStructureOutput.model_validate(output)

    cov = output.evidence_coverage
    if not cov:
        html_empty = """
        <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 14px; margin: 15px 0; color: #8b949e; font-size: 13px;">
            <strong>Evidence Coverage:</strong> No coverage audit recorded.
        </div>
        """
        return HTML(html_empty.strip())

    db_rows = ""
    for db in cov.databases_queried:
        db_name = db.get("database", "Unknown")
        queried = db.get("queried", False)
        hit = db.get("hit", False)

        if not queried:
            status_badge = '<span style="background: #21262d; color: #8b949e; padding: 2px 6px; border-radius: 4px; font-size: 10px;">SKIPPED / UNCONFIGURED</span>'
            hit_badge = '<span style="color: #8b949e;">&mdash;</span>'
        elif hit:
            status_badge = '<span style="background: #1e3a24; color: #7ee787; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold;">&#10004; QUERIED</span>'
            hit_badge = '<span style="background: #1e3a24; color: #7ee787; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold;">HIT FOUND</span>'
        else:
            status_badge = '<span style="background: #1e3a24; color: #7ee787; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold;">&#10004; QUERIED</span>'
            hit_badge = '<span style="background: #342814; color: #d29922; padding: 2px 6px; border-radius: 4px; font-size: 10px;">NO HITS / MONOMER</span>'

        db_rows += f"""
        <tr style="border-bottom: 1px solid #30363d;">
            <td style="padding: 6px 10px; font-weight: 600; color: #f0f6fc;">{db_name}</td>
            <td style="padding: 6px 10px;">{status_badge}</td>
            <td style="padding: 6px 10px;">{hit_badge}</td>
        </tr>
        """

    if cov.evidence_gaps:
        gaps_items = "".join([f'<li style="margin-bottom: 4px;">{g}</li>' for g in cov.evidence_gaps])
        gaps_html = f"""
        <div style="margin-top: 12px; padding: 10px; background: #252526; border-radius: 6px; border-left: 3px solid #d29922;">
            <div style="font-size: 11px; text-transform: uppercase; color: #d29922; font-weight: bold; margin-bottom: 6px;">Identified Scientific Gaps & Uncertainties</div>
            <ul style="margin: 0; padding-left: 20px; font-size: 12px; color: #c9d1d9;">
                {gaps_items}
            </ul>
        </div>
        """
    else:
        gaps_html = """
        <div style="margin-top: 12px; padding: 10px; background: #252526; border-radius: 6px; border-left: 3px solid #7ee787;">
            <div style="font-size: 11px; text-transform: uppercase; color: #7ee787; font-weight: bold;">Identified Scientific Gaps</div>
            <div style="font-size: 12px; color: #8b949e; margin-top: 4px;">&#10004; Zero evidence gaps; full experimental and homology consensus achieved.</div>
        </div>
        """

    html_container = f"""
    <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 15px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #c9d1d9;">
        <div style="font-size: 15px; font-weight: 700; color: #58a6ff; margin-bottom: 12px;">
            &#128203; Evidence Coverage & Gaps Dashboard
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left;">
            <thead>
                <tr style="background: #252526; border-bottom: 2px solid #30363d; color: #8b949e; text-transform: uppercase; font-size: 10.5px;">
                    <th style="padding: 6px 10px;">Evidence Source / Database</th>
                    <th style="padding: 6px 10px;">Query Status</th>
                    <th style="padding: 6px 10px;">Result</th>
                </tr>
            </thead>
            <tbody>
                {db_rows}
            </tbody>
        </table>
        {gaps_html}
    </div>
    """
    return HTML(html_container.strip())
