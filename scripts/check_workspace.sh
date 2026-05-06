#!/usr/bin/env bash

set -u

required_dirs=(
  "docs"
  "docs/figures"
  "docs/figures/architecture"
  "docs/meetings"
  "infra"
  "infra/db"
  "infra/db/migrations"
  "infra/db/seed"
  "src"
  "src/backend"
  "src/frontend"
  "src/ingestion"
  "src/ml"
  "src/evaluation"
  "src/shared"
  "scripts"
  "data"
  "data/raw"
  "data/processed"
  "data/metadata"
  "models"
  "outputs"
  "tests"
)

required_files=(
  "README.md"
  "AGENTS.md"
  "ROADMAP_STATUS.md"
  "PROJECT_BOARD.md"
  "NEXT_ACTIONS.md"
  "CHANGELOG.md"
  "docs/01_architecture_overview.md"
  "docs/02_database_plan.md"
  "docs/architecture_build_notes.md"
  "infra/db/docker-compose.yml"
  "infra/db/README.md"
  "infra/db/migrations/001_init.sql"
  "infra/db/seed/001_seed_lookup_values.sql"
  "scripts/render_architecture_figures.sh"
  "scripts/build_architecture_pdf.sh"
  "scripts/check_workspace.sh"
  "scripts/db_start.sh"
  "scripts/db_migrate.sh"
  "scripts/db_reset.sh"
  "scripts/db_validate.sh"
)

figure_names=(
  "fig01_system_context"
  "fig02_high_level_pipeline"
  "fig03_component_architecture"
  "fig04_data_lifecycle"
  "fig05_emanuskript_backbone"
  "fig06_reconstruction_candidate_flow"
  "fig07_database_entity_overview"
  "fig08_evaluation_loop"
  "fig09_deployment_architecture"
  "fig10_first_90_days_status"
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
echo "Checking architecture figure sources and SVGs..."
for name in "${figure_names[@]}"; do
  source_path="docs/figures/architecture/${name}.mmd"
  svg_path="docs/figures/architecture/${name}.svg"

  if [ -f "$source_path" ]; then
    echo "  [OK]   $source_path"
  else
    echo "  [MISS] $source_path"
    missing=$((missing + 1))
  fi

  if [ -f "$svg_path" ]; then
    echo "  [OK]   $svg_path"
  else
    echo "  [MISS] $svg_path"
    missing=$((missing + 1))
  fi
done

echo
echo "Checking architecture document output..."
if [ -f "outputs/Fragment_Autocomplete_Architecture_Draft.pdf" ]; then
  echo "  [OK]   outputs/Fragment_Autocomplete_Architecture_Draft.pdf"
elif [ -f "outputs/Fragment_Autocomplete_Architecture_Draft.html" ]; then
  echo "  [OK]   outputs/Fragment_Autocomplete_Architecture_Draft.html"
else
  echo "  [MISS] outputs/Fragment_Autocomplete_Architecture_Draft.pdf or .html"
  missing=$((missing + 1))
fi

echo
if [ "$missing" -eq 0 ]; then
  echo "Workspace validation passed."
  echo "Summary: all required files, folders, figures, and document outputs are present."
  exit 0
fi

echo "Workspace validation failed."
echo "Summary: $missing required item(s) missing."
exit 1
