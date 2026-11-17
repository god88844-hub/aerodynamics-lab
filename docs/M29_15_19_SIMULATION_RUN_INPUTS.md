# M29.15–M29.19 — Saved simulation inputs

| Phase | Acceptance check |
| --- | --- |
| M29.15 | Capture the validated design, requested scenario, submitted options, and effective solver options used by the API. |
| M29.16 | Save the input record in the same transaction as the report. Editing the design leaves the saved run's input bytes intact. |
| M29.17 | Return the SHA-256 with the run and verify the stored bytes before download. |
| M29.18 | Let users download the input JSON from the result's Trustworthiness section. |
| M29.19 | Preserve existing databases and verify the download across edits and API container replacement. |

## Download a run

Current run responses include `input_sha256`. The **Download simulation inputs**
link and `GET /api/simulations/{run_id}/inputs` return the same JSON bytes.
Calculate SHA-256 on the file as downloaded. Reformatting the JSON changes the
bytes. The download also includes the digest in `X-AeroForge-Input-SHA256`.

The record includes the validated design, scenario key, requested parameters,
effective API solver parameters, and physics package version. Predefined
settings inside the flight scenario are part of that model implementation.
This record covers the API inputs. Reproducing a numerical result across
installations also requires the matching build, component data, and numerical
environment. Matched-hardware evidence remains tracked in
[#16](https://github.com/god88844-hub/aeroforge/issues/16).

A run that fails during parameter parsing records the submitted options and
sets `effective_parameters` to null. A run refused by the solver retains the
options passed to it. If the stored bytes fail their digest check, the download
returns HTTP 409. Older results remain available with `input_sha256: null`.
Those input downloads return HTTP 404 because the historical inputs were never
recorded. Deleting a design also deletes its runs and their input records.

## Database upgrade

The packaged and development API add the new table at startup alongside the
existing tables. Deployments using Alembic run `alembic upgrade head` in their
configured API environment. Revision 0002 only adds the input table. It can
adopt the table if normal API startup already created it.

To roll back the application, retain the table so previously recorded inputs
remain available on re-upgrade. The database removes an input record when its
run is deleted, including deletes by the older application. Downgrading the
database revision to 0001 drops the input table and its data.
