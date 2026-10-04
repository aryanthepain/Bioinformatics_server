#!/usr/bin/env bash
# One-time setup for the primary-structure module. It mirrors the notebook's
# setup cell: Swiss-Prot formatted for DIAMOND, Pfam-A pressed for HMMER,
# plus the ESM-2 model. From the backend folder:
#
#     bash scripts/setup_primary.sh
#
# Needs about 5 GB of free disk space and roughly 400 MB of downloads.
# Safe to run again later: it rebuilds from the latest UniProt and Pfam releases.
set -euo pipefail

cd "$(dirname "$0")/.."   # the backend folder
DATA_DIR="data/primary"

say() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

command -v diamond  >/dev/null 2>&1 || fail "DIAMOND is not installed. Run: brew install diamond"
command -v hmmpress >/dev/null 2>&1 || fail "HMMER is not installed. Run: brew install hmmer"
command -v hmmscan  >/dev/null 2>&1 || fail "HMMER is not installed. Run: brew install hmmer"
command -v uv       >/dev/null 2>&1 || fail "uv is not installed."

free_kb=$(df -Pk . | awk 'NR==2 {print $4}')
if [ "$free_kb" -lt 5000000 ]; then
  fail "Less than 5 GB of free disk space."
fi

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

say "1/5  Downloading Swiss-Prot (about 90 MB)"
curl -fL --retry 3 --progress-bar -o uniprot_sprot.fasta.gz \
  https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz
gunzip -f uniprot_sprot.fasta.gz

say "2/5  Building the DIAMOND database"
diamond makedb --in uniprot_sprot.fasta -d swissprot --quiet
rm -f uniprot_sprot.fasta

say "3/5  Downloading Pfam-A (about 300 MB)"
curl -fL --retry 3 --progress-bar -o Pfam-A.hmm.gz \
  https://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam-A.hmm.gz
gunzip -f Pfam-A.hmm.gz

say "4/5  Pressing Pfam-A for HMMER"
hmmpress -f Pfam-A.hmm

# Which releases were downloaded (for your records; not required).
curl -fsL https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/reldate.txt \
  -o swissprot_release.txt || echo "(Swiss-Prot release note unavailable)"
curl -fsL https://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam.version.gz \
  | gunzip -c > pfam_release.txt || echo "(Pfam release note unavailable)"

cd ../..   # back to the backend folder

say "5/5  Downloading the ESM-2 model (about 30 MB)"
uv run python -c "
from transformers import AutoTokenizer, EsmModel
AutoTokenizer.from_pretrained('facebook/esm2_t6_8M_UR50D')
EsmModel.from_pretrained('facebook/esm2_t6_8M_UR50D')
print('ESM-2 model ready')
"

# Results computed with older databases are no longer valid.
rm -rf data/cache/primary

say "Done. Primary-structure analysis is ready; restart the backend if it is running."
