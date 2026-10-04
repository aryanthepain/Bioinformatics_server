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
│   ├── scripts/
│   │   ├── smoke_test.py        end-to-end check of the running backend
│   │   └── check_tertiary.py    runs the real tertiary module once (5–15 min)
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
│       ├── verdict.py           combines level results into the final answer
│       └── levels/
│           ├── __init__.py      level registry — where real modules plug in
│           ├── placeholders.py  stand-in results until modules are connected
│           └── tertiary.py      REAL: Swiss-Model, Foldseek, ProtParam, wet-lab advice
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

Until the analysis modules are connected, every level returns clearly marked
placeholder results. Two optional settings help while building the interface:

```bash
# Instant results instead of the realistic ~15-second run
PFP_MOCK_DELAY_SCALE=0 uv run uvicorn app.main:app --reload --port 8000

# Make one level fail on purpose, to see the error state
PFP_MOCK_FAIL_LEVEL=secondary uv run uvicorn app.main:app --reload --port 8000
```

## Real analysis modules

Connected so far: **tertiary structure** (`backend/app/levels/tertiary.py`, ported
from the team notebook with its logic unchanged). The other levels still use
placeholders.

**Secrets live in `backend/.env`** (never committed; see `.env.example`):

```
SWISSMODEL_TOKEN=your-swiss-model-token
```

Without a token, the tertiary level is skipped with an explanation.

- **Check the module on its own** (5–15 minutes, needs internet):
  `uv run python scripts/check_tertiary.py`
- **Cache:** real results are saved in `backend/data/cache`, so the same
  sequence is instant the second time. Delete that folder to clear it, or set
  `PFP_CACHE=off`.
- **Fast interface work:** `PFP_PLACEHOLDER_LEVELS=tertiary` uses placeholder
  data even though the real module exists.

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
5. Integrate primary-structure analysis (DIAMOND, HMMER, ESM-2, ProtParam)
6. Integrate secondary-structure analysis (JPred, ProtBert, RCSB/PDBe)
7. Integrate tertiary-structure analysis (Swiss-Model, Foldseek, ProtParam) ✅
8. Integrate quaternary-structure analysis, then evidence aggregation
9. Polish

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
