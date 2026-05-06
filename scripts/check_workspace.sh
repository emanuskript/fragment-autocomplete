#!/usr/bin/env bash

set -u

required_files=(
  ".gitignore"
  ".editorconfig"
  "README.md"
  "AGENTS.md"
  "ROADMAP_STATUS.md"
  "PROJECT_BOARD.md"
  "NEXT_ACTIONS.md"
  "CHANGELOG.md"
  "docs/00_project_brief.md"
  "docs/01_architecture_overview.md"
  "docs/02_database_plan.md"
  "docs/03_data_sources.md"
  "docs/04_evaluation_plan.md"
  "docs/05_use_cases_20_30.md"
  "docs/06_risks_and_decisions.md"
  "docs/meetings/README.md"
  "src/backend/README.md"
  "src/frontend/README.md"
  "src/ingestion/README.md"
  "src/ml/README.md"
  "src/evaluation/README.md"
  "src/shared/README.md"
  "data/README.md"
  "data/raw/.gitkeep"
  "data/processed/.gitkeep"
  "data/metadata/.gitkeep"
  "models/.gitkeep"
  "outputs/.gitkeep"
  "scripts/check_workspace.sh"
)

required_dirs=(
  "docs"
  "docs/meetings"
  "src"
  "src/backend"
  "src/frontend"
  "src/ingestion"
  "src/ml"
  "src/evaluation"
  "src/shared"
  "data"
  "data/raw"
  "data/processed"
  "data/metadata"
  "models"
  "outputs"
  "scripts"
  "tests"
)

missing=0

echo "Checking required directories..."
for path in "${required_dirs[@]}"; do
  if [ -d "$path" ]; then
    echo "  [OK]   $path"
  else
    echo "  [MISS] $path"
    missing=$((missing + 1))
  fi
done

echo
echo "Checking required files..."
for path in "${required_files[@]}"; do
  if [ -f "$path" ]; then
    echo "  [OK]   $path"
  else
    echo "  [MISS] $path"
    missing=$((missing + 1))
  fi
done

echo
if [ "$missing" -eq 0 ]; then
  echo "Workspace validation passed."
  echo "Summary: all required files and directories are present."
  exit 0
fi

echo "Workspace validation failed."
echo "Summary: $missing required item(s) missing."
exit 1
