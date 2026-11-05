#!/usr/bin/env bash
# Copies the saved results in backend/data/cache into backend/seed_cache.
# seed_cache is committed and copied into the hosted app (deploy/Dockerfile), so
# the proteins you have already analysed open instantly on the website.
#
#     bash scripts/update_seed_cache.sh      (from the backend folder), then commit
set -euo pipefail
cd "$(dirname "$0")/.."   # the backend folder

[ -d data/cache ] || { echo "No saved results yet (backend/data/cache). Analyse some proteins first."; exit 1; }
rm -rf seed_cache
cp -R data/cache seed_cache
find seed_cache \( -name '*.tmp' -o -name '.DS_Store' \) -delete
echo "Copied $(find seed_cache -name '*.json' | wc -l | tr -d ' ') saved results into backend/seed_cache."
echo "Commit them (git add backend/seed_cache) so the hosted app includes them."
