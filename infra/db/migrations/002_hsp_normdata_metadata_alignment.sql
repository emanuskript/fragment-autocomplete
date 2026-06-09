BEGIN;

CREATE TABLE IF NOT EXISTS controlled_vocabulary (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  source_name TEXT,
  source_path TEXT,
  description TEXT,
  expected_term_count INTEGER,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT controlled_vocabulary_expected_count_check CHECK (
    expected_term_count IS NULL OR expected_term_count >= 0
  )
);

CREATE TABLE IF NOT EXISTS controlled_term (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vocabulary_id UUID NOT NULL REFERENCES controlled_vocabulary(id) ON DELETE CASCADE,
  notation TEXT NOT NULL,
  label_de TEXT,
  label_en TEXT,
  code_group TEXT,
  norm_uuid TEXT,
  allowed_values JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_sheet TEXT,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT controlled_term_unique_notation UNIQUE (vocabulary_id, notation)
);

CREATE TABLE IF NOT EXISTS metadata_controlled_term_assignment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_table TEXT NOT NULL,
  target_id UUID NOT NULL,
  field_name TEXT NOT NULL,
  vocabulary_id UUID NOT NULL REFERENCES controlled_vocabulary(id) ON DELETE RESTRICT,
  term_id UUID NOT NULL REFERENCES controlled_term(id) ON DELETE RESTRICT,
  notation TEXT NOT NULL,
  assignment_status TEXT NOT NULL DEFAULT 'machine_extracted',
  confidence NUMERIC,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT metadata_term_assignment_target_check CHECK (
    target_table IN ('repository', 'manuscript', 'witness', 'canvas', 'image_asset', 'msi_asset', 'fragment')
  ),
  CONSTRAINT metadata_term_assignment_status_check CHECK (
    assignment_status IN ('unreviewed', 'machine_extracted', 'human_reviewed', 'needs_review')
  ),
  CONSTRAINT metadata_term_assignment_confidence_check CHECK (
    confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
  ),
  CONSTRAINT metadata_term_assignment_unique UNIQUE (target_table, target_id, field_name, term_id)
);

CREATE TABLE IF NOT EXISTS fragment_location (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fragment_id UUID NOT NULL REFERENCES fragment(id) ON DELETE CASCADE,
  repository_id UUID REFERENCES repository(id) ON DELETE SET NULL,
  shelfmark TEXT,
  location_type TEXT NOT NULL DEFAULT 'secondary',
  notes TEXT,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fragment_location_type_check CHECK (
    location_type IN ('primary', 'secondary', 'suspected', 'former', 'unknown')
  )
);

ALTER TABLE repository
  ADD COLUMN IF NOT EXISTS hsp_key TEXT,
  ADD COLUMN IF NOT EXISTS gnd_uri TEXT,
  ADD COLUMN IF NOT EXISTS institution TEXT,
  ADD COLUMN IF NOT EXISTS institution_key TEXT,
  ADD COLUMN IF NOT EXISTS settlement TEXT,
  ADD COLUMN IF NOT EXISTS settlement_key TEXT,
  ADD COLUMN IF NOT EXISTS settlement_ref TEXT,
  ADD COLUMN IF NOT EXISTS repo_access_level TEXT,
  ADD COLUMN IF NOT EXISTS metadata_review_status TEXT NOT NULL DEFAULT 'unreviewed';

ALTER TABLE manuscript
  ADD COLUMN IF NOT EXISTS hsp_id TEXT,
  ADD COLUMN IF NOT EXISTS mxml_id TEXT,
  ADD COLUMN IF NOT EXISTS corpus_id TEXT,
  ADD COLUMN IF NOT EXISTS former_shelfmarks JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS object_status TEXT,
  ADD COLUMN IF NOT EXISTS object_form TEXT,
  ADD COLUMN IF NOT EXISTS object_form_notation TEXT,
  ADD COLUMN IF NOT EXISTS material_type JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS material_notation JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS format JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS format_notation TEXT,
  ADD COLUMN IF NOT EXISTS orig_date_display TEXT,
  ADD COLUMN IF NOT EXISTS orig_date_type TEXT,
  ADD COLUMN IF NOT EXISTS orig_date_precision TEXT,
  ADD COLUMN IF NOT EXISTS orig_place_norm JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS script_type_display TEXT,
  ADD COLUMN IF NOT EXISTS script_type_notation TEXT,
  ADD COLUMN IF NOT EXISTS script_type_uuid TEXT,
  ADD COLUMN IF NOT EXISTS script_grade TEXT,
  ADD COLUMN IF NOT EXISTS layout_class TEXT,
  ADD COLUMN IF NOT EXISTS column_count_notation TEXT,
  ADD COLUMN IF NOT EXISTS ruling_technique JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS decoration TEXT,
  ADD COLUMN IF NOT EXISTS music_notation TEXT,
  ADD COLUMN IF NOT EXISTS persons JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS organisations JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS metadata_review_status TEXT NOT NULL DEFAULT 'unreviewed';

