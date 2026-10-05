"""
Export UI Data Contract Utility & CLI.

Generates the published Draft 2020-12 JSON Schema for QuaternaryStructureOutput
and exports canonical UI data contract payloads for frontend synchronization.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from quaternary.config import QuaternaryConfig
from quaternary.models import QuaternaryStructureOutput
from quaternary_pipeline import analyze_quaternary


DEFAULT_SCHEMA_PATH = Path("schema/quaternary_structure_output.schema.json")
DEFAULT_CANONICAL_PATH = Path("quaternary_structure_output.json")
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def export_json_schema(target_path: Path = DEFAULT_SCHEMA_PATH) -> Dict[str, Any]:
    """Generate Draft 2020-12 JSON Schema directly from Pydantic domain models.

    Args:
        target_path: Path where the schema JSON will be saved.

    Returns:
        The generated JSON Schema dictionary.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Ingest Pydantic v2 schema dictionary
    raw_schema = QuaternaryStructureOutput.model_json_schema()

    # Reorder top-level keys placing $schema, title, and description first
    schema: Dict[str, Any] = {
        "$schema": SCHEMA_DRAFT,
        "title": "QuaternaryStructureOutput",
        "description": "Canonical data contract for protein quaternary structure synthesis and UI export.",
    }
    for key, value in raw_schema.items():
        if key not in schema:
            schema[key] = value

    # Write formatted JSON
    target_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"[EXPORT] JSON Schema saved to: {target_path} ({target_path.stat().st_size:,} bytes)")
    return schema


def export_canonical_payload(
    target_path: Path = DEFAULT_CANONICAL_PATH,
    target_identifier: str = "P0A6F5",
) -> Dict[str, Any]:
    """Execute quaternary characterization on canonical benchmark target and export payload.

    Args:
        target_path: Filepath where the canonical output JSON will be saved.
        target_identifier: Accession or sequence to analyze (defaults to GroEL P0A6F5).

    Returns:
        The serialized JSON payload dictionary.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[EXPORT] Generating canonical payload for benchmark target '{target_identifier}'...")
    cfg = QuaternaryConfig(offline_mode=True, cache_enabled=True)
    output = analyze_quaternary(target_identifier, config=cfg, enable_multimer=False)

    payload_json = output.model_dump_json(indent=2)
    target_path.write_text(payload_json, encoding="utf-8")
    print(f"[EXPORT] Canonical UI contract payload saved to: {target_path} ({target_path.stat().st_size:,} bytes)")
    return json.loads(payload_json)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quaternary UI Data Contract & JSON Schema Exporter CLI"
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Export only schema/quaternary_structure_output.schema.json",
    )
    parser.add_argument(
        "--canonical",
        action="store_true",
        help="Export only canonical root quaternary_structure_output.json",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Export both JSON Schema and canonical payload (default behavior)",
    )
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help=f"Target path for schema (default: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--canonical-path",
        type=Path,
        default=DEFAULT_CANONICAL_PATH,
        help=f"Target path for canonical payload (default: {DEFAULT_CANONICAL_PATH})",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="P0A6F5",
        help="Target accession/sequence for canonical payload (default: P0A6F5)",
    )

    args = parser.parse_args()

    # Determine execution scope
    export_schema_flag = args.schema_only or args.all or (not args.canonical and not args.schema_only)
    export_canonical_flag = args.canonical or args.all or (not args.canonical and not args.schema_only)

    if export_schema_flag:
        export_json_schema(args.schema_path)

    if export_canonical_flag:
        export_canonical_payload(args.canonical_path, target_identifier=args.target)

    print("[SUCCESS] Contract export completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
