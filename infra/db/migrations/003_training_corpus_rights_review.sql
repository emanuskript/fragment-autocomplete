BEGIN;

ALTER TABLE image_asset
  ADD COLUMN IF NOT EXISTS rights_review_status TEXT NOT NULL DEFAULT 'pending_review';

DO $$
BEGIN
  ALTER TABLE image_asset
    ADD CONSTRAINT image_asset_rights_review_status_check CHECK (
      rights_review_status IN ('pending_review', 'approved_for_training', 'not_approved', 'needs_review')
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_image_asset_rights_review_status
  ON image_asset(rights_review_status);

COMMIT;
