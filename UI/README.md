# Protein Function Predictor

Paste an unseen protein sequence, get a predicted function — backed by evidence
from primary, secondary, tertiary and quaternary structure analysis.

- **Frontend:** React 19 + TypeScript + Vite 6 (`frontend/`)
- **Backend:** FastAPI on Python 3.12, managed with `uv` (`backend/`)

---

## Prerequisites (macOS)

| Tool | Check with | Needed version |
| --- | --- | --- |
| Xcode Command Line Tools | `xcode-select -p` | any |
| Node.js | `node -v` | 20.19 or newer (22 or 24 LTS recommended) |
| uv | `uv --version` | any recent |

You do **not** need to install Python yourself — `uv` downloads Python 3.12
automatically and keeps it separate from any other Python on your Mac.

## Running the app (two terminals)

**Terminal 1 — backend**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend**

```bash
cd frontend
npm install
npm run dev
```

Then open <http://localhost:5173>.

## Project structure

```
UI/
├── README.md
├── .gitignore
├── .vscode/settings.json        VS Code picks the backend venv automatically
├── docs/
│   └── LEVEL_CONTRACT.md        how to connect an analysis module (share with the team)
├── backend/
│   ├── .python-version          pins Python 3.12 for uv
│   ├── pyproject.toml           backend dependencies
│   ├── .env.example             template for .env (secrets; .env itself is never committed)
│   ├── quaternary_pipeline.py   the team's quaternary package (from main; one fix in clients/rcsb.py)
│   ├── quaternary/              ″
│   ├── seed_cache/              saved example results, copied into the hosted app
│   ├── scripts/
│   │   ├── smoke_test.py        end-to-end check of the running backend
│   │   ├── setup_primary.sh     one-time download of Swiss-Prot and Pfam
│   │   ├── setup_secondary.py   one-time download of S4PRED, PSIPRED and the ESM-2 SS3 model
│   │   ├── check_primary.py     runs each real module once…
│   │   ├── check_secondary.py   ″
│   │   ├── check_tertiary.py    ″ (about a minute)
│   │   ├── check_quaternary.py  ″ (about a minute; --offline needs no internet)
│   │   └── update_seed_cache.sh copies saved results into seed_cache
│   └── app/
│       ├── main.py              FastAPI app: startup, shutdown, routes
│       ├── api.py               the HTTP endpoints
│       ├── schemas.py           the data contract shared with the frontend
│       ├── config.py            limits and settings
│       ├── sequence.py          sequence cleaning and validation
│       ├── examples.py          example proteins for the input screen
│       ├── jobs.py              in-memory job store, progress and cancellation
│       ├── runner.py            runs the levels in the background
│       ├── cache.py             saves results of slow real modules (backend/data/cache)
│       ├── verdict.py           combines the four levels into the predicted function
│       ├── warmup.py            optional model loading at start-up (hosting)
│       └── levels/
│           ├── __init__.py      level registry — where real modules plug in
│           ├── placeholders.py  stand-in results (used when a module is switched off)
│           ├── primary.py       REAL: DIAMOND, HMMER/Pfam, ESM-2, ProtParam, UniProt (+ optional EBI BLASTp, InterProScan)
│           ├── secondary.py     REAL: S4PRED, ESM-2 SS3, PSIPRED, GOR IV, Chou–Fasman, PDB comparison
│           ├── tertiary.py      REAL: AlphaFold DB, Foldseek, pLDDT, DSSP, ProtParam, annotation transfer
│           └── quaternary.py    REAL: the team's quaternary pipeline (six stages)
├── deploy/                      hosting: Dockerfile, docker-compose, Caddy, DEPLOY.md
└── frontend/
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts           dev server + /api proxy to FastAPI
    ├── public/favicon.svg
    └── src/
        ├── main.tsx             React entry point
        ├── App.tsx              picks the screen; keeps ?job=… in the address bar
        ├── api/
        │   ├── types.ts         TypeScript copy of backend/app/schemas.py
        │   └── client.ts        every call to the backend
        ├── hooks/
        │   ├── useAnalysis.ts   submit → poll → finished; cancel; retries
        │   ├── useBackendStatus.ts  the "Server online" indicator
        │   ├── useExamples.ts   example proteins
        │   └── useNow.ts        ticking clock for live timers
        ├── lib/
        │   ├── sequence.ts      instant validation (mirrors the backend)
        │   ├── format.ts        numbers, times, durations
        │   ├── download.ts      JSON export
        │   └── anchors.ts       ids of the per-level analysis sections
        ├── components/
        │   ├── Header           brand + server status
        │   ├── InputScreen      sequence entry, examples, level guide
        │   ├── RunScreen        live progress, cancel, failed/cancelled states
        │   ├── StepIcon         status icons for the progress list
        │   ├── ResultsScreen    verdict, residue map, overview cards, analyses, print
        │   ├── ResidueMap       aligned tracks with crosshair, readout, keyboard control
        │   ├── LevelAnalysis    the detailed section for one structural level
        │   ├── SequenceView     residue letters coloured by a chosen track
        │   ├── LevelStatusTag   live / placeholder / failed tag
        │   └── MessageScreen    loading / not-found pages
        └── styles/
            ├── tokens.css       colours, fonts, radii — the design system
            ├── global.css       base styles
            ├── tones.css        colours for residue tracks (one class per tone)
            └── ui.css           buttons, tags, alerts, layout
```

