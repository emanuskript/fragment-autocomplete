BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS repository (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  short_name TEXT,
  repository_type TEXT,
  homepage_url TEXT,
  iiif_base_url TEXT,
  country TEXT,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT repository_name_unique UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS manuscript (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repository_id UUID REFERENCES repository(id) ON DELETE SET NULL,
  shelfmark TEXT,
  title TEXT,
  date_not_before INTEGER,
  date_not_after INTEGER,
  place TEXT,
  language TEXT,
  script TEXT,
  material TEXT,
  description TEXT,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT manuscript_date_range_check CHECK (
    date_not_before IS NULL OR date_not_after IS NULL OR date_not_before <= date_not_after
  )
);

CREATE TABLE IF NOT EXISTS witness (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  manuscript_id UUID REFERENCES manuscript(id) ON DELETE SET NULL,
  external_source TEXT,
  external_identifier TEXT,
  shelfmark TEXT,
  title TEXT,
  language TEXT,
  date_not_before INTEGER,
  date_not_after INTEGER,
  iiif_manifest_url TEXT,
  text_url TEXT,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT witness_date_range_check CHECK (
    date_not_before IS NULL OR date_not_after IS NULL OR date_not_before <= date_not_after
  )
);

CREATE TABLE IF NOT EXISTS iiif_manifest_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repository_id UUID REFERENCES repository(id) ON DELETE SET NULL,
  manuscript_id UUID REFERENCES manuscript(id) ON DELETE SET NULL,
  manifest_url TEXT NOT NULL UNIQUE,
  manifest_json JSONB NOT NULL,
  fetched_at TIMESTAMPTZ,
  etag TEXT,
  last_modified TEXT,
  fetch_status TEXT NOT NULL DEFAULT 'pending',
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT iiif_manifest_cache_fetch_status_check CHECK (
    fetch_status IN ('pending', 'running', 'completed', 'failed', 'cancelled')
  )
);

CREATE TABLE IF NOT EXISTS canvas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  manuscript_id UUID REFERENCES manuscript(id) ON DELETE SET NULL,
  iiif_manifest_cache_id UUID REFERENCES iiif_manifest_cache(id) ON DELETE SET NULL,
  canvas_identifier TEXT,
  canvas_label TEXT,
  page_number TEXT,
  folio_number TEXT,
  width_px INTEGER,
  height_px INTEGER,
  physical_width_mm NUMERIC,
  physical_height_mm NUMERIC,
  sequence_index INTEGER,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT canvas_pixel_dimensions_check CHECK (
    (width_px IS NULL OR width_px > 0) AND (height_px IS NULL OR height_px > 0)
  ),
  CONSTRAINT canvas_physical_dimensions_check CHECK (
    (physical_width_mm IS NULL OR physical_width_mm > 0) AND
    (physical_height_mm IS NULL OR physical_height_mm > 0)
  )
);

CREATE TABLE IF NOT EXISTS image_asset (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canvas_id UUID REFERENCES canvas(id) ON DELETE SET NULL,
  repository_id UUID REFERENCES repository(id) ON DELETE SET NULL,
  asset_type TEXT,
  source_url TEXT,
  iiif_image_service_url TEXT,
  local_path TEXT,
  checksum_sha256 TEXT,
  media_type TEXT,
  width_px INTEGER,
  height_px INTEGER,
  dpi NUMERIC,
  color_mode TEXT,
  rights_statement TEXT,
  license TEXT,
  attribution TEXT,
  training_allowed BOOLEAN NOT NULL DEFAULT false,
  publication_allowed BOOLEAN NOT NULL DEFAULT false,
  demo_allowed BOOLEAN NOT NULL DEFAULT false,
  access_level TEXT NOT NULL DEFAULT 'private',
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT image_asset_access_level_check CHECK (access_level IN ('private', 'internal', 'restricted', 'public')),
  CONSTRAINT image_asset_pixel_dimensions_check CHECK (
    (width_px IS NULL OR width_px > 0) AND (height_px IS NULL OR height_px > 0)
  )
);

