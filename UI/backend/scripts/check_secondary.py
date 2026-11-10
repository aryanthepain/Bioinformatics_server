"""Compare the secondary-structure module with the final notebook's recorded results.

From the backend folder, after `uv sync` and `uv run python scripts/setup_secondary.py`:

    uv run python scripts/check_secondary.py              # hemoglobin alpha (under a minute)
    uv run python scripts/check_secondary.py --examples   # also cache every example of the app

It analyses the notebook's test protein, human hemoglobin alpha, with the ported
module and compares the result with the output recorded in
"SecondaryStructureFinal.ipynb" (cell 4, run on a CPU): the five predictors' states
and scores for the first 12 residues, the consensus profile, the consensus regions
and the pairwise agreement between the predictors. It then runs the repeat (warm)
call, as the notebook's RUN_REPEAT_BENCHMARK does, and the comparison with
experimental PDB structures, which the app runs in the background (the notebook
leaves it off, so it has no recorded output to compare with).

  PASS  identical to the notebook
  NOTE  differs for an expected reason: the neural predictors' arithmetic differs
        very slightly between computers (a residue whose two best states are almost
        tied can flip), or the PDB lookup needs the internet
  FAIL  differs where it must not

Results for the app's example proteins are saved to the cache, so the app shows
their secondary-structure results instantly afterwards.
"""

import argparse
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # lets "import app" work

from app import cache  # noqa: E402
from app.examples import EXAMPLES, find_example  # noqa: E402
from app.jobs import JobStore, StageContext  # noqa: E402
from app.levels import secondary  # noqa: E402

# The notebook's input (cell 1).
PROTEIN_NAME = "Human Hemoglobin Alpha"
SEQUENCE = (
    "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDP"
    "VNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"
)

# Recorded in the notebook's cell 4, copied verbatim.
PROFILE = {"H": (92, 64.788732), "E": (0, 0.0), "C": (43, 30.281690), "U": (7, 4.929577)}
REGIONS = [
    ("C", 1, 4, 4), ("H", 5, 36, 32), ("C", 37, 39, 3), ("U", 40, 41, 2), ("C", 42, 53, 12), ("U", 54, 56, 3),
    ("C", 57, 58, 2), ("H", 59, 72, 14), ("C", 73, 76, 4), ("H", 77, 89, 13), ("C", 90, 96, 7), ("U", 97, 98, 2),
    ("H", 99, 112, 14), ("C", 113, 119, 7), ("H", 120, 138, 19), ("C", 139, 142, 4),
]
PREDICTORS = ["S4PRED", "ESM-2 SS3", "PSIPRED-single", "GOR IV", "Chou–Fasman"]
AGREEMENT = [  # rows and columns in PREDICTORS order
    [100.0, 85.2, 84.5, 69.0, 50.0],
    [85.2, 100.0, 78.2, 65.5, 52.8],
    [84.5, 78.2, 100.0, 80.3, 42.3],
    [69.0, 65.5, 80.3, 100.0, 33.8],
    [50.0, 52.8, 42.3, 33.8, 100.0],
]
# The first 12 residues of the residue table: each predictor's states and scores.
FIRST_12 = {
    "S4PRED": ("CCCCHHHHHHHH", [0.999466, 0.998235, 0.994546, 0.994079, 0.849820, 0.820281, 0.790608, 0.819336,
                                0.844299, 0.837038, 0.944481, 0.953744]),
    "ESM-2 SS3": ("CCCHHHHHHHHH", [0.863064, 0.888866, 0.914227, 0.819786, 0.842611, 0.856038, 0.906078, 0.888487,
                                   0.879929, 0.917647, 0.933423, 0.934540]),
    "PSIPRED-single": ("CCCCHHHCCCCH", [0.999, 0.906, 0.913, 0.965, 0.695, 0.535, 0.545, 0.608, 0.607, 0.752, 0.642,
                                        0.622]),
    "GOR IV": ("CCCCCCCCCCHH", [0.999525, 0.999678, 0.998445, 0.998112, 0.996499, 0.989468, 0.966153, 0.826036,
                                0.500536, 0.429840, 0.494114, 0.511537]),
    "Chou–Fasman": ("HHHHHHHHHHHH", None),
}
FIRST_12_CONSENSUS = "CCCCHHHHHHHH"
FIRST_12_VOTES = [4, 4, 4, 3, 4, 4, 4, 3, 3, 3, 4, 5]
FIRST_12_NEURAL = "CCCCHHHHHHHH"
NOTEBOOK_SECONDS = {"first": 35.25, "warm": 3.28}  # Colab CPU, cell 4
DETERMINISTIC = {"PSIPRED-single", "GOR IV", "Chou–Fasman"}  # same answer on every computer
TOLERATED_FLIPS = 2  # neural predictors: residues whose consensus may flip on another computer


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


def expected_consensus() -> str:
    return "".join(state * length for state, _, _, length in REGIONS)


