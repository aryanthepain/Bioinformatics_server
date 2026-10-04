"""Compare the primary-structure module with the notebook's recorded results.

From the backend folder, after running scripts/setup_primary.sh:

    uv run python scripts/check_primary.py

It runs the notebook's four test sequences through the ported pipeline and
compares every result with the output recorded in the notebook:

  PASS  identical to the notebook
  NOTE  differs for an expected reason (e.g. a newer Swiss-Prot or Pfam
        release, or the corrected coverage calculation)
  FAIL  differs where it must not (calculation or text)

The three test proteins that are also examples in the app (AKT1,
bacteriorhodopsin, ubiquitin) are saved to the cache, so the app shows their
primary-structure results instantly afterwards.
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # lets "import app" work

from app import cache  # noqa: E402
from app.examples import find_example  # noqa: E402
from app.jobs import JobStore, StageContext  # noqa: E402
from app.levels import primary  # noqa: E402

# Recorded in the notebook (cells 4-7), copied verbatim.
NOTEBOOK_RUNS = [
    {
        "name": "AKT1 (RAC-alpha serine/threonine-protein kinase)",
        "sequence": (
            "MSDVAIVKEGWLHKRGEYIKTWRPRYFLLKNDGTFIGYKERPQDVDQREAPLNNFSVAQCQLMKTERPRP"
            "NTFIIRCLQWTTVIERTFHVETPEEREEWTTAIQTVADGLKKQEEEEMDFRSGSPSDNSGAEEMEVSLAK"
            "PKHRVTMNEFEYLKLLGKGTFGKVILVKEKATGRYYAMKILKKEVIVAKDEVAHTLTENRVLQNSRHPFL"
            "TALKYSFQTHDRLCFVMEYANGGELFFHLSRERVFSEDRARFYGAEIVSALDYLHSEKNVVYRDLKLENL"
            "MLDKDGHIKITDFGLCKEGIKDGATMKTFCGTPEYLAPEVLEDNDYGRAVDWWGLGVVMYEMMCGRLPFY"
            "NQDHEKLFELILMEEIRFPRTLGPEAKSLLSGLLKKDPKQRLGGGSEDAKEIMQHRFFAGIVWQHVYEKK"
            "LSPPFKPQVTSETDTRYFDEEFTAQMITITPPDQDDSMECVDSERRPHFPQFSYSASGTA"
        ),
        "summary": [
            '[+] DIAMOND: 100.00% identity and 100.00% query coverage to sp|P31749|AKT1_HUMAN.',
             '[+] HMMER: detected Pkinase (independent domain E-value: 1.90e-79).',
             '[+] ESM-2: successfully extracted a 320-dimensional sequence embedding.'],
        "physicochemical": {"Molecular Weight (kDa)": 55.69, "Isoelectric Point (pI)": 5.75, "Instability Index (heuristic)": 35.47, "GRAVY (mean hydropathy)": -0.575, "Alpha Helix Propensity Fraction": 0.348, "Beta Sheet Propensity Fraction": 0.356},
        "interpretation": [
            'Instability index is at or below 40. This heuristic alone does not establish experimental '
             'stability.',
             'Negative GRAVY indicates a hydrophilic sequence on average. It does not by itself establish '
             'cellular localization or solubility.',
             'At pH 7.4, the protein is expected to have a net negative charge based on its theoretical pI. '
             'Anion-exchange binding is possible, but must be tested experimentally.'],
    },
    {
        "name": "Bacteriorhodopsin",
        "sequence": (
            "MLELLPTAVEGVSQAQITGRPEWIWLALGTALMGLGTLYFLVKGMGVSDPDAKKFYAITTLVPAIAFTMY"
            "LSMLLGYGLTMVPFGGEQNPIYWARYADWLFTTPLLLLDLALLVDADQGTILALVGADGIMIGTGLVGAL"
            "TKVYSYRFVWWAISTAAMLYILYVLFFGFTSKAESMRPEVASTFKVLRNVTVVLWSAYPVVWLIGSEGAG"
            "IVPLNIETLLFMVLDVSAKVGFGLILLRSRAIFGEAEAPEPSAGDGAAATSD"
        ),
        "summary": [
            '[+] DIAMOND: 100.00% identity and 100.00% query coverage to sp|P02945|BACR_HALSA.',
             '[+] HMMER: detected Bac_rhodopsin (independent domain E-value: 2.70e-74).',
             '[+] ESM-2: successfully extracted a 320-dimensional sequence embedding.'],
        "physicochemical": {"Molecular Weight (kDa)": 28.26, "Isoelectric Point (pI)": 4.62, "Instability Index (heuristic)": 27.03, "GRAVY (mean hydropathy)": 0.723, "Alpha Helix Propensity Fraction": 0.37, "Beta Sheet Propensity Fraction": 0.489},
        "interpretation": [
            'Instability index is at or below 40. This heuristic alone does not establish experimental '
             'stability.',
             'Positive GRAVY indicates a hydrophobic sequence on average. It does not by itself establish '
             'membrane localization.',
             'At pH 7.4, the protein is expected to have a net negative charge based on its theoretical pI. '
             'Anion-exchange binding is possible, but must be tested experimentally.'],
    },
    {
        "name": "p53 (the notebook's copy, missing Arg-181)",
        "sequence": (
            "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAA"
            "PPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKT"
            "CPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHECSDSDGLAPPQHLIRVEGNLRVEYLDDRNT"
            "FRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRD"
            "RRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELK"
            "DAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD"
        ),
        "summary": [
            '[+] DIAMOND: 99.70% identity and 99.75% query coverage to sp|P04637|P53_HUMAN.',
             '[+] HMMER: detected P53 (independent domain E-value: 3.00e-62).',
             '[+] ESM-2: successfully extracted a 320-dimensional sequence embedding.'],
        "physicochemical": {"Molecular Weight (kDa)": 43.5, "Isoelectric Point (pI)": 6.2, "Instability Index (heuristic)": 74.88, "GRAVY (mean hydropathy)": -0.747, "Alpha Helix Propensity Fraction": 0.301, "Beta Sheet Propensity Fraction": 0.265},
        "interpretation": [
            'Instability index is above 40. This is a sequence-based heuristic, not a direct measurement of '
             'protein stability.',
             'Negative GRAVY indicates a hydrophilic sequence on average. It does not by itself establish '
             'cellular localization or solubility.',
             'At pH 7.4, the protein is expected to have a net negative charge based on its theoretical pI. '
             'Anion-exchange binding is possible, but must be tested experimentally.'],
    },
    {
        "name": "Ubiquitin",
        "sequence": (
            "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLV"
            "LRLRGG"
        ),
        "summary": [
            '[+] DIAMOND: 100.00% identity and 100.00% query coverage to sp|Q865C5|UBIQ_CAMDR.',
             '[+] HMMER: detected ubiquitin (independent domain E-value: 7.70e-34).',
             '[+] ESM-2: successfully extracted a 320-dimensional sequence embedding.'],
        "physicochemical": {"Molecular Weight (kDa)": 8.56, "Isoelectric Point (pI)": 6.56, "Instability Index (heuristic)": 36.06, "GRAVY (mean hydropathy)": -0.489, "Alpha Helix Propensity Fraction": 0.329, "Beta Sheet Propensity Fraction": 0.395},
        "interpretation": [
            'Instability index is at or below 40. This heuristic alone does not establish experimental '
             'stability.',
             'Negative GRAVY indicates a hydrophilic sequence on average. It does not by itself establish '
             'cellular localization or solubility.',
             'At pH 7.4, the protein is expected to have a net negative charge based on its theoretical pI. '
             'Anion-exchange binding is possible, but must be tested experimentally.'],
    },
]


class QuietContext(StageContext):
    """Prints a progress message only when the set of running tools changes."""

    last = ""

    def report(self, message: str) -> None:
        self.check_cancelled()
        stem = message.split(" · ")[0]
        if stem != self.last:
            self.last = stem
            print(f"      {time.strftime('%H:%M:%S')}  {stem}", flush=True)


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


def compare(run: dict, got: dict) -> None:
    expected_diamond, expected_hmmer, expected_esm = run["summary"]
    diamond = got["diamond"]
    hmmer = got["hmmer"]
    summary = got["consensus"]["summary"]

    # DIAMOND: hit, identity and coverage
    expected_hit = expected_diamond.rsplit(" to ", 1)[1].rstrip(".")
    expected_identity = expected_diamond.split("% identity")[0].split()[-1]
    expected_coverage = expected_diamond.split("% query coverage")[0].split()[-1]
    got_identity = f"{diamond.get('identity', 0.0):.2f}"
    got_coverage = f"{diamond.get('query_coverage', 0.0):.2f}"
    if summary[0] == expected_diamond:
        result("PASS", f"DIAMOND line identical: {summary[0]}")
    else:
        if diamond.get("best_hit") == expected_hit:
            result("PASS", f"DIAMOND best hit {expected_hit}")
        elif float(diamond.get("identity", 0.0)) >= 99.0:
            result("NOTE", f"DIAMOND best hit {diamond.get('best_hit')} instead of {expected_hit} "
                           "(an equally identical entry; your Swiss-Prot release differs from the notebook's)")
        else:
            result("FAIL", f"DIAMOND best hit {diamond.get('best_hit')} (notebook: {expected_hit})")
        if got_identity == expected_identity:
            result("PASS", f"DIAMOND identity {got_identity}%")
        else:
            result("NOTE", f"DIAMOND identity {got_identity}% (notebook: {expected_identity}%; DIAMOND or database version differs)")
        if got_coverage == expected_coverage:
            result("PASS", f"DIAMOND coverage {got_coverage}%")
        elif expected_coverage == "99.75" and got_coverage == "100.00":
            result("NOTE", "DIAMOND coverage 100.00% (notebook printed 99.75% because of its column-index bug; "
                           "this query is aligned end to end, so 100% is correct)")
        else:
            result("FAIL", f"DIAMOND coverage {got_coverage}% (notebook: {expected_coverage}%)")

    # HMMER: best domain and its E-value
    expected_domain = expected_hmmer.split("detected ")[1].split(" (")[0]
    expected_evalue = float(expected_hmmer.split("E-value: ")[1].rstrip(").").strip())
    if summary[1] == expected_hmmer:
        result("PASS", f"HMMER line identical: {summary[1]}")
    elif hmmer.get("domain") == expected_domain:
        ratio = max(hmmer["e_value"], expected_evalue) / max(min(hmmer["e_value"], expected_evalue), 1e-300)
        kind = "NOTE" if ratio < 1e6 else "FAIL"
        result(kind, f"HMMER domain {expected_domain}, E-value {hmmer['e_value']:.2e} (notebook {expected_evalue:.2e}; "
                     "E-values shift slightly between Pfam releases)")
    else:
        result("FAIL", f"HMMER best domain {hmmer.get('domain')} (notebook: {expected_domain})")

    # ESM-2
    if len(summary) > 2 and summary[2] == expected_esm:
        result("PASS", "ESM-2 line identical (320-dimensional embedding)")
    else:
        result("FAIL", f"ESM-2 line differs: {summary[2:] or 'missing'}")

    # Score
    if got["consensus"]["evidence_score"] == 90:
        result("PASS", "evidence score 90 / 90")
    else:
        result("FAIL", f"evidence score {got['consensus']['evidence_score']} / 90 (notebook: 90 / 90)")

    # ProtParam: must be identical
    for key, value in run["physicochemical"].items():
        actual = got["physicochemical"].get(key)
        result("PASS" if actual == value else "FAIL", f"{key}: {actual} (notebook: {value})")

    # Interpretation: must be identical
    texts = [text for _, text in got["interpretation"]]
    for expected, actual in zip(run["interpretation"], texts):
        result("PASS" if expected == actual else "FAIL", f"interpretation: {actual[:70]}…")


def main() -> int:
    missing = primary.missing_setup()
    if missing:
        print("FAIL  Not set up yet. Missing: " + ", ".join(missing))
        print("      Run: bash scripts/setup_primary.sh")
        return 1

    ctx = QuietContext(JobStore(), "check", "primary", threading.Event())
    print("Loading the pipeline (ESM-2 model)…")
    pipeline = primary.get_pipeline(ctx)

    for run in NOTEBOOK_RUNS:
        print(f"\n{run['name']} ({len(run['sequence'])} residues)")
        started = time.monotonic()
        got = pipeline.execute(run["sequence"], ctx)
        print(f"      finished in {time.monotonic() - started:.0f} s")
        compare(run, got)
        if find_example(run["sequence"]) is not None:
            level_result = primary._to_level_result(run["sequence"], got, pipeline)
            cache.store("primary", primary.CACHE_VERSION, run["sequence"], level_result)

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
