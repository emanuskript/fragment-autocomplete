BEGIN;

INSERT INTO repository (name, short_name, repository_type, homepage_url, raw_metadata)
VALUES
  ('SUB Göttingen / GDZ', 'SUB/GDZ', 'library_repository', 'https://gdz.sub.uni-goettingen.de/', '{"seed_note":"Initial placeholder repository row; not sample manuscript data."}'::jsonb),
  ('Fragmentarium', 'Fragmentarium', 'fragment_repository', 'https://fragmentarium.ms/', '{"seed_note":"Initial placeholder repository row; not sample manuscript data."}'::jsonb),
  ('e-codices', 'e-codices', 'iiif_repository', 'https://www.e-codices.unifr.ch/', '{"seed_note":"Initial placeholder repository row; not sample manuscript data."}'::jsonb),
  ('Biblissima', 'Biblissima', 'metadata_repository', 'https://portail.biblissima.fr/', '{"seed_note":"Initial placeholder repository row; not sample manuscript data."}'::jsonb),
  ('Gallica / BnF', 'Gallica', 'iiif_repository', 'https://gallica.bnf.fr/', '{"seed_note":"Initial placeholder repository row; not sample manuscript data."}'::jsonb),
  ('Digital Bodleian', 'Bodleian', 'iiif_repository', 'https://digital.bodleian.ox.ac.uk/', '{"seed_note":"Initial placeholder repository row; not sample manuscript data."}'::jsonb),
  ('CoMMA', 'CoMMA', 'text_metadata_resource', NULL, '{"seed_note":"Initial placeholder text/metadata resource row; not a visual reconstruction dataset."}'::jsonb)
ON CONFLICT (name) DO UPDATE
SET
  short_name = EXCLUDED.short_name,
  repository_type = EXCLUDED.repository_type,
  homepage_url = EXCLUDED.homepage_url,
  raw_metadata = repository.raw_metadata || EXCLUDED.raw_metadata,
  updated_at = now();

COMMIT;
