"""End-to-end check of the running backend, using only the standard library.

Start the server first (in another terminal), then from the backend folder:

    uv run python scripts/smoke_test.py

Every check prints PASS or FAIL. The script exits with status 0 only if
all checks pass.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

TERMINAL = {"completed", "failed", "cancelled"}
LEVEL_KEYS = ["primary", "secondary", "tertiary", "quaternary"]
TRACK_STYLES = {"blocks", "states", "marks"}

failures: list[str] = []


def check(condition: bool, description: str) -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {description}")
    if not condition:
        failures.append(description)
    return condition


def call(base: str, method: str, path: str, body: Any = None) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            text = response.read().decode("utf-8")
            return response.status, json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        text = error.read().decode("utf-8")
        try:
            return error.code, json.loads(text)
        except json.JSONDecodeError:
            return error.code, text


def wait_for(base: str, job_id: str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_line = ""
    while True:
        status, job = call(base, "GET", f"/api/analyses/{job_id}")
        if status != 200:
            raise RuntimeError(f"Polling returned HTTP {status}: {job}")
        running = next((lvl for lvl in job["levels"] if lvl["status"] == "running"), None)
        line = f"    … {job['status']}"
        if running is not None:
            line += f" · {running['key']}: {running.get('message') or ''}"
        if line != last_line:
            print(line)
            last_line = line
        if job["status"] in TERMINAL:
            return job
        if time.monotonic() > deadline:
            raise RuntimeError(f"Job {job_id} did not finish within {timeout:.0f} seconds.")
        time.sleep(0.5)


def check_tracks(level: dict[str, Any], length: int) -> None:
    for track in level["result"]["tracks"]:
        segments = track["segments"]
        ok = track["style"] in TRACK_STYLES and all(
            1 <= seg["start"] <= seg["end"] <= length for seg in segments
        )
        check(ok, f"{level['key']} track '{track['key']}' stays within residues 1–{length}")
        if track["style"] == "states" and segments:
            contiguous = segments[0]["start"] == 1 and segments[-1]["end"] == length and all(
                nxt["start"] == cur["end"] + 1 for cur, nxt in zip(segments, segments[1:])
            )
            check(contiguous, f"{level['key']} track '{track['key']}' covers every residue once")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="backend address")
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds to wait per job")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    print(f"Testing the backend at {base}\n")

    print("1. Health")
    try:
        status, payload = call(base, "GET", "/api/health")
    except urllib.error.URLError as error:
        print(f"  FAIL  Could not connect ({error.reason}).")
        print("        Start the server first: uv run uvicorn app.main:app --reload --port 8000")
        return 1
    check(status == 200 and payload.get("status") == "ok", "GET /api/health returns status ok")
    live_levels = payload.get("live_levels", []) if isinstance(payload, dict) else []
    if live_levels:
        print(f"  NOTE  Real modules are connected for: {', '.join(live_levels)}.")
        print("        A full analysis now calls real web services and can take 15 minutes,")
        print("        so sections 4 and 5 are skipped. To run them, restart the backend with")
        print(f"        PFP_PLACEHOLDER_LEVELS={','.join(live_levels)} uv run uvicorn app.main:app --reload --port 8000")

    print("\n2. Examples")
    status, examples = call(base, "GET", "/api/examples")
    check(status == 200 and isinstance(examples, list) and len(examples) >= 1, "examples are listed")
    if status != 200 or not examples:
        return 1
    check(
        all(len(example["sequence"]) == example["length"] for example in examples),
        "every example's length matches its sequence",
    )
    shortest = min(examples, key=lambda example: example["length"])

    print("\n3. Input validation")
    bad_inputs = {
        "an empty sequence": "   ",
        "a DNA sequence": "ATGGCTAGCTAGGATCCATGGCTAGC",
        "a sequence that is too short": "MKTAYIAKQR",
        "unsupported characters": "MKTAYIAKQRQISFVKSHFSRQXBLEERLGLIEVQ",
        "two FASTA records": ">a\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ\n>b\nMKTAYIAKQRQISFVKSHFSRQ",
    }
    for description, text in bad_inputs.items():
        status, payload = call(base, "POST", "/api/analyses", {"sequence": text})
        detail = payload.get("detail") if isinstance(payload, dict) else None
        check(
            status == 422 and isinstance(detail, str) and len(detail) > 0,
            f"rejects {description} with a readable message",
        )
    status, payload = call(base, "POST", "/api/analyses", {})
    check(status == 422, "rejects a request with no sequence field")
    status, payload = call(base, "GET", "/api/analyses/does-not-exist")
    check(status == 404 and isinstance(payload, dict) and "detail" in payload, "an unknown job id returns 404")

    if live_levels:
        return finish()

    print(f"\n4. Full analysis ({shortest['name']}, {shortest['length']} residues)")
    fasta = f">{shortest['name']} example\n{shortest['sequence']}"
    status, job = call(base, "POST", "/api/analyses", {"sequence": fasta})
    if not check(status == 202 and isinstance(job, dict) and "id" in job, "POST /api/analyses returns 202 with a job id"):
        return 1
    check(job["query"]["name"] == f"{shortest['name']} example", "the FASTA header becomes the query name")
    check([level["key"] for level in job["levels"]] == LEVEL_KEYS, "the job lists all four levels in order")

    job = wait_for(base, job["id"], args.timeout)
    check(job["status"] == "completed", "the analysis completes")
    for level in job["levels"]:
        if not check(level["status"] == "completed" and level["result"] is not None, f"{level['key']} level completed with a result"):
            continue
        result = level["result"]
        check(
            result["source"] in {"live", "placeholder"}
            and bool(result["headline"]["value"])
            and bool(result["headline"]["label"])
            and bool(result["summary"]),
            f"{level['key']} result has a source, headline and summary",
        )
        check_tracks(level, job["query"]["length"])
        for table in result.get("tables", []):
            column_keys = {column["key"] for column in table["columns"]}
            check(
                all(set(row) <= column_keys for row in table["rows"]),
                f"{level['key']} table '{table['key']}' only uses its declared columns",
            )
        check(
            all(note["kind"] in {"recommendation", "observation", "caution"} for note in result.get("notes", [])),
            f"{level['key']} notes have valid kinds",
        )
    verdict = job.get("verdict")
    check(job["verdict_status"] == "completed" and isinstance(verdict, dict), "a verdict is produced")
    if isinstance(verdict, dict):
        check(
            [item["key"] for item in verdict["level_support"]] == LEVEL_KEYS,
            "the verdict reports support from all four levels",
        )

    print("\n5. Cancelling")
    status, job = call(base, "POST", "/api/analyses", {"sequence": shortest["sequence"]})
    if not check(status == 202 and isinstance(job, dict) and "id" in job, "a second analysis starts"):
        return 1
    status, _ = call(base, "POST", f"/api/analyses/{job['id']}/cancel")
    check(status == 200, "POST /cancel is accepted")
    job = wait_for(base, job["id"], args.timeout)
    if job["status"] == "completed":
        print("  NOTE  The job finished before the cancel arrived (expected with PFP_MOCK_DELAY_SCALE=0).")
    else:
        check(job["status"] == "cancelled", "the analysis ends as cancelled")

    return finish()


def finish() -> int:
    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED:")
        for description in failures:
            print(f"  - {description}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
