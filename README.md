# ProtFunc — Hierarchical Protein Function Prediction Platform

[![Live Application](https://img.shields.io/badge/Live%20Server-protfunc.duckdns.org-2ea043?style=for-the-badge&logo=caddy&logoColor=white)](https://protfunc.duckdns.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.12-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/Frontend-React%2019%20%7C%20TypeScript%20%7C%20Vite%206-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Deployment-Docker%20Compose%20%7C%20Caddy%20HTTPS-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

> **ProtFunc** predicts the biochemical function of unseen protein sequences by systematically aggregating evidence across all **four structural tiers** of protein architecture (Primary, Secondary, Tertiary, and Quaternary), integrated through a literature-anchored Bayesian log-odds consensus engine.

---

## 🌐 Live Online Application

The production system is deployed and publicly accessible with SSL/HTTPS:

**🔗 Production Web Portal:** [https://protfunc.duckdns.org/](https://protfunc.duckdns.org/)  
**📖 Interactive OpenAPI / Swagger Documentation:** [https://protfunc.duckdns.org/docs](https://protfunc.duckdns.org/docs)  
**🩺 System Health & Active Modules API:** [https://protfunc.duckdns.org/api/health](https://protfunc.duckdns.org/api/health)

```json
{
  "status": "ok",
  "version": "0.4.0",
  "live_levels": ["primary", "secondary", "tertiary", "quaternary"]
}
```

---

## 📑 Table of Contents

- [System Architecture & Scientific Methodology](#-system-architecture--scientific-methodology)
- [Server Version Functionalities](#-server-version-functionalities)
  - [1. Progressive Real-Time Execution Engine](#1-progressive-real-time-execution-engine)
  - [2. Multi-Level Structural Analysis Hierarchy](#2-multi-level-structural-analysis-hierarchy)
  - [3. Bayesian Log-Odds Consensus Engine](#3-bayesian-log-odds-consensus-engine)
  - [4. Interactive Multi-Track Residue Map](#4-interactive-multi-track-residue-map)
  - [5. Pre-Computed Benchmark Examples](#5-pre-computed-benchmark-examples)
  - [6. Standardized Data Contract & JSON Export](#6-standardized-data-contract--json-export)
- [Local Installation & Execution Guide](#-local-installation--execution-guide)
  - [Prerequisites](#prerequisites)
  - [Option A: Full Docker Deployment (Mirrors Cloud Server)](#option-a-full-docker-deployment-mirrors-cloud-server)
  - [Option B: Native Local Development (Backend + Frontend)](#option-b-native-local-development-backend--frontend)
  - [Option C: Standalone Quaternary Pipeline CLI & Notebooks](#option-c-standalone-quaternary-pipeline-cli--notebooks)
- [Environment Variables & Configuration](#-environment-variables--configuration)
- [API Reference](#-api-reference)
- [Repository Structure](#-repository-structure)
- [Scientific Literature & References](#-scientific-literature--references)

---

## 🔬 System Architecture & Scientific Methodology

Most function prediction tools rely strictly on primary sequence alignments (e.g., BLAST) and fail when sequence identity falls below the **twilight zone (< 30%)**. ProtFunc solves this by constructing a multi-tiered evidentiary proof tree:

```
                            +---------------------------------+
                            |     Raw Amino Acid Sequence     |
                            +----------------+----------------+
                                             |
                   +-------------------------+-------------------------+
                   |                                                   |
         [Tier 1: Primary]                                   [Tier 2: Secondary]
     DIAMOND vs. Swiss-Prot                              5-Predictor Consensus:
     HMMER scan vs. Pfam-A                               (S4PRED, ESM-2 SS3, PSIPRED,
     ESM-2 Embeddings & ProtParam                         GOR IV, Chou-Fasman)
     Optional: EBI BLASTp & InterPro                     Cross-checked against PDBe/PDB
                   |                                                   |
                   +-------------------------+-------------------------+
                                             |
                   +-------------------------+-------------------------+
                   |                                                   |
         [Tier 3: Tertiary]                                  [Tier 4: Quaternary]
     AlphaFold DB 3D Model                               PDB Assemblies & PDBe PISA
     Foldseek Structural Homology                        Complex Portal & IntAct
     pydssp 3D DSSP Extraction                           Stoichiometry & Delta G Diss.
     Per-residue pLDDT Confidence                        Biological Assembly Conflict Engine
                   |                                                   |
                   +-------------------------+-------------------------+
                                             |
                                             v
                      +-----------------------------------------------+
                      |   Bayesian Log-Odds Integration & Verdict     |
                      |   - Base Transfer: Homology x Conservation    |
                      |   - Secondary Structure Consistency Bonus     |
                      |   - Quaternary Stoichiometry Consistency      |
                      |   - Final Calibrated Functional Assignment    |
                      +-----------------------------------------------+
```

---

## 🚀 Server Version Functionalities

The server instance at [https://protfunc.duckdns.org/](https://protfunc.duckdns.org/) includes a full suite of features designed for both research biologists and computational structural biologists:

### 1. Progressive Real-Time Execution Engine
* **Instant First Result:** The results page renders within ~60 seconds as soon as the **Primary structure** level finishes, providing an immediate provisional verdict and predicted function.
* **Non-Blocking Background Computation:** Secondary, Tertiary, and Quaternary levels compute concurrently in the background. As each level finishes, the frontend updates dynamically without requiring a full page reload.
* **Live Confidence Interval:** Displays real-time upper and lower confidence bounds indicating how pending levels could refine the overall score.

### 2. Multi-Level Structural Analysis Hierarchy

| Level | Engine & Tools | What It Determines | Evidence Rendered |
| :--- | :--- | :--- | :--- |
| **Primary** | DIAMOND, HMMER (Pfam-A), ESM-2, ProtParam, UniProt REST, EBI BLASTp / InterProScan | Closest homologs, domain architecture, molecular weight, theoretical pI, GRAVY hydropathicity, instability index. | Alignments, E-values, domain spans, physicochemical overview card. |
| **Secondary** | S4PRED, ESM-2 SS3, PSIPRED, GOR IV, Chou-Fasman, RCSB PDB / PDBe | 3-state secondary structure ($\alpha$-helix, $\beta$-strand, coil) consensus across 5 engines + agreement with experimental PDB structures. | Aligned per-residue prediction tracks, agreement %, structural breakdown chart. |
| **Tertiary** | AlphaFold DB, Foldseek, ProtParam, pydssp, UniProt | True 3D coordinate model, structural superimposition, structural homologs across PDB/Swiss-Prot, per-residue pLDDT. | AlphaFold DB 3D viewer link, Foldseek hit table (probability, TM-score), pLDDT confidence strips. |
| **Quaternary** | UniProt, Complex Portal, RCSB PDB, PDBe PISA, SWISS-MODEL, IntAct, AlphaFold-Multimer | Oligomeric state (monomer, homomer, heteromer), stoichiometry ($A_2$, $A_7$, $A_{14}$), symmetry ($C_1$, $D_7$), dissociation free energy ($\Delta G_{diss}$), biological vs. crystallographic assembly conflict resolution. | Biological assembly tables, PISA thermodynamic stability, interaction partners, stoichiometry badges. |

### 3. Bayesian Log-Odds Consensus Engine
Function assignment operates on a rigorous annotation transfer model:
$$\text{Confidence} = P(\text{homology to template}) \times P(\text{function conserved at distance})$$

* **Route Selection:**
  1. **Sequence Homology:** Primary hit with $\ge 30\%$ identity and $\ge 80\%$ coverage transfers annotated function.
  2. **Domain Architecture:** Pfam profile match ($E < 10^{-10}$) or integrated InterPro signature transfers family-level annotation.
  3. **Fold Conservation:** Tertiary Foldseek alignment ($\ge 50\%$ coverage, prob $\ge 0.5$) transfers fold-level function.
* **Log-Odds Adjustments:**
  * Secondary structure agreement with experimental PDB $\ge 75\% \implies +0.40$; $< 60\% \implies -1.00$.
  * Quaternary assembly confirmed or supported $\implies +0.40$; conflicting stoichiometry $\implies -0.50$.
* **Confidence Bands:** High ($\ge 0.80$), Moderate ($\ge 0.50$), Low ($< 0.50$).

### 4. Interactive Multi-Track Residue Map
* **Synchronized Residue Tracks:** Simultaneously view predictions from Chou-Fasman, GOR IV, PSIPRED, S4PRED, ESM-2 SS3, Consensus Secondary Structure, Charge, and Hydropathy.
* **Interactive Inspection:** Hover or scrub over any residue position for real-time detail readout.
* **Keyboard Navigation:** Full accessibility via `Left` / `Right` arrows and `Home` / `End` keys.

### 5. Pre-Computed Benchmark Examples
The server pre-computes five representative benchmark proteins for instant, zero-latency evaluation:
1. **Ubiquitin** (*Homo sapiens*, 76 aa) — Compact eukaryotic regulatory hub protein.
2. **Hemoglobin $\alpha$** (*Homo sapiens*, 142 aa) — Heterotetrameric ($A_2B_2$) oxygen transport globulin.
3. **Bacteriorhodopsin** (*Halobacterium salinarum*, 262 aa) — 7-transmembrane proton pump.
4. **p53 Tumor Suppressor** (*Homo sapiens*, 393 aa) — Intrinsically disordered homotetrameric transcription factor.
5. **AKT1 Kinase** (*Homo sapiens*, 480 aa) — Multi-domain signaling kinase.

### 6. Standardized Data Contract & JSON Export
* Conforms to the strict JSON data schema (`UI/docs/LEVEL_CONTRACT.md` and `schema/quaternary_output_contract.json`).
* One-click JSON export button to download the entire analysis payload for downstream machine learning or bioinformatics pipelines.
* Clean, print-ready CSS formatting for generating experimental PDF reports.

---

## 💻 Local Installation & Execution Guide

### Prerequisites

| Component | Minimum Version | Notes |
| :--- | :--- | :--- |
| **Operating System** | Linux, macOS, or Windows (WSL2 recommended for Windows) | Cloud container runs Ubuntu 24.04 LTS |
| **Node.js** | `>= 20.19.0` (LTS 22+ recommended) | Required for the React 19 frontend |
| **Python** | `3.12` | Managed seamlessly by `uv` |
| **uv** | Latest | Extremely fast Python package manager (`curl -LsSf https://astral.sh/uv/install.sh \| sh`) |
| **Docker & Compose** | Latest Docker Desktop or Engine | Recommended for full containerized reproduction |

---

### 📦 How to Download & Install Docker (Official Guides)

Docker is required for **Option A** to execute the complete multi-tier pipeline with all scientific databases and neural network models in an isolated Linux container.

| Platform | Official Documentation | Direct Download / Quick Command |
| :--- | :--- | :--- |
| **Windows** | [Docker Desktop for Windows Guide](https://docs.docker.com/desktop/setup/install/windows-install/) | [Download Docker Desktop for Windows](https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe) <br> *(or `winget install --id Docker.DockerDesktop`)* |
| **macOS** | [Docker Desktop for Mac Guide](https://docs.docker.com/desktop/setup/install/mac-install/) | [Download for Mac (Apple Silicon & Intel)](https://www.docker.com/products/docker-desktop/) <br> *(or `brew install --cask docker`)* |
| **Linux** | [Docker Engine Installation Guide](https://docs.docker.com/engine/install/) | [Official Convenience Script](https://docs.docker.com/engine/install/ubuntu/#install-using-the-convenience-script) <br> `curl -fsSL https://get.docker.com | sudo sh` |

#### Windows Installation Checklist (WSL2):
1. **Enable WSL 2**: Open PowerShell as Administrator and run:
   ```powershell
   wsl --install
   ```
   *(Reboot your computer if prompted by Windows to enable the Virtual Machine Platform).*
2. **Install Docker Desktop**: Run in Administrator PowerShell:
   ```powershell
   winget install --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
   ```
   *Or double-click the downloaded installer and accept the Windows UAC prompt.*
3. **Verify Installation**: Open Docker Desktop from the Start Menu, then verify in your terminal:
   ```powershell
   docker --version
   docker compose version
   ```

---

### Option A: Full Docker Deployment (Mirrors Cloud Server)

This runs the exact setup hosted on `protfunc.duckdns.org` (FastAPI backend + built React frontend + Caddy HTTPS proxy).

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aryanthepain/Bioinformatics_server.git
   cd Bioinformatics_server/UI/deploy
   ```

2. **Configure environment settings:**
   Copy the sample environment file:
   ```bash
   cp .env.example .env
   ```
   *For purely local testing without a domain*, edit `.env`:
   ```env
   SITE_ADDRESS=localhost
   PFP_PLACEHOLDER_LEVELS=
   ```

3. **Build and launch the containers:**
   ```bash
   docker compose up -d --build
   ```
   *Note: The initial build downloads databases (Swiss-Prot, Pfam-A, ESM-2 models) and takes 20–35 minutes. Subsequent builds are instantaneous via Docker layer caching.*

4. **Verify the installation:**
   Open [http://localhost:8000](http://localhost:8000) or [https://localhost](https://localhost) in your browser.

5. **(Optional) Pre-compute example benchmarks:**
   ```bash
   docker compose exec app python scripts/precompute.py http://127.0.0.1:8000
   ```

6. **View logs or restart:**
   ```bash
   docker compose logs -f app       # Follow server logs
   docker compose restart app       # Restart app
   docker compose down              # Stop containers
   ```

---

### Option B: Native Local Development (Backend + Frontend)

Run the backend and frontend in separate terminals with hot-reloading.

#### Terminal 1: Backend (FastAPI + Python 3.12 via `uv`)

```bash
cd UI/backend

# 1. Install all dependencies using uv
uv sync

# 2. (Fast UI mode) Start immediately with placeholder data:
PFP_PLACEHOLDER_LEVELS=tertiary uv run uvicorn app.main:app --reload --port 8000
```

To run with **full real local scientific models**:
```bash
# Setup primary databases (DIAMOND + Pfam-A ~5GB):
bash scripts/setup_primary.sh

# Setup secondary models (S4PRED, PSIPRED, ESM-2 SS3, GOR IV):
uv run python scripts/setup_secondary.py

# Optional: Add your SWISS-MODEL API token to backend/.env:
echo "SWISSMODEL_TOKEN=your_token_here" > .env

# Run FastAPI backend with live models:
uv run uvicorn app.main:app --reload --port 8000
```

The interactive OpenAPI documentation will be live at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

#### Terminal 2: Frontend (React 19 + TypeScript + Vite 6)

```bash
cd UI/frontend

# 1. Install Node dependencies
npm install

# 2. Launch Vite development server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser. All `/api` requests are automatically proxied to `http://localhost:8000`.

---

### Option C: Standalone Quaternary Pipeline CLI & Notebooks

You can run the Quaternary Structure Analysis pipeline directly from the command line or explore the interactive notebooks without running the web interface.

#### 1. CLI Execution
From the project root:

```bash
# Analyze by UniProt Accession:
python quaternary_pipeline.py --accession P0A6F5 --output quaternary_output.json

# Analyze from a raw FASTA file:
python quaternary_pipeline.py --fasta path/to/protein.fasta --output quaternary_output.json --verbose
```

#### 2. Interactive Jupyter Notebooks
All exploratory and validation notebooks are provided in the repository root:
* [`Quaternary_Structure.ipynb`](Quaternary_Structure.ipynb) — End-to-end interactive quaternary structure prediction and visualization workflow.
* [`Function_Prediction_Integration.ipynb`](Function_Prediction_Integration.ipynb) — Multi-tier data aggregation and consensus verdict derivation.
* [`Tertiary_protein_identification.ipynb`](Tertiary_protein_identification.ipynb) — AlphaFold DB structural alignment and Foldseek validation.
* [`Structure_Prediction.ipynb`](Structure_Prediction.ipynb) — Tertiary coordinate modelling and pLDDT assessment.
* [`Mapping_Protein_Function_from_Primary_Structure.ipynb`](Mapping_Protein_Function_from_Primary_Structure.ipynb) — Sequence alignment and Pfam domain discovery.

To start JupyterLab:
```bash
uv run jupyter lab
```

---

## ⚙️ Environment Variables & Configuration

The application is configured via environment variables (placed in `UI/deploy/.env` for Docker or `UI/backend/.env` for native development):

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SITE_ADDRESS` | `localhost` | Domain name(s) served by Caddy (e.g. `protfunc.duckdns.org`). |
| `PFP_CACHE` | `on` | Cache slow analysis results in `backend/data/cache` (`on` or `off`). |
| `PFP_PLACEHOLDER_LEVELS` | *none* | Comma-separated levels forced to use mock data (e.g. `tertiary,quaternary`). |
| `PFP_MOCK_DELAY_SCALE` | `1.0` | Set to `0` to remove simulated mock latency during UI development. |
| `PFP_EBI_EMAIL` | *none* | Contact email required by EMBL-EBI for remote BLASTp / InterProScan queries. |
| `PFP_QUICK_RESULT_SECONDS`| `0` | Seconds to wait for quaternary results before rendering provisional prediction. |
| `SWISSMODEL_TOKEN` | *none* | User API token for the SWISS-MODEL homology modelling repository. |

---

## 📡 API Reference

When the backend is active, complete interactive documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

| HTTP Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status, API version, and list of currently active live levels. |
| `GET` | `/api/examples` | Returns the list of pre-configured benchmark proteins. |
| `POST` | `/api/analyses` | Initiates an analysis job for a raw sequence. Returns immediately with `{ id, status: "queued" }`. |
| `GET` | `/api/analyses/{id}` | Long-poll or query the status, progress, level findings, and final consensus verdict. |
| `POST` | `/api/analyses/{id}/cancel` | Aborts an ongoing analysis job. |

---

## 📁 Repository Structure

```
Bioinformatics_server/
├── README.md                            # Comprehensive project & server documentation
├── pyproject.toml                       # Root Python project configuration & tool dependencies
├── requirements.txt                     # Pinned Python package dependencies
├── uv.lock                              # Deterministic dependency lockfile
├── quaternary_pipeline.py               # Standalone Quaternary Structure CLI & pipeline driver
├── quaternary_pipeline_architecture.md  # Visual architecture diagram of the Quaternary pipeline
├── quaternary_structure_output.json     # Standardized JSON schema output for sample targets
│
├── quaternary/                          # Modular Quaternary Analysis Package
│   ├── clients/                         # Upstream clients (AlphaFold, Complex Portal, IntAct, PISA, RCSB)
│   ├── models/                          # Pydantic domain models (Stoichiometry, Interface, Provenance)
│   ├── cache/                           # SQLite and JSON caching backends
│   ├── engine.py                        # Quaternary assembly inference engine
│   └── ui_adapter.py                    # Adapter mapping Quaternary results to LevelResult contract
│
├── UI/                                  # Full-Stack Web Application
│   ├── README.md                        # UI-specific architecture & development handbook
│   ├── deploy/                          # Production container & deployment files
│   │   ├── Dockerfile                   # Multi-stage production Docker build
│   │   ├── docker-compose.yml           # App + Caddy HTTPS orchestration
│   │   ├── Caddyfile                    # Automatic TLS reverse-proxy config
│   │   ├── setup_server.sh              # One-click Ubuntu server setup script
│   │   └── DEPLOY.md                    # In-depth cloud server deployment guide
│   ├── backend/                         # FastAPI Python 3.12 Backend
│   │   ├── app/                         # Application modules (API, runner, verdict, schemas)
│   │   │   └── levels/                  # Level adapters (primary, secondary, tertiary, quaternary)
│   │   └── scripts/                     # Verification, precomputation & setup scripts
│   └── frontend/                        # React 19 + TypeScript + Vite 6 Frontend
│       ├── src/components/              # UI screens (InputScreen, RunScreen, ResultsScreen, ResidueMap)
│       └── src/api/                     # Typed client & API schemas
│
├── notebooks/                           # Interactive Research & Validation Notebooks
│   ├── Quaternary_Structure.ipynb
│   ├── Function_Prediction_Integration.ipynb
│   ├── Tertiary_protein_identification.ipynb
│   ├── Structure_Prediction.ipynb
│   └── Mapping_Protein_Function_from_Primary_Structure.ipynb
│
├── schema/                              # Standardized JSON data contracts
│   └── quaternary_output_contract.json
└── tests/                               # Comprehensive automated pytest test suite
```

---

## 📚 Scientific Literature & References

1. **Tian, W., & Skolnick, J. (2003).** How well is enzyme function conserved as a function of pairwise sequence identity? *Journal of Molecular Biology*, 333(4), 863–882.
2. **Rost, B. (1999).** Twilight zone of protein sequence alignments. *Protein Engineering*, 12(2), 85–94.
3. **Rost, B. (2002).** Enzyme function less conserved than anticipated. *Journal of Molecular Biology*, 318(2), 595–608.
4. **Aloy, P., Ceulemans, H., Stark, A., & Russell, R. B. (2003).** The relationship between sequence and interaction divergence in multimeric proteins. *Journal of Molecular Biology*, 332(5), 989–998.
5. **van Kempen, M., et al. (2024).** Fast and accurate protein structure search with Foldseek. *Nature Biotechnology*, 42, 243–246.
6. **Jumper, J., et al. (2021).** Highly accurate protein structure prediction with AlphaFold. *Nature*, 596(7873), 583–589.
7. **Krissinel, E., & Henrick, K. (2007).** Inference of macromolecular assemblies from crystalline state (PISA). *Journal of Molecular Biology*, 372(3), 774–797.
8. **Mirdita, M., et al. (2022).** ColabFold: making protein folding accessible to all. *Nature Methods*, 19(6), 679–682.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