ALTER TABLE witness
  ADD COLUMN IF NOT EXISTS text_title TEXT,
  ADD COLUMN IF NOT EXISTS text_author TEXT,
  ADD COLUMN IF NOT EXISTS author_gnd TEXT,
  ADD COLUMN IF NOT EXISTS text_rubric TEXT,
  ADD COLUMN IF NOT EXISTS text_incipit TEXT,
  ADD COLUMN IF NOT EXISTS text_explicit TEXT,
  ADD COLUMN IF NOT EXISTS locus_from TEXT,
  ADD COLUMN IF NOT EXISTS locus_to TEXT,
  ADD COLUMN IF NOT EXISTS specific_text_id TEXT,
  ADD COLUMN IF NOT EXISTS external_source_uri TEXT,
  ADD COLUMN IF NOT EXISTS metadata_review_status TEXT NOT NULL DEFAULT 'unreviewed';

ALTER TABLE canvas
  ADD COLUMN IF NOT EXISTS written_area_height_mm NUMERIC,
  ADD COLUMN IF NOT EXISTS written_area_width_mm NUMERIC,
  ADD COLUMN IF NOT EXISTS lines_per_page INTEGER,
  ADD COLUMN IF NOT EXISTS lines_per_column INTEGER,
  ADD COLUMN IF NOT EXISTS ruling_visible BOOLEAN,
  ADD COLUMN IF NOT EXISTS metadata_review_status TEXT NOT NULL DEFAULT 'unreviewed';

ALTER TABLE image_asset
  ADD COLUMN IF NOT EXISTS rights_uri TEXT,
  ADD COLUMN IF NOT EXISTS binarisation_method TEXT,
  ADD COLUMN IF NOT EXISTS metadata_review_status TEXT NOT NULL DEFAULT 'unreviewed';

ALTER TABLE msi_asset
  ADD COLUMN IF NOT EXISTS metadata_review_status TEXT NOT NULL DEFAULT 'unreviewed';