## API

Interactive documentation: <http://127.0.0.1:8000/docs> (while the backend runs).

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Is the server up? |
| GET | `/api/examples` | Example proteins for the input screen |
| POST | `/api/analyses` | Start an analysis; returns immediately with a job |
| GET | `/api/analyses/{id}` | Poll progress and results |
| POST | `/api/analyses/{id}/cancel` | Stop a running analysis |

Each analysis reports four levels (primary, secondary, tertiary, quaternary)
in one shared shape, so modules can change without touching the frontend.
See [docs/LEVEL_CONTRACT.md](docs/LEVEL_CONTRACT.md).

## Placeholder mode

Levels switched to placeholders (`PFP_PLACEHOLDER_LEVELS=primary,tertiary`, or
all four for interface work) return clearly marked stand-in results. Two optional
settings help while building the interface:

```bash
# Instant results instead of the realistic ~15-second run
PFP_MOCK_DELAY_SCALE=0 uv run uvicorn app.main:app --reload --port 8000

# Make one level fail on purpose, to see the error state
PFP_MOCK_FAIL_LEVEL=secondary uv run uvicorn app.main:app --reload --port 8000
```

## Real analysis modules

All four levels are connected, each ported from the team notebook with its
logic unchanged: **primary** (`levels/primary.py`, the final notebook
`Final_Primary_structure.ipynb`, pipeline 3.1-fast-local: the validated sequence and its
query ID, ProtParam, DIAMOND `--fast` against Swiss-Prot, HMMER against Pfam-A, the 320-d
ESM-2 embedding with its nearest neighbours in the notebook's 4-protein demo reference,
UniProt metadata for the 3 best candidates, and the evidence tier A–D with its
rationale; the optional remote EMBL-EBI BLASTp and InterProScan, off in the notebook's
fast profile, run in the background only when `PFP_EBI_EMAIL` is set),
**secondary** (`levels/secondary.py`, the final notebook `SecondaryStructureFinal.ipynb`:
five local single-sequence predictors - S4PRED, ESM-2 SS3, PSIPRED-single, GOR IV and
Chou–Fasman - and their majority consensus, profile, regions and pairwise agreement; the
consensus is then compared with up to three experimentally solved PDB structures in the
background), **tertiary** (`levels/tertiary.py`, the notebook
`Tertiary_protein_identification.ipynb`: the AlphaFold DB structure of the primary
level's closest Swiss-Prot match, searched with Foldseek, with its confidence, secondary
structure, shape, surface and the annotation of its AlphaFold DB match; skipped with a
message when there is no match or no AlphaFold DB model) and **quaternary**
(`levels/quaternary.py`, which runs the team's `quaternary_pipeline` package on the
closest Swiss-Prot homologue found by the primary level).