CREATE TABLE IF NOT EXISTS msi_asset (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  image_asset_id UUID NOT NULL REFERENCES image_asset(id) ON DELETE CASCADE,
  modality TEXT,
  wavelength_nm NUMERIC,
  band_name TEXT,
  local_path TEXT,
  source_url TEXT,
  checksum_sha256 TEXT,
  alignment_reference_asset_id UUID REFERENCES image_asset(id) ON DELETE SET NULL,
  alignment_transform JSONB NOT NULL DEFAULT '{}'::jsonb,
  registration_quality NUMERIC,
  rights_statement TEXT,
  license TEXT,
  attribution TEXT,
  training_allowed BOOLEAN NOT NULL DEFAULT false,
  publication_allowed BOOLEAN NOT NULL DEFAULT false,
  demo_allowed BOOLEAN NOT NULL DEFAULT false,
  access_level TEXT NOT NULL DEFAULT 'private',
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT msi_asset_access_level_check CHECK (access_level IN ('private', 'internal', 'restricted', 'public')),
  CONSTRAINT msi_asset_registration_quality_check CHECK (
    registration_quality IS NULL OR (registration_quality >= 0 AND registration_quality <= 1)
  )
);

CREATE TABLE IF NOT EXISTS fragment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  manuscript_id UUID REFERENCES manuscript(id) ON DELETE SET NULL,
  image_asset_id UUID REFERENCES image_asset(id) ON DELETE SET NULL,
  shelfmark TEXT,
  fragment_label TEXT,
  fragment_type TEXT,
  suspected_origin TEXT,
  orientation_degrees NUMERIC,
  contour_geom geometry(Polygon, 0),
  bbox_geom geometry(Polygon, 0),
  measured_width_mm NUMERIC,
  measured_height_mm NUMERIC,
  description TEXT,
  rights_statement TEXT,
  license TEXT,
  attribution TEXT,
  training_allowed BOOLEAN NOT NULL DEFAULT false,
  publication_allowed BOOLEAN NOT NULL DEFAULT false,
  demo_allowed BOOLEAN NOT NULL DEFAULT false,
  access_level TEXT NOT NULL DEFAULT 'private',
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fragment_access_level_check CHECK (access_level IN ('private', 'internal', 'restricted', 'public')),
  CONSTRAINT fragment_orientation_check CHECK (orientation_degrees IS NULL OR (orientation_degrees >= 0 AND orientation_degrees < 360)),
  CONSTRAINT fragment_measured_dimensions_check CHECK (
    (measured_width_mm IS NULL OR measured_width_mm > 0) AND
    (measured_height_mm IS NULL OR measured_height_mm > 0)
  )
);

