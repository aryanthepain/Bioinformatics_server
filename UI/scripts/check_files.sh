#!/bin/sh
# Checks that every file of the UI project is present.
# Run it from anywhere:
#     sh ~/Projects/Bioinformatics_server/UI/scripts/check_files.sh
# It prints nothing but a success line when the project is complete.

cd "$(dirname "$0")/.." || exit 1
missing=0
while IFS= read -r file; do
  [ -z "$file" ] && continue
  if [ ! -f "$file" ]; then
    echo "MISSING  UI/$file"
    missing=$((missing + 1))
  fi
done <<'FILES'
.gitignore
.vscode/settings.json
README.md
backend/.env.example
backend/.python-version
backend/app/__init__.py
backend/app/api.py
backend/app/cache.py
backend/app/config.py
backend/app/examples.py
backend/app/jobs.py
backend/app/levels/__init__.py
backend/app/levels/placeholders.py
backend/app/levels/primary.py
backend/app/levels/secondary.py
backend/app/levels/tertiary.py
backend/app/main.py
backend/app/runner.py
backend/app/schemas.py
backend/app/sequence.py
backend/app/verdict.py
backend/pyproject.toml
backend/scripts/check_primary.py
backend/scripts/check_tertiary.py
backend/scripts/setup_primary.sh
backend/scripts/smoke_test.py
docs/LEVEL_CONTRACT.md
frontend/index.html
frontend/package.json
frontend/public/favicon.svg
frontend/src/App.tsx
frontend/src/api/client.ts
frontend/src/api/types.ts
frontend/src/components/Header.css
frontend/src/components/Header.tsx
frontend/src/components/InputScreen.css
frontend/src/components/InputScreen.tsx
frontend/src/components/LevelAnalysis.css
frontend/src/components/LevelAnalysis.tsx
frontend/src/components/LevelStatusTag.tsx
frontend/src/components/MessageScreen.tsx
frontend/src/components/ResidueMap.css
frontend/src/components/ResidueMap.tsx
frontend/src/components/ResultsScreen.css
frontend/src/components/ResultsScreen.tsx
frontend/src/components/RunScreen.css
frontend/src/components/RunScreen.tsx
frontend/src/components/SequenceView.css
frontend/src/components/SequenceView.tsx
frontend/src/components/StepIcon.tsx
frontend/src/hooks/useAnalysis.ts
frontend/src/hooks/useBackendStatus.ts
frontend/src/hooks/useExamples.ts
frontend/src/hooks/useNow.ts
frontend/src/lib/anchors.ts
frontend/src/lib/download.ts
frontend/src/lib/format.ts
frontend/src/lib/sequence.ts
frontend/src/main.tsx
frontend/src/styles/global.css
frontend/src/styles/tokens.css
frontend/src/styles/tones.css
frontend/src/styles/ui.css
frontend/src/vite-env.d.ts
frontend/tsconfig.json
frontend/vite.config.ts
scripts/check_files.sh
FILES

if [ "$missing" -eq 0 ]; then
  echo "OK: all 66 project files are present."
else
  echo "$missing file(s) missing. The project is incomplete; do not run it yet."
  exit 1
fi
