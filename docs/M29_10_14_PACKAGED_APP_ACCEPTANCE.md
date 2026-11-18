# M29.10–M29.14 — Packaged app acceptance

| Phase | Acceptance check |
| --- | --- |
| M29.10 | The API image serves the reference design and the byte-verified public evidence from the shipped data directory. |
| M29.11 | A saved design and simulation result survive replacement of the API container on the SQLite volume. |
| M29.12 | Compose waits for service health. The web proxy reconnects to a replacement API while its own container keeps running. The default host bindings are loopback. |
| M29.13 | Chromium creates and edits one saved design, runs ideal hover, and renders the solver's trustworthiness verdict. |
| M29.14 | GitHub Actions runs this browser check against the built images alongside Python, frontend, and dependency-audit checks. |

## Run the packaged app

From the repository root:

```sh
docker compose up --build --wait
```

Open <http://127.0.0.1:5173>. The default SQLite database lives in the
`appdata` Compose volume, which survives `docker compose down` and container
recreation. This default mode is for local loopback access. For an installation
with authenticated users, use the [authenticated HTTPS overlay](M29_25_29_AUTHENTICATED_COMPOSE.md).

## Preserve existing Compose SQLite data before upgrading

An older API container stores its database at `/srv/aeroforge/aeroforge.db`.
If it contains data you want to keep, save it **before** recreating the old
container. Run these commands with the same Compose project name you used
for your deployment and choose an unused backup filename:

```sh
docker compose stop web api
docker compose cp api:/srv/aeroforge/aeroforge.db ./aeroforge-legacy.db
```

After the upgrade, restore the backup into the new volume before starting
the stack. The restore stages a complete copy before creating the destination.
If the destination already exists, the restore fails and preserves it.

```sh
docker compose build api
docker compose run --rm --no-deps -v "$PWD/aeroforge-legacy.db:/legacy.db:ro" api \
  python -c 'from pathlib import Path
from shutil import copyfileobj
from tempfile import NamedTemporaryFile

target = Path("/srv/aeroforge/state/aeroforge.db")
with Path("/legacy.db").open("rb") as source, NamedTemporaryFile(dir=target.parent) as staged:
    copyfileobj(source, staged)
    staged.flush()
    target.hardlink_to(staged.name)'
docker compose up --build --wait
```

Verify the saved designs in the UI and retain the original backup.

## Run the browser acceptance test

Use the separate `aeroforge-e2e` Compose project and make ports 5173 and 8000
available before starting. The test replaces that project's API container.

```sh
docker compose --project-name aeroforge-e2e up --build --wait
cd apps/web
npm ci
npx --no-install playwright install --only-shell chromium
npm run test:e2e
cd ../..
docker compose --project-name aeroforge-e2e down --volumes
```

The ideal-hover run verifies the software and deployment path. Independent
matched-hardware measurements and engineering review remain tracked in
[#16](https://github.com/god88844-hub/aeroforge/issues/16) and
[#28](https://github.com/god88844-hub/aeroforge/issues/28).
