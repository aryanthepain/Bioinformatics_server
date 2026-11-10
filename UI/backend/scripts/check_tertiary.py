"""Compare the tertiary-structure module with the notebook's recorded result.

From the backend folder (needs the internet; no account or token):

    uv run python scripts/check_tertiary.py

It runs the notebook's own example of "Tertiary_protein_identification.ipynb" -
UniProt ID P99999 with the human cytochrome c sequence - through the ported
module (AlphaFold DB, Foldseek, ProtParam, structure analysis, UniProt) and
compares every printed value with the output recorded in the notebook. It
takes about a minute.

  PASS  identical to the notebook
  NOTE  differs for an expected reason (a newer AlphaFold DB model, Foldseek
        database or Biopython release)
  FAIL  differs where it must not

In the app the UniProt ID comes from the primary level's closest Swiss-Prot match.
"""

import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # lets "import app" work

from app.jobs import JobStore, LevelSkipped, StageContext  # noqa: E402
from app.levels import tertiary  # noqa: E402
from app.levels.quaternary import Homologue  # noqa: E402

UNIPROT_ID = "P99999"
UNKNOWN_SEQ = "MGDVEKGKKIFIMKCSQCHTVEKGGKHKTGPNLHGLFGRKTGQAPGYSYTAANKNKGIIWGEDTLMEYLENPKKYIPGTKMIFVGIKKKEERADLIAYLKKATNE"

# The notebook's recorded output for this example.
EXPECTED = {
    "afdb50": ("AF-A0A1S3FTQ6-F1-model_v6 Cytochrome c, somatic", 4.679e-21),
    "pdb100": ("5dfs-assembly2.cif.gz_B Crystal structure of Spider Monkey Cytochrome C at 1.15 Angstrom", 4.954e-21),
    "molecular_weight_da": 11748.60,
    "isoelectric_point": 9.59,
    "gravy": -0.706,
    "instability_index": 11.38,
    "atoms": 824,
    "dimensions_angstrom": [37.4, 33.7, 34.8],
    "mean_plddt": 97.9,
    "disordered": [],
    "secondary_structure": {"helix": 0.40, "strand": 0.02, "coil": 0.58},
    "radius_of_gyration": 12.5,
    "radius_of_gyration_expected": 12.9,
    "residues": 105,
    "surface_hydrophobic_fraction": 0.19,
    "surface_net_charge": 9,
    "best_prob": 1.00,
    "best_seq_id": 91.4,
    "best_coverage": 1.00,
    "annotation_accession": "A0A1S3FTQ6",
    "annotation_name": "n/a",
    "annotation_function_start": "Electron carrier protein. The oxidized form of the cytochrome c heme group",
    "sites": 0,
}


class PrintingContext(StageContext):
    """Prints progress messages instead of sending them to the web page."""

    last = ""

    def report(self, message: str) -> None:
        self.check_cancelled()
        stem = message.split(" · ")[0]
        if stem != self.last:
            self.last = stem
            print(f"  {time.strftime('%H:%M:%S')}  {stem}", flush=True)


passes = notes = 0
failures: list[str] = []


def result(kind: str, text: str) -> None:
    global passes, notes
    print(f"  {kind:<4}  {text}")
    if kind == "PASS":
        passes += 1
    elif kind == "NOTE":
        notes += 1
    else:
        failures.append(text)


def compare(label: str, actual: Any, expected: Any, digits: int, note_within: float, why: str) -> None:
    """PASS when equal at the notebook's printed precision, NOTE when close, otherwise FAIL."""
    if actual is None:
        result("FAIL", f"{label}: missing (notebook: {expected})")
    elif round(float(actual), digits) == round(float(expected), digits):
        result("PASS", f"{label} {round(float(actual), digits)}")
    elif abs(float(actual) - float(expected)) <= note_within:
        result("NOTE", f"{label} {round(float(actual), digits)} (notebook: {expected}; {why})")
    else:
        result("FAIL", f"{label} {round(float(actual), digits)} (notebook: {expected})")