def compare_report(report: dict[str, Any]) -> None:
    table = report["secondary_structure_table"]
    used = report["predictors_used"]
    result("PASS" if used == PREDICTORS else "FAIL", f"{len(used)}/5 methods: {', '.join(used)}")
    for row in report["timings"].itertuples(index=False):
        if row.Status != "OK":
            result("FAIL", f"{row.Predictor}: {row.Status}")

    print("\n  The first 12 residues of the residue table")
    for name, (states, scores) in FIRST_12.items():
        if name not in used:
            continue
        got = "".join(table[name].tolist()[:12])
        if got == states:
            result("PASS", f"{name} states {got}")
        else:
            result("FAIL", f"{name} states {got} (notebook: {states})")
        if scores is None:
            continue
        got_scores = [float(value) for value in table[f"{name}_Score"].tolist()[:12]]
        digits = 3 if name == "PSIPRED-single" else 6
        largest = max(abs(a - b) for a, b in zip(got_scores, scores, strict=True))
        shown = ", ".join(f"{value:.{min(digits, 4)}f}" for value in got_scores[:4])
        if all(round(a, digits) == round(b, digits) for a, b in zip(got_scores, scores, strict=True)):
            result("PASS", f"{name} scores {shown}, …")
        elif largest < 0.01 and name not in DETERMINISTIC:
            result("NOTE", f"{name} scores differ by up to {largest:.4f} (arithmetic differs slightly between computers)")
        elif largest < 0.001:
            result("NOTE", f"{name} scores differ by up to {largest:.5f} (rounding)")
        else:
            result("FAIL", f"{name} scores differ by up to {largest:.4f}: {shown}, … (notebook: {scores[:4]}, …)")
    consensus12 = "".join(table["Consensus"].tolist()[:12])
    votes12 = [int(value) for value in table["Votes_for_top_call"].tolist()[:12]]
    neural12 = "".join(table["Neural_consensus"].tolist()[:12])
    same = (consensus12, votes12, neural12) == (FIRST_12_CONSENSUS, FIRST_12_VOTES, FIRST_12_NEURAL)
    result("PASS" if same else "FAIL",
           f"consensus {consensus12}, votes {votes12}, neural consensus {neural12}, models "
           f"{int(table['Models_available'].iloc[0])}")

    print("\n  Consensus profile, regions and pairwise agreement")
    consensus = report["secondary_structure"]
    flips = sum(a != b for a, b in zip(consensus, expected_consensus(), strict=True))
    kind_if_close = "NOTE" if flips <= TOLERATED_FLIPS else "FAIL"
    if flips:
        print(f"        The consensus differs from the notebook's at {flips} residue(s).")
    profile = report["profile"]
    for state, (residues, percent) in PROFILE.items():
        got_residues, got_percent = int(profile.loc[state, "Residues"]), float(profile.loc[state, "Percent"])
        same = got_residues == residues and round(got_percent, 6) == round(percent, 6)
        result("PASS" if same else kind_if_close,
               f"{state}: {got_residues} residues, {got_percent:.6f}%" + ("" if same else f" (notebook: {residues}, {percent}%)"))
    regions = [(str(row.State), int(row.Start), int(row.End), int(row.Length))
               for row in report["regions"].itertuples(index=False)]
    if regions == REGIONS:
        result("PASS", f"the notebook's {len(REGIONS)} consensus regions")
    else:
        first = next((i for i, (a, b) in enumerate(zip(regions, REGIONS)) if a != b), min(len(regions), len(REGIONS)))
        result(kind_if_close, f"{len(regions)} regions (notebook: {len(REGIONS)}); first difference: "
                              f"{regions[first] if first < len(regions) else 'none'} "
                              f"(notebook: {REGIONS[first] if first < len(REGIONS) else 'none'})")
    matrix = report["pairwise_agreement_percent"]
    if used == PREDICTORS:
        got = [[round(float(matrix.loc[left, right]), 1) for right in PREDICTORS] for left in PREDICTORS]
        if got == AGREEMENT:
            result("PASS", "pairwise agreement matrix (S4PRED/ESM-2 85.2, S4PRED/PSIPRED 84.5, …)")
        else:
            largest = max(abs(a - b) for row_a, row_b in zip(got, AGREEMENT) for a, b in zip(row_a, row_b))
            result(kind_if_close if largest <= 100 * TOLERATED_FLIPS / len(SEQUENCE) + 0.05 else "FAIL",
                   f"pairwise agreement differs by up to {largest:.1f} points: {got}")


def compare_warm(first: dict[str, Any], warm: dict[str, Any]) -> None:
    same = (warm["secondary_structure"] == first["secondary_structure"]
            and warm["predictors_used"] == first["predictors_used"])
    result("PASS" if same else "FAIL", "the repeat call gives the same consensus")


