"""Run the quaternary-structure level once, outside the web app.

From the backend folder:

    uv run python scripts/check_quaternary.py             hemoglobin alpha, compared with the recorded run
    uv run python scripts/check_quaternary.py --offline   GroEL from the package's test data (no internet)
    uv run python scripts/check_quaternary.py --examples  every example with a cached primary result,
                                                          plus a preview of the final verdict

The default run analyses UniProt P69905 (human hemoglobin alpha, one of the
app's examples) as the app does, and compares the result with the run your
teammate recorded in October 2026 (schema/fixtures/ui_examples/hemoglobin_alpha.json
on the main branch). It needs internet and usually takes under a minute.

  PASS  same as the recorded run, or the result follows the interface rules
  NOTE  different from the recorded run, which is expected when the databases
        have changed since October; read the line, it is not an error
  FAIL  the module crashed or its result breaks the interface rules

Every live run fills the pipeline's own cache (backend/data/quaternary_cache),
so the app afterwards shows these proteins' quaternary results within seconds.
"""

import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # lets "import app" work

from app import cache  # noqa: E402
from app.examples import EXAMPLES  # noqa: E402
from app.jobs import JobStore, StageContext  # noqa: E402
from app.levels import primary, quaternary, secondary, tertiary  # noqa: E402
from app.schemas import AnalysisJob, LevelReport, LevelResult, QueryInfo  # noqa: E402
from app.verdict import build_verdict  # noqa: E402

HEMOGLOBIN = next(example for example in EXAMPLES if example.key == "hemoglobin-alpha")

# The example sequence is UniProt P69905 itself (100% identity over its full
# length), so it can be analysed directly when no primary result is cached.
P69905 = quaternary.Homologue(
    accession="P69905",
    entry="HBA_HUMAN",
    protein="Hemoglobin subunit alpha",
    organism="Homo sapiens",
    gene="HBA1",
    identity=100.0,
    coverage=100.0,
    passed=True,
)

# GroEL, the package's offline test protein (its bundled test data).
GROEL = quaternary.Homologue(
    accession="P0A6F5",
    entry="CH60_ECOLI",
    protein="Chaperonin GroEL",
    organism="Escherichia coli",
    gene="groL",
    identity=100.0,
    coverage=100.0,
    passed=True,
)

# The teammate's live run of P69905 (main branch, October 2026).
RECORDED = {
    "stoichiometry": "A4",
    "assembly type": "HOMOMER",
    "symmetry": "D2",
    "evidence status": "CONFIRMED",
    "Complex Portal": "CPX-2158",
    "PISA entry": "1A01",
    "PISA state": "STABLE",
    "PISA ΔG dissociation": "3.19",
    "PISA interfaces": 5,
    "AlphaFold DB mean pLDDT": "98.06",
    "UniProt GO terms": 20,
}


class PrintingContext(StageContext):
    """Prints the level's progress (each stage once, then every 10 s while it runs)."""

    def __init__(self) -> None:
        super().__init__(JobStore(), "check", "quaternary", threading.Event())
        self._last_stage = ""
        self._last_time = 0.0

    def report(self, message: str) -> None:
        self.check_cancelled()
        stage = message.split(" · ")[0]
        now = time.monotonic()
        if stage != self._last_stage or now - self._last_time >= 10.0:
            print(f"      {time.strftime('%H:%M:%S')}  {message}", flush=True)
            self._last_stage, self._last_time = stage, now


passes = 0
notes = 0
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


def compare(label: str, got: object) -> None:
    expected = RECORDED[label]
    if got == expected:
        result("PASS", f"{label}: {got}")
    else:
        result("NOTE", f"{label}: {got if got is not None else 'none'} (recorded run: {expected})")


