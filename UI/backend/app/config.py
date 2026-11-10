"""Runtime settings for the backend.

Settings are read from environment variables. For convenience they can also
be written in backend/.env, one NAME=value per line (see .env.example).
A real environment variable always wins over the file, so this works too:

    PFP_MOCK_DELAY_SCALE=0 uv run uvicorn app.main:app --reload
"""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"


def _load_env_file(path: Path) -> None:
    """Read NAME=value lines from backend/.env without overriding real variables."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if name and name not in os.environ:
            os.environ[name] = value


_load_env_file(ENV_FILE)

API_VERSION = "0.4.0"

LEVEL_NAMES = ("primary", "secondary", "tertiary", "quaternary")

# --- Sequence limits -------------------------------------------------------
# The secondary-structure notebook supports 25-1,000 residues per query, and
# ESM-2 (primary structure) handles at most ~1,022 residues per sequence.
MIN_SEQUENCE_LENGTH = 25
MAX_SEQUENCE_LENGTH = 1000

# --- Job handling ------------------------------------------------------------
# Results live in memory and disappear when the server restarts.
MAX_STORED_JOBS = 100
# Analyses that may run at the same time; others queue. Most of an analysis is
# spent waiting for web services (EBI, AlphaFold DB, Foldseek), so several can overlap;
# the CPU-heavy primary and secondary levels still run for one analysis at a time.
MAX_CONCURRENT_JOBS = 3


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a number, but it is set to {raw!r}.") from None
    if value < 0:
        raise RuntimeError(f"{name} must not be negative, but it is set to {raw!r}.")
    return value


def _read_levels(name: str) -> frozenset[str]:
    raw = os.getenv(name, "")
    levels = {part.strip().lower() for part in raw.split(",") if part.strip()}
    unknown = levels - set(LEVEL_NAMES)
    if unknown:
        raise RuntimeError(
            f"{name} contains unknown level name(s): {', '.join(sorted(unknown))}. "
            f"Use any of: {', '.join(LEVEL_NAMES)}."
        )
    return frozenset(levels)


# --- Real modules or placeholders ---------------------------------------------
# Levels listed here use placeholder data even when a real module exists,
# e.g. PFP_PLACEHOLDER_LEVELS=tertiary for fast interface work.
PLACEHOLDER_LEVELS = _read_levels("PFP_PLACEHOLDER_LEVELS")

# --- Result cache -------------------------------------------------------------
# Real results are saved in backend/data/cache so repeat analyses are instant.
# Set PFP_CACHE=off to ignore the cache; delete the folder to clear it.
CACHE_ENABLED = os.getenv("PFP_CACHE", "on").strip().lower() not in {"off", "0", "false", "no"}
CACHE_DIR = BACKEND_DIR / "data" / "cache"

# --- External services --------------------------------------------------------
# The tertiary level uses AlphaFold DB and Foldseek, which need no account.
# Longest we wait for a Foldseek search.
FOLDSEEK_TIMEOUT_SECONDS = _read_float("PFP_FOLDSEEK_TIMEOUT", 900.0)
# Longest a single web request may take before it counts as a failure.
HTTP_TIMEOUT_SECONDS = 60.0

# --- Quick results ------------------------------------------------------------
# The results page opens as soon as any level has finished. A provisional
# prediction is shown once the primary level is done (after waiting up to this
# many seconds for the quaternary level; 0 = show it straight away). It updates
# each time another level finishes.
QUICK_RESULT_SECONDS = _read_float("PFP_QUICK_RESULT_SECONDS", 0.0)

# --- Placeholder (mock) mode -------------------------------------------------
# Multiplies every simulated delay. 1 = realistic pacing (~15 s per analysis),
# 0 = instant results. Real analysis modules ignore this setting.
MOCK_DELAY_SCALE = _read_float("PFP_MOCK_DELAY_SCALE", 1.0)

# Set to primary / secondary / tertiary / quaternary to make that level's
# placeholder fail on purpose, which is useful for testing error states.
MOCK_FAIL_LEVEL = os.getenv("PFP_MOCK_FAIL_LEVEL", "").strip().lower() or None

# --- Primary-structure module (DIAMOND, HMMER, ESM-2) -------------------------
# Databases created by scripts/setup_primary.sh (about 4 GB; ignored by git).
PRIMARY_DATA_DIR = Path(os.getenv("PFP_PRIMARY_DATA_DIR", "").strip() or BACKEND_DIR / "data" / "primary")
# Program names (or full paths) for the two command-line tools.
DIAMOND_BIN = os.getenv("PFP_DIAMOND_BIN", "").strip() or "diamond"
HMMSCAN_BIN = os.getenv("PFP_HMMSCAN_BIN", "").strip() or "hmmscan"
# Longest a single DIAMOND or hmmscan run may take.
PRIMARY_TOOL_TIMEOUT_SECONDS = _read_float("PFP_PRIMARY_TOOL_TIMEOUT", 1800.0)
# The primary level's remote EMBL-EBI services (BLASTp and InterProScan) refine its
# result in the background. EBI's job service requires a contact e-mail with every
# job; without one these two modules are skipped and only the local tools are used.
EBI_EMAIL = os.getenv("PFP_EBI_EMAIL", "").strip()
# Longest each remote job may take (the notebook allows 1 h and 2 h; shorter here so
# a stuck EBI job cannot hold an analysis slot for hours).
EBI_BLAST_TIMEOUT_SECONDS = _read_float("PFP_EBI_BLAST_TIMEOUT", 1800.0)
EBI_INTERPRO_TIMEOUT_SECONDS = _read_float("PFP_EBI_INTERPRO_TIMEOUT", 3600.0)

# --- Secondary-structure module (S4PRED, ESM-2 SS3, PSIPRED, GOR IV, Chou-Fasman) ---
# The notebook's ASSETS folder, created by scripts/setup_secondary.py (about 250 MB;
# ignored by git): S4PRED's code and weights, PSIPRED built from source, the ESM-2
# secondary-structure checkpoint.
SECONDARY_DATA_DIR = Path(os.getenv("PFP_SECONDARY_DATA_DIR", "").strip() or BACKEND_DIR / "data" / "secondary")

# --- Quaternary-structure module (the team's quaternary_pipeline package) -----
# Longest the pipeline's six stages (about a dozen database queries) may take.
QUATERNARY_TIMEOUT_SECONDS = _read_float("PFP_QUATERNARY_TIMEOUT", 600.0)
# The pipeline's own cache of database answers. Delete the folder to clear it;
# PFP_CACHE=off turns it off together with the result cache above.
QUATERNARY_CACHE_DIR = BACKEND_DIR / "data" / "quaternary_cache"

# --- Hosting ------------------------------------------------------------------
# Load the primary level's ESM-2 and the secondary level's predictors when the server starts instead of during
# the first analysis (on by default in the hosted Docker image; see app/warmup.py).
PRELOAD_MODELS = os.getenv("PFP_PRELOAD_MODELS", "off").strip().lower() in {"on", "1", "true", "yes"}
