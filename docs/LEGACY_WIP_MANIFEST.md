# Preserved 21-file WIP manifest

Remote branch: [archive/aeroforge-wip-2026-11](https://github.com/god88844-hub/aerodynamics-lab/tree/archive/aeroforge-wip-2026-11). Archive commit `a1d7313146b687e78468df9a5b66a3920120092c`; comparison main `8a511949a639b8b42d27a9c7ba9967b661db1c06`. The archive is unmerged. Two paths already matched before reconciliation; two provenance paths were promoted; 17 paths retain quarantined WIP. Blob equality is byte identity within Git, not evidence that unrelated WIP is authorized. Current main may contain independent security/compatibility maintenance in the same paths.

Reproduce inventory: `git diff-tree --no-commit-id --name-only -r a1d7313146b687e78468df9a5b66a3920120092c`; compare blobs with `git rev-parse REF:PATH`.

| Path | Disposition | Archive Git blob SHA-1 | Main Git blob SHA-1 |
| --- | --- | --- | --- |
| `.github/workflows/ci.yml` | QUARANTINED / unpromoted WIP | `f900f2d63a6896722c622e228037a193de52cba3` | `863e3fe56f4505270d88c5f6f53f3ccada5ee0e3` |
| `apps/api/app/services/run_provenance.py` | Already present at audited pre-reconciliation main | `30eaaef3fc30a97758aedc3784dcf23a95b26124` | `30eaaef3fc30a97758aedc3784dcf23a95b26124` |
| `apps/api/app/services/simulation_service.py` | Provenance hook/regression promoted; later maintenance retained | `855e2fff96097df9fbfeefa45b13ccf3760b416b` | `855e2fff96097df9fbfeefa45b13ccf3760b416b` |
| `apps/web/e2e/accessibility.spec.ts` | QUARANTINED / unpromoted WIP | `6905a8707cae7ad33b47135947bfb865f5c2dbe2` | `absent` |
| `apps/web/e2e/production-stack.spec.ts` | QUARANTINED / unpromoted WIP | `1ac47eeddbcaa5b446612fd502d06d77d5957c8d` | `5215ae382f4ce713dfb3c3515fa14e6dbff00df9` |
| `apps/web/package-lock.json` | QUARANTINED / unpromoted WIP | `02a60ef2bb62b5dde69eb5d4e5f101f5fadf8da5` | `3f23df31d8910d57e56385c2243817dd310fda9c` |
| `apps/web/package.json` | QUARANTINED / unpromoted WIP | `d4e5f263e64f0d5c0f68b0b14055aebc7b9eafdc` | `c7fcf5e7cb607dda90f5be7e5bb8feca789e0c0d` |
| `apps/web/src/App.tsx` | QUARANTINED / unpromoted WIP | `47750b8b500f8d9954eb29eae01f88d68179335f` | `f09cfede76d70c366c513f1e4ff1dd0f31e0682e` |
| `apps/web/src/charts/TelemetryCharts.tsx` | QUARANTINED / unpromoted WIP | `9118e624ccbe73bd2a1e9fb2fc8cf66628007125` | `d39ee000fcef2e4f69052d0375f955394ed029db` |
| `apps/web/src/editor/ComponentInspector.tsx` | QUARANTINED / unpromoted WIP | `92fe167b174efc837021ccaa9fc85752c885c895` | `80ad40d88bbf6e5e8926a4c1a95ac92cfb1540a3` |
| `apps/web/src/index.css` | QUARANTINED / unpromoted WIP | `ba6ad3d327ac236851d0af127af0198e300f2a85` | `8caaa07f0a84db8e09e918989a0287a943e46ffd` |
| `apps/web/src/panels/DesignPanel.tsx` | QUARANTINED / unpromoted WIP | `64dd4ed30f3653acac69d8f8e24588fc193e4911` | `fcdd46404f05efe9e88092d4916b26e6adf8dffd` |
| `apps/web/src/panels/FlightEvidencePanel.tsx` | QUARANTINED / unpromoted WIP | `9ba63bdd9d4976f002b8754ebb4afbea3439870c` | `c9a89da26b9d92b8cb990cdcf37284471e57f626` |
| `apps/web/src/panels/ResultsPanel.tsx` | QUARANTINED / unpromoted WIP | `08c4d1704c972c6886ed2f28b740602ce7f87e97` | `ad0cbd2df7883e44fd9ba2e6ea51ab532f572aa7` |
| `apps/web/src/panels/ScenarioPanel.tsx` | QUARANTINED / unpromoted WIP | `8d37a57814ef3a8585d9f8a7e11b811dd177a9d0` | `de9efc1219f38dc4c4dece8c534e785e61faa607` |
| `apps/web/src/panels/fields.tsx` | QUARANTINED / unpromoted WIP | `6b43381d004c2adb65e85d677f1d2c94708cb318` | `4a770a8e785b0c6d092c18ffef19d4bb3b832331` |
| `apps/web/src/playback/PlaybackWorkspace.tsx` | QUARANTINED / unpromoted WIP | `b867e562d2ad1aa9789d577d2d75b8e35af44749` | `7222c3ee1d26eb6c8bb37e57c9136b2e352793b6` |
| `scripts/check_api_load.py` | QUARANTINED / unpromoted WIP | `3d2b457205e0f9e19d434478bbc55133ba57b7e3` | `absent` |
| `scripts/verify_release_ci.py` | QUARANTINED / unpromoted WIP | `b7c9678b09f2c9b326ee21797b491f4c8ba79632` | `183ab882edd67b43c60ae84b908f19336bcc4c2c` |
| `tests/integration/test_api.py` | Provenance hook/regression promoted; later maintenance retained | `829d8b90f842c3a32f5896fe7c7b04a18eaff8c5` | `95299059cf6bb5958585a306b1053b0180ff785b` |
| `tests/integration/test_run_provenance.py` | Already present at audited pre-reconciliation main | `0f5613bb22041ff0a3753438b6a5896c325315a6` | `0f5613bb22041ff0a3753438b6a5896c325315a6` |
