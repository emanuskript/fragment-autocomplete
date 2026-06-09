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
  "docs/03_iiif_ingestion_plan.md"
  "docs/05_local_assets_inventory.md"
  "docs/06_model_weights_compatibility_report.md"
  "docs/07_segmentation_test_inputs.md"
  "docs/08_segmentation_smoke_test_report.md"
  "docs/09_segmentation_storage_report.md"
  "docs/10_minimal_segmentation_viewer.md"
  "docs/11_full_pilot_segmentation_report.md"
  "docs/12_metadata_standards_alignment.md"
  "docs/architecture_build_notes.md"
  "data/metadata/local_assets_manifest.yaml"
  "data/metadata/initial_sample_dataset.yaml"
  "data/metadata/initial_sample_dataset_resolved.yaml"
  "data/metadata/model_weights_compatibility.yaml"
  "data/metadata/segmentation_test_inputs.yaml"
  "data/metadata/segmentation_smoke_test_results.yaml"
  "data/metadata/segmentation_storage_results.yaml"
  "data/metadata/segmentation_pilot_inputs.yaml"
  "data/metadata/segmentation_pilot_results.yaml"
  "data/metadata/segmentation_pilot_storage_results.yaml"
  "data/metadata/hsp_normdata_terms.yaml"
  "data/metadata/hsp_metadata_field_mapping.yaml"
  "data/metadata/hsp_normdata_import_results.yaml"
  "infra/db/docker-compose.yml"
  "infra/db/README.md"
  "infra/db/migrations/001_init.sql"
  "infra/db/migrations/002_hsp_normdata_metadata_alignment.sql"
  "infra/db/seed/001_seed_lookup_values.sql"
  "scripts/render_architecture_figures.sh"
  "scripts/build_architecture_pdf.sh"
  "scripts/check_workspace.sh"
  "scripts/db_start.sh"
  "scripts/db_migrate.sh"
  "scripts/db_reset.sh"
  "scripts/db_validate.sh"
  "scripts/ingest_iiif_manifest.py"
  "scripts/validate_iiif_ingestion.sh"
  "scripts/extract_hsp_metadata_standards.py"
  "scripts/import_hsp_normdata.py"
  "scripts/validate_hsp_metadata_alignment.sh"
  "scripts/inventory_local_assets.py"
  "scripts/inspect_model_weights.py"
  "scripts/prepare_segmentation_pilot_inputs.py"
  "scripts/prepare_segmentation_test_inputs.py"
  "scripts/register_initial_sample_dataset.py"
  "scripts/run_segmentation_pilot.py"
  "scripts/run_segmentation_smoke_test.py"
  "scripts/run_segmentation_viewer.sh"
  "scripts/store_segmentation_pilot_outputs.py"
  "scripts/store_segmentation_outputs.py"
  "scripts/validate_segmentation_pilot_inputs.sh"
  "scripts/validate_segmentation_pilot_run.sh"
  "scripts/validate_segmentation_pilot_storage.sh"
  "scripts/validate_segmentation_viewer.sh"
  "scripts/validate_segmentation_viewer_data.py"
  "scripts/validate_segmentation_smoke_test.sh"
  "scripts/validate_segmentation_storage.sh"
  "scripts/validate_segmentation_test_inputs.sh"
  "scripts/validate_initial_sample_dataset.sh"
  "scripts/view_segmentation_results.py"
  "models/model_registry.yaml"
  "src/ingestion/__init__.py"
  "src/ingestion/db.py"
  "src/ingestion/iiif_client.py"
  "src/ingestion/iiif_manifest.py"
  "src/ingestion/iiif_normalizer.py"
  "src/ingestion/iiif_ingest.py"
  "tests/ingestion/fixtures/iiif_v2_minimal_manifest.json"
  "tests/ingestion/fixtures/iiif_v3_minimal_manifest.json"
  "tests/ingestion/test_iiif_normalizer.py"
  "tests/ingestion/test_sample_dataset_config.py"
  "tests/metadata/test_hsp_normdata.py"
  "docs/04_initial_sample_dataset_report.md"
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
