"""Run the real tertiary-structure module once, outside the web app.

From the backend folder, with SWISSMODEL_TOKEN set in backend/.env:

    uv run python scripts/check_tertiary.py

It uses the cytochrome c sequence from the team notebook and takes 5-15
minutes (Swiss-Model). The result is saved in the cache, so analysing the
same sequence in the app afterwards is instant. Press Ctrl+C to stop.
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # lets "import app" work

from app import cache  # noqa: E402
from app.config import SWISSMODEL_TOKEN  # noqa: E402
from app.jobs import JobStore, LevelSkipped, StageContext  # noqa: E402
from app.levels import tertiary  # noqa: E402

# The sequence the notebook was tested with (its top hits were cytochrome c).
SEQUENCE = (
    "MGDVEKGKKIFIMKCSQCHTVEKGGKHKTGPNLHGLFGRKTGQAPGYSYTAANKNKGIIWGEDTLMEYLENPKKYIPGTKMIFVGIKKKEERADLIAYLKKATNE"
)


class PrintingContext(StageContext):
    """Prints progress messages instead of sending them to the web page."""

    def report(self, message: str) -> None:
        self.check_cancelled()
        print(f"  {time.strftime('%H:%M:%S')}  {message}", flush=True)


def main() -> int:
    if not SWISSMODEL_TOKEN:
        print("FAIL  SWISSMODEL_TOKEN is not set. Add it to UI/backend/.env first.")
        return 1

    print(f"Running the tertiary module on a {len(SEQUENCE)}-residue test sequence.")
    print("Swiss-Model usually needs 5-15 minutes. Press Ctrl+C to stop.\n")
    ctx = PrintingContext(JobStore(), "check", "tertiary", threading.Event())
    started = time.monotonic()
    try:
        result = tertiary.analyze(SEQUENCE, ctx)
    except LevelSkipped as skip:
        print(f"\nFAIL  Skipped: {skip}")
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 1
    except Exception as error:  # show the reason plainly
        print(f"\nFAIL  {error}")
        return 1

    minutes = (time.monotonic() - started) / 60
    print(f"\nFinished in {minutes:.1f} minutes.\n")
    print(f"Headline   {result.headline.value} ({result.headline.label})")
    print(f"Summary    {result.summary}\n")
    for table in result.tables:
        for row in table.rows:
            print(f"Match      {row['database']}: {row['match']} {row['description']} (E-value {row['evalue']})")
    print()
    for metric in result.metrics:
        print(f"{metric.label:<24}{metric.value}")
    print()
    for note in result.notes:
        print(f"{note.title.upper()}: {note.text}")
    print()
    for track in result.tracks:
        print(f"Track      {track.label} ({track.style}, {len(track.segments)} segments)")

    cache.store("tertiary", tertiary.CACHE_VERSION, SEQUENCE, result)
    text = " ".join(row["description"] for table in result.tables for row in table.rows).lower()
    if "cytochrome" in text:
        print("\nMatches the notebook's result (cytochrome c).")
    print("\nPASS  The tertiary module works with the live services.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
