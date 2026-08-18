# Fragment Autocomplete Database

This folder contains the local PostgreSQL/PostGIS database foundation for Fragment Autocomplete.

It provides:

- PostgreSQL 16 with PostGIS through Docker Compose.
- Direct SQL migrations.
- Initial repository lookup seed values.
- Shell scripts for start, reset, migration, and validation.

The database foundation is accompanied by local registration scripts for IIIF/sample metadata, eManuSkript segmentation outputs, and artificial-fragment task metadata. Generated image and mask binaries remain filesystem artifacts and are never stored in PostgreSQL. Reconstruction, retrieval, training, frontend/backend product work, and deployment remain outside this milestone.

## Defaults

- Database: `fragment`
- User: `fragment`
- Password: `fragment_dev_password`
- Host port: `55432`

If port `55432` is already in use, set `FRAGMENT_DB_PORT`:

```bash
FRAGMENT_DB_PORT=55433 bash scripts/db_start.sh
```

Use the same environment variable for migration and validation commands when using a non-default host port.

## Commands

Start the database:

```bash
bash scripts/db_start.sh
```

Apply migrations and seed values:

```bash
bash scripts/db_migrate.sh
```

Validate the schema:

```bash
bash scripts/db_validate.sh
```

Register and validate the controlled 23-task artificial-fragment pilot:

```bash
python3 scripts/register_artificial_fragment_tasks.py --verbose
bash scripts/validate_artificial_fragment_task_registration.sh
```

The registration command uses deterministic scientific task identities and is safe to rerun. It stores artifact paths, SHA-256 checksums, dimensions, source relationships, transforms, generation settings, and layout-survival JSON in the existing `artificial_fragment_task` table. It does not register generated images as `image_asset` rows and does not store binary payloads.

Reset the local database volume:

```bash
bash scripts/db_reset.sh --yes
```

The reset command deletes the local Docker volume. It is intended for development only.