def run_pdb(raw: dict[str, Any], ctx: StageContext) -> dict[str, Any]:
    """The app's background step (secondary.refine): compare_pdb_references, retried while RCSB is busy."""
    print("\nComparison with experimental PDB structures (the app's background step; off in the notebook)")
    level = secondary.refine(SEQUENCE, secondary.build_level_result(raw), ctx)
    pdb = (level.raw or {})["pdb_references"]
    if pdb["status"] != "success":
        result("NOTE", f"PDB lookup unavailable after {pdb.get('attempts', 1)} attempt(s) | {pdb.get('error')} "
                       "(needs the internet; RCSB's search is sometimes busy, try again later)")
        return pdb
    print(f"      PDB reference lookup | {pdb['seconds']:.2f} s, attempt {pdb.get('attempts', 1)}")
    for row in pdb["rows"]:
        if row["Status"] == "OK":
            agreement = "—" if row["SS_agreement_pct"] is None else f"{row['SS_agreement_pct']:.1f}%"
            print(f"      {row['PDB_entity']}: query aligned {row['Aligned_query_pct']:.1f}%, identity "
                  f"{row['Aligned_identity_pct']:.1f}%, {row['Comparable_residues']} comparable, agreement {agreement}")
        else:
            print(f"      {row['PDB_entity']}: {row['Status']}")
    compared = [row for row in pdb["rows"] if row["Status"] == "OK"]
    result("PASS" if compared else "NOTE",
           f"{len(compared)} of {len(pdb['rows'])} experimental structures compared"
           + ("" if compared else " (hemoglobin alpha has many PDB structures; is the internet reachable?)"))
    return pdb


def run_example(name: str, sequence: str, ctx: StageContext) -> None:
    print(f"\nApp example {name} ({len(sequence)} residues), for the cache")
    level = secondary.analyze(sequence, ctx)
    if secondary.needs_refinement(level):
        level = secondary.refine(sequence, level, ctx)
    print(f"      {level.summary}")
    failed = [row for row in (level.raw or {})["timings"] if row["Status"] != "OK"]
    for row in failed:
        result("FAIL", f"{name}: {row['Predictor']}: {row['Status']}")
    cache.store("secondary", secondary.CACHE_VERSION, sequence, level)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--examples", action="store_true", help="also run and cache every example of the app")
    args = parser.parse_args()

    missing = secondary.missing_setup()
    if missing:
        print("FAIL  Not set up yet. Missing: " + ", ".join(missing))
        print("      Run: uv sync, then uv run python scripts/setup_secondary.py")
        return 1
    secondary._import_libraries()
    ctx = PrintingContext(JobStore(), "check", "secondary", threading.Event())

    print(f"The notebook's example: {PROTEIN_NAME} ({len(SEQUENCE)} residues), on {secondary.DEVICE}\n")
    report = secondary.analyze_secondary_structure(SEQUENCE, PROTEIN_NAME, ctx)
    print(f"\n      {len(report['predictors_used'])}/5 methods | first call {report['elapsed_seconds']:.2f} s "
          f"(notebook: {NOTEBOOK_SECONDS['first']} s on a Colab CPU)")
    for row in report["timings"].itertuples(index=False):
        load = "—" if row.Load_s != row.Load_s or row.Load_s is None else f"{row.Load_s:.2f} s"
        predict = "—" if row.Predict_s != row.Predict_s or row.Predict_s is None else f"{row.Predict_s:.3f} s"
        print(f"      {row.Predictor:<15} load {load:>9}  predict {predict:>9}  {row.Status}")
    compare_report(report)

    warm = secondary.analyze_secondary_structure(SEQUENCE, PROTEIN_NAME)
    print(f"\n      Warm inference and report | {warm['elapsed_seconds']:.2f} s (notebook: {NOTEBOOK_SECONDS['warm']} s)")
    compare_warm(report, warm)

    raw = secondary._report_to_raw(report)
    raw["pdb_references"] = run_pdb(raw, ctx)

    print("\nInterface result")
    level = secondary.build_level_result(raw)
    length = len(SEQUENCE)
    covered = all(
        track.segments
        and track.segments[0].start == 1
        and track.segments[-1].end == length
        and all(nxt.start == cur.end + 1 for cur, nxt in zip(track.segments, track.segments[1:]))
        for track in level.tracks
    )
    result("PASS" if covered and level.source == "live" else "FAIL",
           f"{len(level.tracks)} residue tracks, {len(level.tables)} tables; headline "
           f"{level.headline.value} ({level.headline.label})")
    if not failures and find_example(SEQUENCE) is not None:
        cache.store("secondary", secondary.CACHE_VERSION, SEQUENCE, level)
        print("      Saved to the cache: the app now shows hemoglobin alpha's secondary structure instantly.")

    if args.examples:
        for example in EXAMPLES:
            if example.sequence != SEQUENCE:
                run_example(example.name, example.sequence, ctx)

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
