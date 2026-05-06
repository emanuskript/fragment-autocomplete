# Fragment Autocomplete Database

This folder contains the local PostgreSQL/PostGIS database foundation for Fragment Autocomplete.

It provides:

- PostgreSQL 16 with PostGIS through Docker Compose.
- Direct SQL migrations.
- Initial repository lookup seed values.
- Shell scripts for start, reset, migration, and validation.

This is database infrastructure only. It does not implement IIIF ingestion, eManuSkript integration, artificial fragment generation, reconstruction, retrieval, ML, frontend, backend API, or deployment.

## Defaults

- Database: `fragment`
- User: `fragment`
- Password: `fragment_dev_password`
- Host port: `5432`

If port `5432` is already in use, set `FRAGMENT_DB_PORT`:

```bash
FRAGMENT_DB_PORT=55432 bash scripts/db_start.sh
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

Reset the local database volume:

```bash
bash scripts/db_reset.sh --yes
```

The reset command deletes the local Docker volume. It is intended for development only.
