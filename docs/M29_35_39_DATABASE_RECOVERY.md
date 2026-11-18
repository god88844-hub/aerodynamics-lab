# Reproducible Python dependencies and database recovery

M29.35 pins Python dependencies and distribution hashes in `apps/api/requirements.lock`. CI and the API image install that file with hash verification and binary wheels, then run `pip check`. Python, Node and Nginx build images are pinned by their multi-platform manifest digests. Nginx uses the stable Alpine release resolved on 18 November 2026. M29.36 adds a backend vulnerability audit.

To deliberately refresh the Python dependency set, run the following from the repository root, review the lockfile diff and pass the full CI workflow.

```sh
uv pip compile apps/api/requirements.txt --universal --python-version 3.11 --generate-hashes --output-file apps/api/requirements.lock
```

M29.37 provides `app.persistence.snapshot`. It opens the source read-only, uses SQLite's online backup API, checks database integrity and foreign keys, flushes the complete copy and publishes it at a new destination. A competing writer at the destination makes publication fail. The command prints the completed file's SHA-256. It includes committed WAL data and supports backups while the API is running. [Python SQLite backup API](https://docs.python.org/3.11/library/sqlite3.html#sqlite3.Connection.backup)

Choose a new backup path. Keep the exported file outside the deployment volume so it survives a volume loss.

```sh
docker compose exec api python -m app.persistence.snapshot /srv/aeroforge/state/aeroforge.db /tmp/aeroforge-backup.db
docker compose cp api:/tmp/aeroforge-backup.db ./aeroforge-backup.db
```

M29.38 verifies recovery through the application. To recover into a new state file, stop the API and web services, mount the backup read-only and create a checked snapshot.

```sh
docker compose stop api web
docker compose run --rm --no-deps -v "$PWD/aeroforge-backup.db:/backup.db:ro" api python -m app.persistence.snapshot /backup.db /srv/aeroforge/state/aeroforge.db
docker compose up --wait
```

The destination must be absent. Preserve an existing database and its journal files together before selecting a replacement. Use the recovery procedure on a separate deployment when assessing a backup. Store backups with access controls appropriate to the saved designs and measurements.

M29.39 packages Alembic and its migrations inside the API image. From the repository root, `python -m alembic -c apps/api/alembic.ini upgrade head` locates the included scripts. Existing Alembic-managed databases follow their recorded revision. Older databases created directly at application startup require schema inspection before assigning a baseline revision.

The packaged browser test takes a live backup after design edits and a simulation, restores it to another database and retrieves every design revision, the saved result and its original input digest through FastAPI. Regression tests also exercise live WAL transactions, corruption, existing destinations and competing publication.

M29 acceptance still requires the broader load, accessibility and complete provenance review described in issue #28. Physical acceptance and independent engineering review remain outstanding roadmap requirements.
