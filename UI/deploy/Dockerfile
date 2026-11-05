# The whole Protein Function Predictor (website, API and all four levels) as one image.
# Built by deploy/docker-compose.yml with the UI folder as the build context.
# Works on ARM (Oracle Cloud Ampere A1) and on ordinary x86-64 machines.

# ---- 1. The website (React + Vite) -----------------------------------------------
FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. DIAMOND and HMMER (Bioconda, via micromamba) --------------------------------
FROM debian:bookworm-slim AS tools
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl bzip2 \
 && rm -rf /var/lib/apt/lists/*
ENV MAMBA_ROOT_PREFIX=/opt/mamba
RUN case "$(uname -m)" in \
        aarch64|arm64) platform=linux-aarch64 ;; \
        x86_64) platform=linux-64 ;; \
        *) echo "Unsupported processor: $(uname -m)" >&2; exit 1 ;; \
    esac \
 && curl -fsSL "https://micro.mamba.pm/api/micromamba/${platform}/latest" | tar -xj -C /usr/local bin/micromamba \
 && micromamba create -y -p /opt/tools -c conda-forge -c bioconda diamond hmmer \
 && micromamba clean -a -y \
 && /opt/tools/bin/diamond version \
 && /opt/tools/bin/hmmscan -h | head -n 2

# ---- 3. The application ----------------------------------------------------------------
FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf-cache \
    PFP_DIAMOND_BIN=/opt/tools/bin/diamond \
    PFP_HMMSCAN_BIN=/opt/tools/bin/hmmscan \
    PFP_PRELOAD_MODELS=on
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=tools /opt/tools /opt/tools

# Python libraries: the versions pinned in uv.lock (requirements.txt is exported from it),
# plus PyTorch (CPU-only build, much smaller) and Transformers at their uv.lock versions.
COPY backend/requirements.txt backend/uv.lock deploy/ml_versions.py /tmp/build/
RUN pip install -r /tmp/build/requirements.txt \
 && torch_version="$(python /tmp/build/ml_versions.py /tmp/build/uv.lock torch)" \
 && transformers_version="$(python /tmp/build/ml_versions.py /tmp/build/uv.lock transformers)" \
 && ( pip install --index-url https://download.pytorch.org/whl/cpu "torch==${torch_version}" \
      || pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.4,<3" ) \
 && pip install "transformers==${transformers_version}" \
 && python -c "import torch, transformers; print('torch', torch.__version__, '| transformers', transformers.__version__)"

# The two models, downloaded now so the server never has to (about 1.7 GB).
RUN python -c "from transformers import AutoModelForTokenClassification, AutoTokenizer, EsmModel; \
AutoTokenizer.from_pretrained('facebook/esm2_t6_8M_UR50D'); EsmModel.from_pretrained('facebook/esm2_t6_8M_UR50D'); \
AutoTokenizer.from_pretrained('Rostlab/prot_bert_bfd_ss3'); AutoModelForTokenClassification.from_pretrained('Rostlab/prot_bert_bfd_ss3')"
ENV HF_HUB_OFFLINE=1

RUN useradd --create-home --uid 1000 user
WORKDIR /home/user/app

# The primary level's databases, built as in scripts/setup_primary.sh (about 400 MB of
# downloads, about 5 GB on disk). Kept before the code so code changes do not rebuild them.
RUN mkdir -p backend/data/primary && cd backend/data/primary \
 && curl -fL --retry 5 --retry-delay 10 -o uniprot_sprot.fasta.gz \
      https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz \
 && gunzip -f uniprot_sprot.fasta.gz \
 && /opt/tools/bin/diamond makedb --in uniprot_sprot.fasta -d swissprot --quiet \
 && rm -f uniprot_sprot.fasta \
 && curl -fL --retry 5 --retry-delay 10 -o Pfam-A.hmm.gz \
      https://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam-A.hmm.gz \
 && gunzip -f Pfam-A.hmm.gz \
 && /opt/tools/bin/hmmpress -f Pfam-A.hmm > /dev/null \
 && (curl -fsL https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/reldate.txt \
       -o swissprot_release.txt || true) \
 && (curl -fsL https://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam.version.gz | gunzip -c > pfam_release.txt || true)

# The application code and the built website.
COPY backend/ backend/
COPY --from=frontend /src/frontend/dist frontend/dist

# Saved example results (backend/seed_cache) start the result cache, so the examples open at once.
RUN mkdir -p backend/data/cache backend/data/quaternary_cache \
 && if [ -d backend/seed_cache ]; then cp -a backend/seed_cache/. backend/data/cache/; fi \
 && chown -R user:user backend/data/cache backend/data/quaternary_cache

USER user
WORKDIR /home/user/app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fs http://127.0.0.1:8000/api/health || exit 1
# One worker on purpose: analyses are kept in this process's memory.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
