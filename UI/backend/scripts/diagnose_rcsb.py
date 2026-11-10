"""Why does the RCSB PDB sequence search answer "500 Internal Server Error"? (a one-off check)

From the backend folder:

    uv run python scripts/diagnose_rcsb.py

It sends the secondary notebook's RCSB query (compare_pdb_references) for human hemoglobin
alpha and for the sequences whose PDB lookup failed in the app, plus three small variants of
the query, and prints RCSB's status code, time and answer - including the text RCSB sends
with an error, which the app does not show. Nothing is changed or saved. Paste the output
back into the chat.
"""

import json
import sys
import time
from pathlib import Path

import requests

URL = "https://search.rcsb.org/rcsbsearch/v2/query"
CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "secondary" / "secondary-2"
HEMOGLOBIN = (
    "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDP"
    "VNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"
)


def notebook_query(sequence: str) -> dict:
    """compare_pdb_references' query, verbatim."""
    return {
        "query": {"type": "terminal", "service": "sequence", "parameters": {
            "target": "pdb_protein_sequence", "value": sequence,
            "identity_cutoff": .30, "evalue_cutoff": .1,
        }},
        "return_type": "polymer_entity",
        "request_options": {
            "results_content_type": ["experimental"],
            "paginate": {"start": 0, "rows": 3},
        },
    }


def variant(sequence: str, kind: str) -> dict:
    query = notebook_query(sequence)
    params = query["query"]["parameters"]
    if kind == "sequence_type":  # the parameter name RCSB's current documentation uses
        del params["target"]
        params["sequence_type"] = "protein"
    elif kind == "no content type":
        del query["request_options"]["results_content_type"]
    elif kind == "evalue 1e-5":  # the quaternary pipeline's cut-off
        params["evalue_cutoff"] = 1e-5
    return query


def failed_sequences() -> list[tuple[str, str]]:
    found = []
    for path in sorted(CACHE.glob("*.json")):
        try:
            raw = json.loads(path.read_text())["raw"]
        except (OSError, ValueError, KeyError):
            continue
        if (raw.get("pdb_references") or {}).get("status") == "unavailable":
            found.append((f"{raw['length']} aa (failed in the app)", raw["sequence"]))
    return found


def send(label: str, query: dict) -> None:
    started = time.monotonic()
    try:
        response = requests.post(URL, json=query, timeout=90)
    except requests.RequestException as error:
        print(f"  {label:<26} no answer after {time.monotonic() - started:5.1f} s: {error}")
        return
    seconds = time.monotonic() - started
    if response.status_code == 200:
        body = response.json()
        hits = [item["identifier"] for item in body.get("result_set", [])]
        print(f"  {label:<26} 200 in {seconds:5.1f} s: {body.get('total_count')} hits, first {hits}")
    elif response.status_code == 204:
        print(f"  {label:<26} 204 in {seconds:5.1f} s: no hits")
    else:
        text = " ".join(response.text.split())[:400]
        print(f"  {label:<26} {response.status_code} in {seconds:5.1f} s: {text}")


def main() -> int:
    sequences = [("hemoglobin alpha, 142 aa", HEMOGLOBIN)] + failed_sequences()
    for name, sequence in sequences:
        print(f"\n{name}: {sequence[:40]}…")
        send("notebook query", notebook_query(sequence))
        for kind in ("sequence_type", "no content type", "evalue 1e-5"):
            send(kind, variant(sequence, kind))
    print("\nDone. Paste everything above into the chat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