def check_contract(level: LevelResult, name: str) -> None:
    """The rules the interface relies on (as in scripts/smoke_test.py)."""
    problems = []
    if level.source != "live" or not level.headline.value or not level.headline.label or not level.summary:
        problems.append("missing source, headline or summary")
    if len([metric for metric in level.metrics if metric.group is None]) > 4:
        problems.append("more than four key figures")
    for table in level.tables:
        keys = {column.key for column in table.columns}
        if not all(set(row) <= keys and all(isinstance(value, str) for value in row.values()) for row in table.rows):
            problems.append(f"table {table.key} uses undeclared or non-text cells")
    if len({link.url for link in level.links}) != len(level.links):
        problems.append("duplicate links")
    try:
        json.dumps(level.raw)
    except (TypeError, ValueError):
        problems.append("raw output is not JSON")
    if problems:
        result("FAIL", f"{name}: " + "; ".join(problems))
    else:
        result("PASS", f"{name}: valid interface result ({len(level.tables)} tables, {len(level.notes)} notes)")


def run_level(
    sequence: str,
    target: quaternary.Target,
    homologue: quaternary.Homologue | None,
    offline: bool = False,
) -> LevelResult:
    shown = target.value if target.mode == "homologue" else f"the sequence itself ({len(sequence)} residues)"
    print(f"      analysing {shown}")
    return quaternary.analyze_target(sequence, target, homologue, PrintingContext(), offline=offline)


def print_level(level: LevelResult) -> None:
    print(f"\n      {level.headline.value}  ({level.headline.label})")
    print(f"      {level.summary}")
    for metric in level.metrics:
        if metric.group is None:
            print(f"      {metric.label:<26}{metric.value}")
    print()


def check_hemoglobin() -> None:
    print("Human hemoglobin alpha (UniProt P69905) through the quaternary level.\n")
    primary_result = cache.load("primary", primary.CACHE_VERSION, HEMOGLOBIN.sequence)
    if primary_result is not None:
        print("      homologue taken from the cached primary result, as in the app")
        target, homologue = quaternary.choose_target(HEMOGLOBIN.sequence, primary_result)
    else:
        print("      no cached primary result, so P69905 is analysed directly (the example sequence is P69905)")
        target = quaternary.Target("P69905", "homologue", "UniProt P69905 was analysed directly.")
        homologue = P69905
    level = run_level(HEMOGLOBIN.sequence, target, homologue)
    print_level(level)

    raw = level.raw or {}
    if raw.get("analysed_target") != "P69905":
        result("FAIL", f"analysed {raw.get('analysed_target')!r} instead of P69905")
        return
    output = raw["pipeline_output"]
    assembly = output.get("target_self_assembly") or {}
    provenance = output.get("confidence_provenance") or {}
    compare("stoichiometry", assembly.get("formula"))
    compare("assembly type", assembly.get("assembly_type"))
    compare("symmetry", assembly.get("symmetry"))
    compare("evidence status", assembly.get("confidence_status"))
    complexes = [item.get("complex_portal_id") for item in output.get("functional_complexes") or []]
    compare("Complex Portal", complexes[0] if complexes else None)
    # The entry the interface names in its PISA heading ("… · PDBe PISA · 1A01").
    headings = [
        metric.group for metric in level.metrics if metric.group and metric.group.startswith("Interface thermodynamics")
    ]
    parts = headings[0].split(" · ") if headings else []
    compare("PISA entry", parts[2] if len(parts) == 3 else None)
    compare("PISA state", (output.get("metadata") or {}).get("pisa_thermodynamic_state"))
    delta_g = (provenance.get("pdbe_pisa") or {}).get("dissociation_energy_kcal_mol")
    compare("PISA ΔG dissociation", f"{delta_g:.2f}" if delta_g is not None else None)
    compare("PISA interfaces", len(output.get("interfaces") or []))
    plddt = (provenance.get("alphafold_db") or {}).get("global_plddt")
    compare("AlphaFold DB mean pLDDT", f"{plddt:.2f}" if plddt is not None else None)
    compare("UniProt GO terms", len((output.get("inferred_function") or {}).get("go_terms") or []))
    failed = [
        f"stage {stage['number']} {error['source']}: {error['error']}"
        for stage in raw["stages"]
        for error in stage["errors"]
    ]
    if failed:
        result("NOTE", "queries that failed this time (try again later): " + "; ".join(failed))
    check_contract(level, "hemoglobin alpha")