CREATE TABLE IF NOT EXISTS annotation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type TEXT NOT NULL,
  target_id UUID NOT NULL,
  annotation_type TEXT,
  body_text TEXT,
  body_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  geometry_geom geometry(Geometry, 0),
  created_by TEXT,
  confidence NUMERIC,
  provenance TEXT,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT annotation_confidence_check CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE TABLE IF NOT EXISTS segmentation_run (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  image_asset_id UUID REFERENCES image_asset(id) ON DELETE SET NULL,
  fragment_id UUID REFERENCES fragment(id) ON DELETE SET NULL,
  model_name TEXT NOT NULL,
  model_version TEXT,
  model_source TEXT,
  parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'pending',
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  output_path TEXT,
  output_format TEXT,
  confidence_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  raw_output JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT segmentation_run_status_check CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
  CONSTRAINT segmentation_run_target_check CHECK (image_asset_id IS NOT NULL OR fragment_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS layout_region (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  segmentation_run_id UUID NOT NULL REFERENCES segmentation_run(id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  label_id INTEGER,
  confidence NUMERIC,
  region_geom geometry(Polygon, 0) NOT NULL,
  bbox_geom geometry(Polygon, 0) NOT NULL,
  reading_order_index INTEGER,
  region_area_px NUMERIC,
  mask_path TEXT,
  raw_region JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT layout_region_confidence_check CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  CONSTRAINT layout_region_area_check CHECK (region_area_px IS NULL OR region_area_px >= 0)
);

CREATE TABLE IF NOT EXISTS artificial_fragment_task (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_canvas_id UUID REFERENCES canvas(id) ON DELETE SET NULL,
  source_image_asset_id UUID NOT NULL REFERENCES image_asset(id) ON DELETE CASCADE,
  generated_fragment_image_asset_id UUID REFERENCES image_asset(id) ON DELETE SET NULL,
  mask_path TEXT,
  mask_family TEXT,
  random_seed BIGINT,
  crop_transform JSONB NOT NULL DEFAULT '{}'::jsonb,
  degradation_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
  ground_truth_placement JSONB NOT NULL DEFAULT '{}'::jsonb,
  split_name TEXT NOT NULL DEFAULT 'unknown',
  generation_version TEXT,
  parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT artificial_fragment_task_split_name_check CHECK (split_name IN ('train', 'validation', 'test', 'demo', 'unknown'))
);

CREATE TABLE IF NOT EXISTS reconstruction_job (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fragment_id UUID NOT NULL REFERENCES fragment(id) ON DELETE CASCADE,
  job_type TEXT NOT NULL,
  method_name TEXT,
  method_version TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT reconstruction_job_status_check CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS reconstruction_candidate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reconstruction_job_id UUID NOT NULL REFERENCES reconstruction_job(id) ON DELETE CASCADE,
  fragment_id UUID NOT NULL REFERENCES fragment(id) ON DELETE CASCADE,
  candidate_rank INTEGER NOT NULL,
  candidate_type TEXT,
  canvas_width_px INTEGER,
  canvas_height_px INTEGER,
  physical_width_mm NUMERIC,
  physical_height_mm NUMERIC,
  placement_transform JSONB NOT NULL DEFAULT '{}'::jsonb,
  estimated_canvas_geom geometry(Polygon, 0),
  estimated_fragment_geom geometry(Polygon, 0),
  estimated_layout_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  score NUMERIC,
  uncertainty NUMERIC,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  linked_analogues JSONB NOT NULL DEFAULT '[]'::jsonb,
  output_path TEXT,
  review_status TEXT NOT NULL DEFAULT 'unreviewed',
  reviewer_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT reconstruction_candidate_rank_check CHECK (candidate_rank >= 1),
  CONSTRAINT reconstruction_candidate_score_check CHECK (score IS NULL OR (score >= 0 AND score <= 1)),
  CONSTRAINT reconstruction_candidate_uncertainty_check CHECK (uncertainty IS NULL OR (uncertainty >= 0 AND uncertainty <= 1)),
  CONSTRAINT reconstruction_candidate_canvas_dimensions_check CHECK (
    (canvas_width_px IS NULL OR canvas_width_px > 0) AND
    (canvas_height_px IS NULL OR canvas_height_px > 0) AND
    (physical_width_mm IS NULL OR physical_width_mm > 0) AND
    (physical_height_mm IS NULL OR physical_height_mm > 0)
  ),
  CONSTRAINT reconstruction_candidate_review_status_check CHECK (
    review_status IN ('unreviewed', 'in_review', 'accepted', 'rejected', 'needs_revision')
  )
);

CREATE TABLE IF NOT EXISTS retrieval_embedding (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type TEXT NOT NULL,
  target_id UUID NOT NULL,
  embedding_model TEXT,
  embedding_version TEXT,
  embedding FLOAT8[],
  descriptor_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  descriptor_type TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS text_witness_link (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fragment_id UUID REFERENCES fragment(id) ON DELETE SET NULL,
  manuscript_id UUID REFERENCES manuscript(id) ON DELETE SET NULL,
  witness_id UUID REFERENCES witness(id) ON DELETE SET NULL,
  external_source TEXT,
  external_identifier TEXT,
  source_url TEXT,
  match_type TEXT,
  match_score NUMERIC,
  language TEXT,
  text_snippet TEXT,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT text_witness_link_match_score_check CHECK (match_score IS NULL OR (match_score >= 0 AND match_score <= 1)),
  CONSTRAINT text_witness_link_target_check CHECK (
    fragment_id IS NOT NULL OR manuscript_id IS NOT NULL OR witness_id IS NOT NULL
  )
);

CREATE TABLE IF NOT EXISTS evaluation_run (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  evaluation_type TEXT,
  target_type TEXT,
  target_id UUID,
  dataset_split TEXT NOT NULL DEFAULT 'unknown',
  metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  expert_rubric_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  failure_taxonomy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  evaluator TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT evaluation_run_dataset_split_check CHECK (dataset_split IN ('train', 'validation', 'test', 'demo', 'unknown'))
);

CREATE TABLE IF NOT EXISTS export_bundle (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reconstruction_candidate_id UUID REFERENCES reconstruction_candidate(id) ON DELETE SET NULL,
  fragment_id UUID REFERENCES fragment(id) ON DELETE SET NULL,
  export_type TEXT NOT NULL,
  export_path TEXT NOT NULL,
  media_type TEXT,
  checksum_sha256 TEXT,
  includes_observed_evidence BOOLEAN NOT NULL DEFAULT true,
  includes_inferred_structure BOOLEAN NOT NULL DEFAULT true,
  includes_illustrative_fill BOOLEAN NOT NULL DEFAULT false,
  rights_statement TEXT,
  license TEXT,
  attribution TEXT,
  access_level TEXT NOT NULL DEFAULT 'private',
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT export_bundle_access_level_check CHECK (access_level IN ('private', 'internal', 'restricted', 'public')),
  CONSTRAINT export_bundle_target_check CHECK (reconstruction_candidate_id IS NOT NULL OR fragment_id IS NOT NULL)
);

DO $$
DECLARE
  table_name TEXT;
  table_names TEXT[] := ARRAY[
    'repository',
    'manuscript',
    'witness',
    'iiif_manifest_cache',
    'canvas',
    'image_asset',
    'msi_asset',
    'fragment',
    'annotation',
    'segmentation_run',
    'layout_region',
    'artificial_fragment_task',
    'reconstruction_job',
    'reconstruction_candidate',
    'retrieval_embedding',
    'text_witness_link',
    'evaluation_run',
    'export_bundle'
  ];
BEGIN
  FOREACH table_name IN ARRAY table_names LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS set_%I_updated_at ON %I', table_name, table_name);
    EXECUTE format(
      'CREATE TRIGGER set_%I_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
      table_name,
      table_name
    );
  END LOOP;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_repository_name ON repository(name);
CREATE INDEX IF NOT EXISTS idx_manuscript_repository_id ON manuscript(repository_id);
CREATE INDEX IF NOT EXISTS idx_manuscript_shelfmark ON manuscript(shelfmark);
CREATE INDEX IF NOT EXISTS idx_witness_manuscript_id ON witness(manuscript_id);
CREATE INDEX IF NOT EXISTS idx_witness_external_source_identifier ON witness(external_source, external_identifier);
CREATE INDEX IF NOT EXISTS idx_iiif_manifest_cache_repository_id ON iiif_manifest_cache(repository_id);
CREATE INDEX IF NOT EXISTS idx_iiif_manifest_cache_manuscript_id ON iiif_manifest_cache(manuscript_id);
CREATE INDEX IF NOT EXISTS idx_iiif_manifest_cache_manifest_url ON iiif_manifest_cache(manifest_url);
CREATE INDEX IF NOT EXISTS idx_canvas_manuscript_id ON canvas(manuscript_id);
CREATE INDEX IF NOT EXISTS idx_canvas_iiif_manifest_cache_id ON canvas(iiif_manifest_cache_id);
CREATE INDEX IF NOT EXISTS idx_canvas_canvas_identifier ON canvas(canvas_identifier);
CREATE INDEX IF NOT EXISTS idx_image_asset_canvas_id ON image_asset(canvas_id);
CREATE INDEX IF NOT EXISTS idx_image_asset_repository_id ON image_asset(repository_id);
CREATE INDEX IF NOT EXISTS idx_image_asset_source_url ON image_asset(source_url);
CREATE INDEX IF NOT EXISTS idx_image_asset_checksum_sha256 ON image_asset(checksum_sha256);
CREATE INDEX IF NOT EXISTS idx_msi_asset_image_asset_id ON msi_asset(image_asset_id);
CREATE INDEX IF NOT EXISTS idx_msi_asset_alignment_reference_asset_id ON msi_asset(alignment_reference_asset_id);
CREATE INDEX IF NOT EXISTS idx_fragment_manuscript_id ON fragment(manuscript_id);
CREATE INDEX IF NOT EXISTS idx_fragment_image_asset_id ON fragment(image_asset_id);
CREATE INDEX IF NOT EXISTS idx_fragment_shelfmark ON fragment(shelfmark);
CREATE INDEX IF NOT EXISTS idx_annotation_target ON annotation(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_segmentation_run_image_asset_id ON segmentation_run(image_asset_id);
CREATE INDEX IF NOT EXISTS idx_segmentation_run_fragment_id ON segmentation_run(fragment_id);
CREATE INDEX IF NOT EXISTS idx_segmentation_run_model ON segmentation_run(model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_layout_region_segmentation_run_id ON layout_region(segmentation_run_id);
CREATE INDEX IF NOT EXISTS idx_layout_region_label ON layout_region(label);
CREATE INDEX IF NOT EXISTS idx_artificial_fragment_task_source_canvas_id ON artificial_fragment_task(source_canvas_id);
CREATE INDEX IF NOT EXISTS idx_artificial_fragment_task_source_image_asset_id ON artificial_fragment_task(source_image_asset_id);
CREATE INDEX IF NOT EXISTS idx_artificial_fragment_task_generated_fragment_image_asset_id ON artificial_fragment_task(generated_fragment_image_asset_id);
CREATE INDEX IF NOT EXISTS idx_reconstruction_job_fragment_id ON reconstruction_job(fragment_id);
CREATE INDEX IF NOT EXISTS idx_reconstruction_candidate_fragment_id ON reconstruction_candidate(fragment_id);
CREATE INDEX IF NOT EXISTS idx_reconstruction_candidate_reconstruction_job_id ON reconstruction_candidate(reconstruction_job_id);
CREATE INDEX IF NOT EXISTS idx_reconstruction_candidate_candidate_rank ON reconstruction_candidate(candidate_rank);
CREATE INDEX IF NOT EXISTS idx_retrieval_embedding_target ON retrieval_embedding(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_text_witness_link_fragment_id ON text_witness_link(fragment_id);
CREATE INDEX IF NOT EXISTS idx_text_witness_link_manuscript_id ON text_witness_link(manuscript_id);
CREATE INDEX IF NOT EXISTS idx_text_witness_link_witness_id ON text_witness_link(witness_id);
CREATE INDEX IF NOT EXISTS idx_text_witness_link_external_source_identifier ON text_witness_link(external_source, external_identifier);
CREATE INDEX IF NOT EXISTS idx_evaluation_run_target ON evaluation_run(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_export_bundle_reconstruction_candidate_id ON export_bundle(reconstruction_candidate_id);
CREATE INDEX IF NOT EXISTS idx_export_bundle_fragment_id ON export_bundle(fragment_id);

CREATE INDEX IF NOT EXISTS idx_fragment_contour_geom ON fragment USING GIST (contour_geom);
CREATE INDEX IF NOT EXISTS idx_fragment_bbox_geom ON fragment USING GIST (bbox_geom);
CREATE INDEX IF NOT EXISTS idx_annotation_geometry_geom ON annotation USING GIST (geometry_geom);
CREATE INDEX IF NOT EXISTS idx_layout_region_region_geom ON layout_region USING GIST (region_geom);
CREATE INDEX IF NOT EXISTS idx_layout_region_bbox_geom ON layout_region USING GIST (bbox_geom);
CREATE INDEX IF NOT EXISTS idx_reconstruction_candidate_estimated_canvas_geom ON reconstruction_candidate USING GIST (estimated_canvas_geom);
CREATE INDEX IF NOT EXISTS idx_reconstruction_candidate_estimated_fragment_geom ON reconstruction_candidate USING GIST (estimated_fragment_geom);

COMMIT;
