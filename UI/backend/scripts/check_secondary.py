"""Compare the secondary-structure module with the notebook's recorded results.

From the backend folder (needs internet; the first run also downloads the
ProtBert-BFD-SS3 model, about 1.7 GB, once):

    uv run python scripts/check_secondary.py

It analyses the notebook's test protein, human hemoglobin alpha (UniProt
P69905), with the ported pipeline and compares the result with the output
recorded in the notebook. JPred usually needs 1-5 minutes.

  PASS  identical to the notebook
  NOTE  differs for an expected reason: the PDB has grown since the notebook
        was run, or ProtBert's arithmetic differs very slightly between
        computers (a residue whose two best states are almost tied can flip)
  FAIL  differs where it must not

Hemoglobin alpha is also an example in the app, so a result without failures
is saved to the cache and the app shows it instantly afterwards.
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # lets "import app" work

from app import cache  # noqa: E402
from app.jobs import JobStore, StageContext  # noqa: E402
from app.levels import secondary  # noqa: E402

# The notebook's test protein (cells 1 and 41).
SEQUENCE = (
    "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNA"
    "LSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"
)

# Recorded in the notebook, copied verbatim.
JPRED_STATES = {"H": 97, "E": 0, "C": 45}  # cell 11
JPRED_CONFIDENCE = {"High": 101, "Medium": 16, "Low": 25}  # cell 15
JPRED_HELIX_REGIONS = [(5, 18), (22, 37), (54, 72), (77, 90), (100, 113), (120, 139)]  # cell 13
CONSENSUS_STATES = {"H": 95, "E": 0, "C": 30, "U": 17}  # cell 26
PROFILE = {  # cell 41
    "alpha_helix_percent": "66.90",
    "beta_strand_percent": "0.00",
    "coil_percent": "21.13",
    "uncertain_percent": "11.97",
}
AGREEMENT = "88.03"  # cells 25 and 41
HELIX_REGIONS = [(5, 18), (22, 36), (54, 72), (78, 90), (100, 113), (120, 139)]  # cell 41
STRAND_REGIONS: list[tuple[int, int]] = []  # cell 41
# Cell 41, in the notebook's order: identity %, comparable residues, SS agreement %,
# then the experimental helix, strand and coil residue counts.
PDB_TABLE = {
    "1BZ1_1": ("100.0", 125, "96.8", 107, 0, 35),
    "6KYE_1": ("100.0", 125, "96.8", 104, 0, 38),
    "7UF6_1": ("100.0", 125, "96.8", 106, 0, 36),
    "7UD8_1": ("100.0", 125, "96.0", 111, 0, 31),
    "7CUE_1": ("100.0", 125, "96.0", 105, 0, 37),
    "7UD7_1": ("100.0", 125, "94.4", 110, 0, 32),
    "1Y01_2": ("100.0", 125, "88.8", 91, 0, 51),
    "3IA3_2": ("100.0", 125, "88.0", 93, 0, 52),
    "1Z8U_2": ("100.0", 125, "88.0", 96, 0, 46),
    "7K4M_1": ("100.0", 125, "81.6", 93, 0, 49),
}
# On another computer ProtBert may differ from the notebook's run by this many residues.
TOLERATED_FLIPS = 2


class PrintingContext(StageContext):
    """Prints progress messages instead of sending them to the web page."""

    def report(self, message: str) -> None:
        self.check_cancelled()
        print(f"      {time.strftime('%H:%M:%S')}  {message}", flush=True)


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


def verdict(identical: bool, close: bool) -> str:
    return "PASS" if identical else ("NOTE" if close else "FAIL")


def tally(states: list[str], keys: tuple[str, ...]) -> dict[str, int]:
    return {key: states.count(key) for key in keys}


def show(counts: dict[str, int]) -> str:
    return ", ".join(f"{key} {value}" for key, value in counts.items())


def pdb_row(row: dict) -> tuple:
    def one_decimal(value: float | None) -> str:
        return "—" if value is None else f"{value:.1f}"

    return (
        one_decimal(row["Sequence_Identity_%"]),
        row["Comparable_Residues"],
        one_decimal(row["SS_Agreement_%"]),
        row["Experimental_Helix_Residues"],
        row["Experimental_Strand_Residues"],
        row["Experimental_Coil_Residues"],
    )


def main() -> int:
    missing = secondary.missing_setup()
    if missing:
        print("FAIL  Not set up yet. Missing: " + ", ".join(missing))
        print("      Run `uv sync` in UI/backend first.")
        return 1

    print(f"Analysing human hemoglobin alpha ({len(SEQUENCE)} residues) with the secondary-structure module.")
    print("Needs internet. JPred usually takes 1-5 minutes; the first run also downloads")
    print("ProtBert-BFD-SS3 (about 1.7 GB). Press Ctrl+C to stop.\n")
    ctx = PrintingContext(JobStore(), "check", "secondary", threading.Event())
    started = time.monotonic()
    try:
        results = secondary.analyze_secondary_structure(SEQUENCE, ctx)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 1
    except Exception as error:  # show the reason plainly
        print(f"\nFAIL  {error.__class__.__name__}: {error}")
        return 1
    minutes = (time.monotonic() - started) / 60
    print(f"\nFinished in {minutes:.1f} minutes (JPred job {results['jpred_job_id']}).\n")

    table = results["secondary_structure_table"]

    print("JPred on its own (the same on every computer)")
    got = tally(table["JPred"], ("H", "E", "C"))
    result("PASS" if got == JPRED_STATES else "FAIL", f"states: {show(got)} (notebook: {show(JPRED_STATES)})")
    levels = [secondary.confidence_level(value) for value in table["JPred_Confidence"]]
    got = tally(levels, ("High", "Medium", "Low"))
    result("PASS" if got == JPRED_CONFIDENCE else "FAIL", f"confidence: {show(got)} (notebook: {show(JPRED_CONFIDENCE)})")
    got_regions = secondary.get_regions(table["JPred"], "H")
    result(
        "PASS" if got_regions == JPRED_HELIX_REGIONS else "FAIL",
        f"helix regions: {got_regions}" + ("" if got_regions == JPRED_HELIX_REGIONS else f" (notebook: {JPRED_HELIX_REGIONS})"),
    )

    print("\nConsensus with ProtBert")
    consensus = table["Consensus"]
    got = tally(consensus, ("H", "E", "C", "U"))
    expected_helix = {i for start, end in HELIX_REGIONS for i in range(start, end + 1)}
    got_helix = {i for i, state in enumerate(consensus, start=1) if state == "H"}
    flips = max(
        (sum(abs(got[key] - CONSENSUS_STATES[key]) for key in got) + 1) // 2,
        len(expected_helix ^ got_helix),
        got["E"],
    )
    close = flips <= TOLERATED_FLIPS
    if flips:
        print(f"        ProtBert differs from the notebook's run at {flips} residue(s) or more.")
    result(verdict(got == CONSENSUS_STATES, close), f"consensus: {show(got)} (notebook: {show(CONSENSUS_STATES)})")
    for key, expected in PROFILE.items():
        value = f"{results['profile'][key]:.2f}"
        result(verdict(value == expected, close), f"{key}: {value}% (notebook: {expected}%)")
    value = f"{results['predictor_agreement_percent']:.2f}"
    result(verdict(value == AGREEMENT, close), f"JPred / ProtBert agreement: {value}% (notebook: {AGREEMENT}%)")
    for label, got_list, expected_list in (
        ("helix regions", results["helix_regions"], HELIX_REGIONS),
        ("strand regions", results["strand_regions"], STRAND_REGIONS),
    ):
        same = list(got_list) == expected_list
        result(verdict(same, close), f"{label}: {list(got_list) or 'none'}" + ("" if same else f" (notebook: {expected_list or 'none'})"))

    print("\nExperimental structures (RCSB PDB / PDBe)")
    rows = {row["PDB_entity"]: row for row in results["experimental_comparison"]}
    print(f"        RCSB returned {len(results['rcsb_hits'])} entities; {len(rows)} were compared.")
    for entity, expected in PDB_TABLE.items():
        if entity not in rows:
            result("NOTE", f"{entity}: not among this run's top {secondary.MAX_PDB_HITS} RCSB hits (the PDB keeps growing)")
            continue
        got_row = pdb_row(rows[entity])
        described = (
            f"identity {got_row[0]}%, {got_row[1]} comparable, agreement {got_row[2]}%, "
            f"helix {got_row[3]} / strand {got_row[4]} / coil {got_row[5]}"
        )
        if got_row == expected:
            result("PASS", f"{entity}: {described}")
        elif close and got_row[0] == expected[0] and got_row[3:] == expected[3:]:
            result("NOTE", f"{entity}: {described} (notebook: {expected[1]} comparable, {expected[2]}%; "
                           "follows the ProtBert difference above)")
        else:
            result("FAIL", f"{entity}: {described} (notebook: {expected})")
    for entity in rows:
        if entity not in PDB_TABLE:
            result("NOTE", f"{entity}: new in this run (not among the notebook's top {secondary.MAX_PDB_HITS})")
    order = [entity for entity in rows if entity in PDB_TABLE]
    expected_order = [entity for entity in PDB_TABLE if entity in rows]
    if order == expected_order:
        result("PASS", "the table is in the notebook's order")
    else:
        result("NOTE", f"order {order} (notebook: {expected_order}); rows with equal agreement are ordered "
                       "by numpy's sort, which can differ between computers")

    print("\nInterface result")
    level = secondary._to_level_result(results)
    length = len(SEQUENCE)
    covered = all(
        track.segments
        and track.segments[0].start == 1
        and track.segments[-1].end == length
        and all(nxt.start == cur.end + 1 for cur, nxt in zip(track.segments, track.segments[1:]))
        for track in level.tracks
        if track.style == "states"
    )
    result(
        "PASS" if covered and level.source == "live" else "FAIL",
        f"{len(level.tracks)} residue tracks, {len(level.tables)} tables; headline "
        f"{level.headline.value} ({level.headline.label})",
    )

    print(f"\n{passes} passed, {notes} notes, {len(failures)} failed")
    if failures:
        print("\nNot saved to the cache because of the failures below.")
        print("FAILED:")
        for text in failures:
            print(f"  - {text}")
        return 1
    cache.store("secondary", secondary.CACHE_VERSION, SEQUENCE, level)
    print("Saved to the cache: the app now shows hemoglobin alpha's secondary structure instantly.")
    print("PASS  The ported module reproduces the notebook (any NOTE lines are explained above).")
    return 0


if __name__ == "__main__":
    sys.exit(main())