**The final prediction** (`backend/app/verdict.py`) follows the notebook
`Function_Prediction_Integration_Final.ipynb`: the function is transferred from the
best-supported template (Swiss-Prot homologue → Pfam/InterPro domain → a characterised
structural match of the template's AlphaFold DB structure), its confidence is
P(homology) × P(function conserved), and the secondary and quaternary results act as
consistency checks on the log-odds scale. The tertiary level analyses the template's
own structure, so it is not counted as a check; it provides the structural route.

**Quick results** (`backend/app/runner.py`): the four levels run at the same time
(tertiary and quaternary start when primary has found its closest match). The results page opens
as soon as the first level has finished, on that level's tab; levels that are
still running show their progress in their own tab. A *provisional* prediction
appears on the Summary tab once the primary level is done and updates as the
slower levels finish. Meanwhile it
shows the confidence range those levels could still produce: the predicted
function itself can no longer change, only their consistency checks are
outstanding. When `PFP_EBI_EMAIL` is set, the primary level's optional EBI BLASTp and
InterProScan (a few minutes) run after its local result is shown and then replace it;
likewise the secondary level's comparison with PDB structures (a few seconds). The
prediction is recomputed when they finish. **Stop & finish now** finalises the report with the levels that are
done. Up to three analyses run at once; the CPU-heavy primary and secondary levels run for one
analysis at a time.

**Results page:** a Summary tab (prediction, confidence, key facts, residue map,
how it was reached) and one tab per level with the essentials; everything else is
under "More details". The Print menu prints the full report or a single level.

**Non-standard letters** (`backend/app/sequence.py`): a few of them are replaced
with the standard amino acid they most likely stand for: X (unknown) → L, the most
common amino acid; B → D; Z → E; J → L; U (selenocysteine) → C; O (pyrrolysine) → K.
At most 5% of the residues (at least one) and no more than 3 in a row may be
replaced; otherwise the sequence is rejected with an explanation. Alignment gaps
("-", ".") are removed. The input screen and the results page say what was changed.

**Primary structure needs a one-time setup** (about 5 GB of disk):

```bash
brew install diamond hmmer
cd backend && uv sync && bash scripts/setup_primary.sh
uv run python scripts/check_primary.py   # compares with the notebook's recorded results
uv run python scripts/check_primary.py --benchmark   # also its fast-vs-sensitive benchmark (~15 min)
```

**Secondary structure needs a one-time setup too** (about 250 MB; needs git, make and a C
compiler, which a Mac gets with `xcode-select --install`):

```bash
cd backend && uv sync && uv run python scripts/setup_secondary.py
uv run python scripts/check_secondary.py   # compares with the notebook's recorded results
```

**Settings live in `backend/.env`** (never committed; see `.env.example`), for
example the contact e-mail EMBL-EBI requires for the optional BLASTp and InterProScan
modules (leave it empty for the notebook's default fast local profile):

```
PFP_EBI_EMAIL=you@example.org
```

The tertiary level needs no account: AlphaFold DB and Foldseek are open. Its
secondary-structure part uses the `pydssp` package, which `uv sync` installs.

- **Check a module on its own** (needs internet):
  `uv run python scripts/check_tertiary.py` (about a minute; compares with the
  notebook's recorded result) or
  `uv run python scripts/check_quaternary.py` (about a minute; add `--offline`
  to test without internet)
- **Cache:** real results are saved in `backend/data/cache`, so the same
  sequence is instant the second time. Delete that folder to clear it, or set
  `PFP_CACHE=off`.
- **Pre-compute** (e.g. before a demo): `python3 scripts/precompute.py <app address>`
  analyses the built-in examples (or a FASTA file) through the running app, so they
  open instantly afterwards.
- **Fast interface work:** `PFP_PLACEHOLDER_LEVELS=primary,tertiary` uses
  placeholder data even though the real modules exist.

## Testing the backend

With the backend running, in a second terminal:

```bash
cd backend
uv run python scripts/smoke_test.py
```

It should end with `ALL CHECKS PASSED`. While a real module is connected, the
two slow sections (full analysis, cancelling) are skipped with a note; start the
backend with `PFP_PLACEHOLDER_LEVELS=tertiary` to run them too.

## Roadmap

1. Project skeleton and environment check ✅
2. Data contract and mock API (placeholder results for all four levels) ✅
3. Input screen: sequence entry, validation, examples, job progress ✅
4. Results screen: verdict, residue map, level cards, detailed analyses, print ✅
5. Integrate primary-structure analysis (DIAMOND, HMMER, ESM-2 + retrieval, ProtParam, UniProt; optional EBI BLASTp, InterProScan) ✅
6. Integrate secondary-structure analysis (S4PRED, ESM-2 SS3, PSIPRED, GOR IV, Chou–Fasman, RCSB/PDBe) ✅
7. Integrate tertiary-structure analysis (AlphaFold DB, Foldseek, pLDDT, DSSP, annotation transfer) ✅
8. Integrate quaternary-structure analysis, then evidence aggregation ✅
9. Hosting (Docker on a cloud server; see `deploy/DEPLOY.md`) ✅
10. Quick results (parallel levels, provisional prediction) and a tabbed results page ✅

## Hosting

The whole app runs as one Docker container behind HTTPS (Caddy) on a cloud
server, e.g. a Google Cloud free-trial VM. Step-by-step guide:
**[deploy/DEPLOY.md](deploy/DEPLOY.md)**.
After changing Python dependencies, refresh the file the Docker build installs:

```bash
cd backend
uv export --frozen --no-hashes --no-emit-project --no-group primary --format requirements-txt -o requirements.txt
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `uv: command not found` | Close and reopen the terminal after installing uv, or run `source $HOME/.local/bin/env`. |
| `node: command not found` | Install the LTS version from <https://nodejs.org>, then reopen the terminal. |
| `ModuleNotFoundError: No module named 'app'` | You started uvicorn from the wrong folder. `cd backend` first. |
| `Address already in use` (port 8000) | Another server is running. Find it with `lsof -i :8000`, stop it, or close the old terminal. |
| `Port 5173 is already in use` | An old `npm run dev` is still running. Stop it with Ctrl+C in its terminal. |
| Backend check says "HTTP 500" or "HTTP 502" | The frontend is fine but FastAPI is not running. Start Terminal 1. |
| Page shows "Server offline" | Start the backend (Terminal 1). The page reconnects by itself within 15 seconds, or immediately when you click back into the window. |
| "Analysis not found" after editing backend code | Expected: `--reload` restarts the server and results live in memory. Start a new analysis. |
| VS Code underlines `fastapi` imports | Cmd+Shift+P → "Python: Select Interpreter" → choose `backend/.venv/bin/python`. |
