"""Analyse proteins once through the running app, so they open instantly later.

The app saves every finished level (backend/data/cache), so a protein that has
been analysed once opens within seconds the next time. Run this before a demo:

  On the server (recommended), from the deploy folder:
      sudo docker compose exec app python scripts/precompute.py http://127.0.0.1:8000

  Against any running copy of the app:
      python3 scripts/precompute.py http://127.0.0.1:8000             the built-in examples
      python3 scripts/precompute.py http://127.0.0.1:8000 my.fasta    the sequences in a FASTA file

Uses only Python's standard library. New sequences take 15-30 minutes each
(mostly waiting for JPred and Swiss-Model); the app runs up to three at once
and queues the rest, so the five examples need roughly 30-60 minutes in total.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

POLL_SECONDS = 15
TIMEOUT_SECONDS = 3 * 60 * 60
TERMINAL = {"completed", "failed", "cancelled"}
MARK = {
    "completed": "done",
    "failed": "failed",
    "skipped": "skipped",
    "cancelled": "stopped",
    "running": "running",
    "pending": "waiting",
}


def call(base: str, method: str, path: str, body: object = None) -> object:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    request = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def read_fasta(path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    name, parts = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(">"):
            if name is not None and parts:
                records.append((name, "".join(parts)))
            name, parts = line[1:].strip() or f"sequence {len(records) + 1}", []
        elif line:
            if name is None:
                name = f"sequence {len(records) + 1}"
            parts.append(line)
    if name is not None and parts:
        records.append((name, "".join(parts)))
    return records


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2
    base = sys.argv[1].rstrip("/")

    try:
        if len(sys.argv) == 3:
            proteins = read_fasta(Path(sys.argv[2]))
        else:
            proteins = [(item["name"], item["sequence"]) for item in call(base, "GET", "/api/examples")]  # type: ignore[union-attr]
    except (OSError, urllib.error.URLError, ValueError) as error:
        print(f"Could not read the proteins to analyse: {error}")
        return 1
    if not proteins:
        print("No sequences to analyse.")
        return 1

    jobs: dict[str, str] = {}
    for name, sequence in proteins:
        try:
            job = call(base, "POST", "/api/analyses", {"sequence": sequence, "name": name[:80]})
        except urllib.error.HTTPError as error:
            print(f"  skipped {name}: {error.read().decode('utf-8', 'replace')[:200]}")
            continue
        except urllib.error.URLError as error:
            print(f"Cannot reach {base}: {error.reason}")
            return 1
        jobs[job["id"]] = name  # type: ignore[index]
        print(f"  started {name}")

    started = time.monotonic()
    last: dict[str, str] = {}
    finished: dict[str, str] = {}
    while len(finished) < len(jobs) and time.monotonic() - started < TIMEOUT_SECONDS:
        time.sleep(POLL_SECONDS)
        for job_id, name in jobs.items():
            if job_id in finished:
                continue
            try:
                job = call(base, "GET", f"/api/analyses/{job_id}")
            except urllib.error.URLError as error:
                print(f"  (could not check {name}: {getattr(error, 'reason', error)}; retrying)")
                continue
            levels = ", ".join(f"{level['key']} {MARK.get(level['status'], level['status'])}" for level in job["levels"])  # type: ignore[index]
            line = f"{job['status']}: {levels}"  # type: ignore[index]
            if line != last.get(job_id):
                minutes = (time.monotonic() - started) / 60
                print(f"  [{minutes:5.1f} min] {name}: {line}")
                last[job_id] = line
            if job["status"] in TERMINAL:  # type: ignore[index]
                finished[job_id] = job["status"]  # type: ignore[index]

    done = sum(1 for status in finished.values() if status == "completed")
    print(f"\n{done} of {len(jobs)} analyses completed; their results are saved on the server.")
    if len(finished) < len(jobs):
        print("Some analyses were still running when this script stopped; they continue on the server.")
    return 0 if done == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
