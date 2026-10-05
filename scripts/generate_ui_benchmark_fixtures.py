"""
Generate and Export Canonical UI Benchmark Fixtures.

Benchmarks the 5 canonical example proteins from the UI branch:
1. Ubiquitin (Homo sapiens, PDB 1UBQ / UniProt P62988, Monomer)
2. Hemoglobin-α (Homo sapiens, UniProt P69905, Heterotetramer α2β2)
3. Bacteriorhodopsin (Halobacterium salinarum, UniProt P02945, Homotrimer A3)
4. p53 (Homo sapiens, UniProt P04637, Homotetramer A4)
5. AKT1 (Homo sapiens, UniProt P31749, Monomer A1)

Exports valid QuaternaryStructureOutput JSON payloads to schema/fixtures/ui_examples/*.
"""

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure utf-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from quaternary.config import QuaternaryConfig
from quaternary_pipeline import analyze_quaternary

BENCHMARK_TARGETS = [
    {
        "key": "ubiquitin",
        "filename": "ubiquitin.json",
        "target": "P62988",
        "name": "Ubiquitin",
        "organism": "Homo sapiens",
        "expected_state": "Monomer (A1)",
    },
    {
        "key": "hemoglobin_alpha",
        "filename": "hemoglobin_alpha.json",
        "target": "P69905",
        "name": "Hemoglobin α",
        "organism": "Homo sapiens",
        "expected_state": "Heterotetramer (α2β2)",
    },
    {
        "key": "bacteriorhodopsin",
        "filename": "bacteriorhodopsin.json",
        "target": "P02945",
        "name": "Bacteriorhodopsin",
        "organism": "Halobacterium salinarum",
        "expected_state": "Homotrimer (A3)",
    },
    {
        "key": "p53",
        "filename": "p53.json",
        "target": "P04637",
        "name": "p53",
        "organism": "Homo sapiens",
        "expected_state": "Homotetramer (A4)",
    },
    {
        "key": "akt1",
        "filename": "akt1.json",
        "target": "P31749",
        "name": "AKT1",
        "organism": "Homo sapiens",
        "expected_state": "Monomer (A1)",
    },
]


def generate_fixtures(output_dir: Path = Path("schema/fixtures/ui_examples")) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = QuaternaryConfig(offline_mode=False, cache_enabled=True, timeout=25.0)

    results = {}
    print(f"=== Generating 5 Canonical UI Benchmark Fixtures into {output_dir} ===")

    for item in BENCHMARK_TARGETS:
        target = item["target"]
        fname = item["filename"]
        out_path = output_dir / fname

        print(f"\n[BENCHMARK] Running '{item['name']}' ({target})...")
        t0 = time.time()
        output = analyze_quaternary(target, config=cfg, enable_multimer=False)
        elapsed = time.time() - t0

        payload_dict = output.model_dump(mode="json")
        out_path.write_text(json.dumps(payload_dict, indent=2), encoding="utf-8")

        formula = getattr(output.stoichiometry, "formula", None)
        subunits = output.stoichiometry.total_subunits
        interfaces = len(output.interfaces)
        print(f"  -> Finished in {elapsed:.2f}s | Status: {output.quaternary_status} | Formula: {formula} | Subunits: {subunits} | Interfaces: {interfaces}")
        print(f"  -> Saved fixture: {out_path} ({out_path.stat().st_size:,} bytes)")

        results[item["key"]] = {
            "name": item["name"],
            "target": target,
            "elapsed": elapsed,
            "status": output.quaternary_status,
            "formula": formula,
            "subunits": subunits,
            "interfaces": interfaces,
            "path": str(out_path),
        }

    print("\n[SUCCESS] All 5 UI benchmark fixtures generated successfully.")
    return results


if __name__ == "__main__":
    generate_fixtures()
