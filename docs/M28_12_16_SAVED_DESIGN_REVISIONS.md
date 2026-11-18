# M28.12–M28.16 — Saved design revisions

| Phase | Implementation |
| --- | --- |
| M28.12 | Store a numbered snapshot and SHA-256 digest when a design is first saved. |
| M28.13 | Add a revision for a changed save and preserve the previous snapshot. The revision write and current design update share a transaction. |
| M28.14 | Treat the existing snapshot of an older saved design as its first revision. Preserve it on the first write that records history. |
| M28.15 | Restore an earlier snapshot from the editor and retain every intervening revision. |
| M28.16 | Verify concurrent saves, rollback, legacy database upgrades and browser restore after API container replacement. |

Open a saved design, choose an earlier **Saved revision**, and select **Restore revision**. A changed restore becomes the current revision immediately. Identical saves and retries of an already applied restore reuse the current revision. The revision history belongs to the saved design and is removed if the design is deleted.

The revisions API lists the number, timestamp, name and SHA-256 for each snapshot at `GET /api/designs/{design_id}/revisions`. Retrieve a specific snapshot at `GET /api/designs/{design_id}/revisions/{number}`. The digest covers UTF-8 JSON with sorted keys and compact separators, using the same encoding convention as saved simulation inputs. Stored simulation reports retain the snapshots they originally ran against.