def check_offline() -> None:
    print("GroEL (UniProt P0A6F5) from the pipeline's bundled test data, without internet.\n")
    target = quaternary.Target("P0A6F5", "homologue", "GroEL from the package's bundled test data.")
    level = run_level("", target, GROEL, offline=True)
    print_level(level)
    assembly = ((level.raw or {}).get("pipeline_output") or {}).get("target_self_assembly") or {}
    if assembly.get("formula") == "A14":
        result("PASS", "GroEL is a 14-subunit homo-oligomer (A14), as in the notebook's offline run")
    else:
        result("FAIL", f"GroEL came out as {assembly.get('formula')!r} instead of A14")
    check_contract(level, "GroEL (offline)")


def check_examples() -> None:
    print("Every example with a cached primary result: quaternary level, then a verdict preview.\n")
    for example in EXAMPLES:
        print(f"--- {example.name}")
        primary_result = cache.load("primary", primary.CACHE_VERSION, example.sequence)
        if primary_result is None:
            result("NOTE", f"{example.name}: no cached primary result; run scripts/check_primary.py --examples "
                           "or analyse it once in the app first")
            continue
        target, homologue = quaternary.choose_target(example.sequence, primary_result)
        try:
            level = run_level(example.sequence, target, homologue)
        except Exception as error:  # report it and carry on with the next example
            result("FAIL", f"{example.name}: {error.__class__.__name__}: {error}")
            continue
        print_level(level)
        check_contract(level, example.name)

        now = datetime.now(timezone.utc)
        results: dict[str, LevelResult | None] = {
            "primary": primary_result,
            "secondary": cache.load("secondary", secondary.CACHE_VERSION, example.sequence),
            "tertiary": cache.load("tertiary", tertiary.CACHE_VERSION, example.sequence),
            "quaternary": level,
        }
        job = AnalysisJob(
            id="check",
            status="running",
            created_at=now,
            updated_at=now,
            query=QueryInfo(name=example.name, sequence=example.sequence, length=len(example.sequence)),
            levels=[
                LevelReport(key=key, title=key, status="completed" if value is not None else "skipped", result=value)
                for key, value in results.items()
            ],
        )
        verdict = build_verdict(job)
        score = f"{verdict.confidence_score:.2f}" if verdict.confidence_score is not None else "no score"
        print(f"      Verdict: {verdict.function}  ·  {verdict.confidence_tier} ({score})")
        print("      Levels: " + ", ".join(f"{item.key} {item.state}" for item in verdict.level_support))
        missing = [key for key, value in results.items() if value is None]
        if missing:
            print("      (not cached, so not used: " + ", ".join(missing) + ")")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the quaternary-structure level once.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="GroEL from the package's test data (no internet)")
    mode.add_argument("--examples", action="store_true", help="every example with a cached primary result")
    args = parser.parse_args()

    missing = quaternary.missing_setup()
    if missing:
        print("FAIL  Not set up yet. Missing: " + ", ".join(missing))
        print("      See the README: copy the package from the main branch, then run `uv sync`.")
        return 1

    started = time.monotonic()
    try:
        if args.offline:
            check_offline()
        elif args.examples:
            check_examples()
        else:
            check_hemoglobin()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 1
    except Exception as error:  # show the reason plainly
        print(f"\nFAIL  {error.__class__.__name__}: {error}")
        return 1

    print(f"\n{passes} passed, {notes} notes, {len(failures)} failed ({time.monotonic() - started:.0f} s)")
    if failures:
        for text in failures:
            print(f"  FAIL  {text}")
        return 1
    print("PASS  The quaternary level works (NOTE lines are explained above).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