def main() -> int:
    print(f"Running the tertiary module on the notebook's example ({UNIPROT_ID}, {len(UNKNOWN_SEQ)} residues).\n")
    ctx = PrintingContext(JobStore(), "check", "tertiary", threading.Event())
    template = Homologue(accession=UNIPROT_ID, entry="CYC_HUMAN", protein="Cytochrome c", organism="Homo sapiens",
                         gene="CYCS", identity=100.0, coverage=100.0, passed=True)
    started = time.monotonic()
    try:
        level = tertiary.run(UNKNOWN_SEQ, template, ctx)
    except LevelSkipped as skip:
        print(f"\nFAIL  Skipped: {skip}")
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 1
    except Exception as error:  # show the reason plainly
        print(f"\nFAIL  {error}")
        return 1
    print(f"\nFinished in {time.monotonic() - started:.0f} s.\n")

    raw = level.raw or {}
    print("The notebook's report, as the module produced it:")
    for line in raw["report"]:
        print(f"      {line}")
    print()

    model_why = "the AlphaFold DB model or Foldseek database was updated"
    for database in ("afdb50", "pdb100"):
        target, evalue = EXPECTED[database]
        hit = raw["foldseek_top_hits"].get(database)
        if hit is None:
            result("FAIL", f"Foldseek {database}: no hit (notebook: {target})")
        elif hit.get("target") == target:
            result("PASS", f"Foldseek {database}: {target}")
            compare(f"Foldseek {database} E-value", hit.get("eval"), evalue, 24, evalue * 10, model_why)
        elif "ytochrome" in str(hit.get("target")):
            result("NOTE", f"Foldseek {database}: {hit.get('target')} (notebook: {target}; {model_why})")
        else:
            result("FAIL", f"Foldseek {database}: {hit.get('target')} (notebook: {target})")

    props = raw["properties"]
    biopython = "Biopython version differs"
    compare("Molecular weight", props["molecular_weight_da"], EXPECTED["molecular_weight_da"], 2, 1.0, biopython)
    compare("Isoelectric point", props["isoelectric_point"], EXPECTED["isoelectric_point"], 2, 0.05, biopython)
    compare("GRAVY", props["gravy"], EXPECTED["gravy"], 3, 0.005, biopython)
    compare("Instability index", props["instability_index"], EXPECTED["instability_index"], 2, 0.1, biopython)
    compare("Atoms in the model", raw["model"]["atoms"], EXPECTED["atoms"], 0, 20, model_why)
    for axis, actual, expected in zip("xyz", raw["model"]["dimensions_angstrom"], EXPECTED["dimensions_angstrom"], strict=True):
        compare(f"Model span {axis} (Å)", actual, expected, 1, 1.0, model_why)

    structure = raw["structure"]
    compare("Residues", structure["residues"], EXPECTED["residues"], 0, 0, model_why)
    compare("Mean pLDDT", structure["mean_plddt"], EXPECTED["mean_plddt"], 1, 1.5, model_why)
    result("PASS" if structure["disordered"] == EXPECTED["disordered"] else "NOTE",
           f"Disordered regions {structure['disordered']} (notebook: none)")
    ss = structure["secondary_structure"]
    if ss is None:
        result("FAIL", "Secondary structure was not computed (is pydssp installed? run: uv add --group primary pydssp)")
    else:
        for key in ("helix", "strand", "coil"):
            compare(f"Secondary structure {key}", ss[key], EXPECTED["secondary_structure"][key], 2, 0.03, model_why)
    compare("Radius of gyration (Å)", structure["radius_of_gyration"], EXPECTED["radius_of_gyration"], 1, 0.3, model_why)
    compare("Expected radius (Å)", structure["radius_of_gyration_expected"], EXPECTED["radius_of_gyration_expected"], 1, 0, "")
    compare("Hydrophobic surface", structure["surface_hydrophobic_fraction"], EXPECTED["surface_hydrophobic_fraction"], 2,
            0.03, model_why)
    compare("Net exposed charge", structure["surface_net_charge"], EXPECTED["surface_net_charge"], 0, 2, model_why)

    best = raw["best_hit"] or {}
    compare("Best match probability", best.get("prob"), EXPECTED["best_prob"], 2, 0.05, model_why)
    compare("Best match sequence identity", best.get("seqId"), EXPECTED["best_seq_id"], 1, 5.0, model_why)
    compare("Best match coverage", best.get("coverage"), EXPECTED["best_coverage"], 2, 0.05, model_why)

    transfer = raw["annotation_transfer"]
    annotation = transfer.get("annotation") or {}
    if transfer["status"] != "transferred":
        result("FAIL", f"Annotation transfer: {transfer['status']} (notebook: transferred from A0A1S3FTQ6)")
    else:
        same = annotation.get("accession") == EXPECTED["annotation_accession"]
        result("PASS" if same else "NOTE", f"Annotation source {annotation.get('accession')} ({annotation.get('name')})")
        function = str(annotation.get("function") or "")
        if function.startswith(EXPECTED["annotation_function_start"]):
            result("PASS", "Annotated function: Electron carrier protein…")
        elif same:
            result("FAIL", f"Annotated function: {function[:80]}…")
        else:
            result("NOTE", f"Annotated function: {function[:80]}… (a different AlphaFold DB match)")
        sites = annotation.get("sites") or []
        result("PASS" if len(sites) == EXPECTED["sites"] else "NOTE", f"Transferred sites: {len(sites)} (notebook: none)")

    print(f"\n{passes} passed, {notes} notes, {len(failures)} failed")
    if failures:
        print("\nFAILED:")
        for text in failures:
            print(f"  - {text}")
        return 1
    print("PASS  The ported module reproduces the notebook (any NOTE lines are explained above).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