ALTER TABLE fragment
  ADD COLUMN IF NOT EXISTS parent_manuscript_id UUID REFERENCES manuscript(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS host_volume TEXT,
  ADD COLUMN IF NOT EXISTS damage_zone TEXT,
  ADD COLUMN IF NOT EXISTS damage_extent_pct NUMERIC,
  ADD COLUMN IF NOT EXISTS orig_width_mm NUMERIC,
  ADD COLUMN IF NOT EXISTS orig_height_mm NUMERIC,
  ADD COLUMN IF NOT EXISTS completeness_pct NUMERIC,
  ADD COLUMN IF NOT EXISTS lines_visible INTEGER,
  ADD COLUMN IF NOT EXISTS columns_visible INTEGER,
  ADD COLUMN IF NOT EXISTS margin_visible TEXT,
  ADD COLUMN IF NOT EXISTS metadata_review_status TEXT NOT NULL DEFAULT 'unreviewed';

DO $$
BEGIN
  ALTER TABLE repository
    ADD CONSTRAINT repository_repo_access_level_check CHECK (repo_access_level IS NULL OR repo_access_level IN ('open', 'restricted', 'closed'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE repository
    ADD CONSTRAINT repository_metadata_review_status_check CHECK (metadata_review_status IN ('unreviewed', 'machine_extracted', 'human_reviewed', 'needs_review'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE manuscript
    ADD CONSTRAINT manuscript_object_status_hsp_check CHECK (object_status IS NULL OR object_status IN ('existent', 'missing', 'destroyed', 'displaced', 'dismembered', 'unknown'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE manuscript
    ADD CONSTRAINT manuscript_object_form_hsp_check CHECK (
      object_form IS NULL OR object_form IN (
        'codex', 'collection', 'composite', 'leporello', 'sammelband', 'fragment',
        'printWithManuscriptParts', 'hostVolume', 'singleSheet', 'scroll', 'other'
      )
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE manuscript
    ADD CONSTRAINT manuscript_orig_date_type_check CHECK (orig_date_type IS NULL OR orig_date_type IN ('dated', 'datable'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE manuscript
    ADD CONSTRAINT manuscript_orig_date_precision_check CHECK (orig_date_precision IS NULL OR orig_date_precision IN ('certain', 'estimated', 'broad'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE manuscript
    ADD CONSTRAINT manuscript_script_grade_check CHECK (script_grade IS NULL OR script_grade IN ('calligraphic', 'semi-formal', 'informal', 'documentary'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE manuscript
    ADD CONSTRAINT manuscript_layout_class_check CHECK (layout_class IS NULL OR layout_class IN ('single_column', 'double_column', 'commentary_frame', 'four_column', 'other'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE manuscript
    ADD CONSTRAINT manuscript_decoration_check CHECK (decoration IS NULL OR decoration IN ('yes', 'no'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE manuscript
    ADD CONSTRAINT manuscript_music_notation_check CHECK (music_notation IS NULL OR music_notation IN ('yes', 'no'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE manuscript
    ADD CONSTRAINT manuscript_metadata_review_status_check CHECK (metadata_review_status IN ('unreviewed', 'machine_extracted', 'human_reviewed', 'needs_review'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE witness
    ADD CONSTRAINT witness_metadata_review_status_check CHECK (metadata_review_status IN ('unreviewed', 'machine_extracted', 'human_reviewed', 'needs_review'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE canvas
    ADD CONSTRAINT canvas_written_area_check CHECK (
      (written_area_width_mm IS NULL OR written_area_width_mm > 0) AND
      (written_area_height_mm IS NULL OR written_area_height_mm > 0)
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE canvas
    ADD CONSTRAINT canvas_line_counts_check CHECK (
      (lines_per_page IS NULL OR lines_per_page >= 0) AND
      (lines_per_column IS NULL OR lines_per_column >= 0)
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE canvas
    ADD CONSTRAINT canvas_metadata_review_status_check CHECK (metadata_review_status IN ('unreviewed', 'machine_extracted', 'human_reviewed', 'needs_review'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE image_asset
    ADD CONSTRAINT image_asset_metadata_review_status_check CHECK (metadata_review_status IN ('unreviewed', 'machine_extracted', 'human_reviewed', 'needs_review'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE msi_asset
    ADD CONSTRAINT msi_asset_metadata_review_status_check CHECK (metadata_review_status IN ('unreviewed', 'machine_extracted', 'human_reviewed', 'needs_review'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE fragment
    ADD CONSTRAINT fragment_damage_extent_pct_check CHECK (damage_extent_pct IS NULL OR (damage_extent_pct >= 0 AND damage_extent_pct <= 100));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE fragment
    ADD CONSTRAINT fragment_completeness_pct_check CHECK (completeness_pct IS NULL OR (completeness_pct >= 0 AND completeness_pct <= 100));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE fragment
    ADD CONSTRAINT fragment_original_dimensions_check CHECK (
      (orig_width_mm IS NULL OR orig_width_mm > 0) AND
      (orig_height_mm IS NULL OR orig_height_mm > 0)
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE fragment
    ADD CONSTRAINT fragment_visible_counts_check CHECK (
      (lines_visible IS NULL OR lines_visible >= 0) AND
      (columns_visible IS NULL OR columns_visible >= 0)
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE fragment
    ADD CONSTRAINT fragment_margin_visible_check CHECK (margin_visible IS NULL OR margin_visible IN ('inner', 'outer', 'upper', 'lower', 'unknown'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  ALTER TABLE fragment
    ADD CONSTRAINT fragment_metadata_review_status_check CHECK (metadata_review_status IN ('unreviewed', 'machine_extracted', 'human_reviewed', 'needs_review'));
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
DECLARE
  table_name TEXT;
  table_names TEXT[] := ARRAY[
    'controlled_vocabulary',
    'controlled_term',
    'metadata_controlled_term_assignment',
    'fragment_location'
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

CREATE INDEX IF NOT EXISTS idx_controlled_vocabulary_code ON controlled_vocabulary(code);
CREATE INDEX IF NOT EXISTS idx_controlled_term_vocabulary_id ON controlled_term(vocabulary_id);
CREATE INDEX IF NOT EXISTS idx_controlled_term_notation ON controlled_term(notation);
CREATE INDEX IF NOT EXISTS idx_controlled_term_norm_uuid ON controlled_term(norm_uuid);
CREATE INDEX IF NOT EXISTS idx_metadata_term_assignment_target ON metadata_controlled_term_assignment(target_table, target_id);
CREATE INDEX IF NOT EXISTS idx_metadata_term_assignment_field ON metadata_controlled_term_assignment(field_name);
CREATE INDEX IF NOT EXISTS idx_metadata_term_assignment_term_id ON metadata_controlled_term_assignment(term_id);
CREATE INDEX IF NOT EXISTS idx_fragment_location_fragment_id ON fragment_location(fragment_id);
CREATE INDEX IF NOT EXISTS idx_fragment_location_repository_id ON fragment_location(repository_id);
CREATE INDEX IF NOT EXISTS idx_manuscript_hsp_id ON manuscript(hsp_id);
CREATE INDEX IF NOT EXISTS idx_manuscript_mxml_id ON manuscript(mxml_id);
CREATE INDEX IF NOT EXISTS idx_manuscript_corpus_id ON manuscript(corpus_id);
CREATE INDEX IF NOT EXISTS idx_manuscript_object_form ON manuscript(object_form);
CREATE INDEX IF NOT EXISTS idx_manuscript_script_type_notation ON manuscript(script_type_notation);
CREATE INDEX IF NOT EXISTS idx_image_asset_rights_uri ON image_asset(rights_uri);
CREATE INDEX IF NOT EXISTS idx_fragment_parent_manuscript_id ON fragment(parent_manuscript_id);

COMMIT;
