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

# ---- 3. The secondary level's assets (scripts/setup_secondary.py) and GOR IV ---------------
# Built in their own stage so the compilers and git stay out of the final image. The same base
# image as the application, so the PSIPRED programs and the gor4 wheel run there.
FROM python:3.12-slim-bookworm AS secondary
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git make gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/*
# gor4 (the GOR IV C code, built with cffi), pinned to the notebook's commit as in pyproject.toml.
RUN pip install --no-cache-dir cffi setuptools wheel \
 && pip wheel --no-cache-dir --no-deps --wheel-dir /wheels \
      "gor4 @ git+https://github.com/acorg/gor4.git@38de0ac7def0dde4f6c6efea3cce2fed772137d1"
# S4PRED and PSIPRED at their pinned commits, PSIPRED built, the S4PRED checkpoint (checksum
# checked) and the ESM-2 secondary-structure checkpoint: about 250 MB.
COPY backend/scripts/setup_secondary.py /tmp/build/setup_secondary.py
RUN pip install --no-cache-dir "huggingface_hub<1" \
 && python /tmp/build/setup_secondary.py --assets /opt/secondary \
 && rm -rf /opt/secondary/s4pred/.git /opt/secondary/psipred/.git

# ---- 4. The application ----------------------------------------------------------------
FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf-cache \
    PFP_DIAMOND_BIN=/opt/tools/bin/diamond \
    PFP_HMMSCAN_BIN=/opt/tools/bin/hmmscan \
    PFP_SECONDARY_DATA_DIR=/opt/secondary \
    PFP_PRELOAD_MODELS=on
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=tools /opt/tools /opt/tools
COPY --from=secondary /opt/secondary /opt/secondary
COPY --from=secondary /wheels /tmp/wheels

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

# pydssp (secondary structure of the tertiary level's AlphaFold DB structure), after PyTorch so
# pip keeps the CPU-only build; its uv.lock version if it is there. Then gor4 (GOR IV, the
# secondary level), from the wheel built above.
RUN pydssp_version="$(python /tmp/build/ml_versions.py /tmp/build/uv.lock pydssp 2>/dev/null || true)" \
 && pip install "pydssp${pydssp_version:+==${pydssp_version}}" \
 && python -c "import pydssp; print('pydssp ok')" \
 && pip install /tmp/wheels/gor4-*.whl \
 && rm -rf /tmp/wheels \
 && python -c "from gor4 import GOR4; print('gor4 ok')"

# The primary level's ESM-2 model, downloaded now so the server never has to. (The secondary
# level's ESM-2 SS3 checkpoint is in /opt/secondary/hf, from the stage above.)
RUN python -c "from transformers import AutoTokenizer, EsmModel; \
AutoTokenizer.from_pretrained('facebook/esm2_t6_8M_UR50D'); EsmModel.from_pretrained('facebook/esm2_t6_8M_UR50D')"
ENV HF_HUB_OFFLINE=1

RUN useradd --create-home --uid 1000 user
WORKDIR /home/user/app

# The primary level's databases, built as in scripts/setup_primary.sh (about 400 MB of
# downloads, about 5 GB on disk). Kept before the code so code changes do not rebuild them.
# fetch() tries each address in turn (official mirrors; plain HTTP as the last resort for
# Pfam), so one download server being unreachable does not stop a deploy. gunzip -t then
# checks that the archive arrived complete.
RUN mkdir -p backend/data/primary && cd backend/data/primary \
 && fetch() { \
      out="$1"; shift; \
      for url in "$@"; do \
        echo "Downloading $url"; \
        if curl -fL --retry 4 --retry-delay 15 --retry-connrefused --connect-timeout 30 -o "$out" "$url"; then return 0; fi; \
      done; \
      echo "Could not download $out from any address" >&2; return 1; \
    } \
 && fetch uniprot_sprot.fasta.gz \
      https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz \
      https://ftp.ebi.ac.uk/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz \
      https://ftp.expasy.org/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz \
 && gunzip -t uniprot_sprot.fasta.gz \
 && gunzip -f uniprot_sprot.fasta.gz \
 && /opt/tools/bin/diamond makedb --in uniprot_sprot.fasta -d swissprot --quiet \
 && rm -f uniprot_sprot.fasta \
 && fetch Pfam-A.hmm.gz \
      https://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam-A.hmm.gz \
      http://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam-A.hmm.gz \
 && gunzip -t Pfam-A.hmm.gz \
 && gunzip -f Pfam-A.hmm.gz \
 && /opt/tools/bin/hmmpress -f Pfam-A.hmm > /dev/null \
 && (fetch swissprot_release.txt \
       https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/reldate.txt \
       https://ftp.ebi.ac.uk/pub/databases/uniprot/current_release/knowledgebase/complete/reldate.txt \
     || true) \
 && (fetch Pfam.version.gz \
       https://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam.version.gz \
       http://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam.version.gz \
     && gunzip -c Pfam.version.gz > pfam_release.txt; rm -f Pfam.version.gz; true)

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
