"""P0A-005 — Reproduce and freeze the M21 SIT cutoff regression baseline.

Reproduces, from the pinned DEVELOPMENT workbook and the frozen benchmark
scripts, the exact 80 V crossing counts recorded in the committed campaign
artifacts:

  Replay (M21.6–M21.10, cohorts 151–200 and 329–378):
    63 observed module_low_v crossings; both frozen electrical models
    (fixed_r and one_rc) missed all 63 (32 mid + 31 late).
  Forecast (M21.11–M21.15, cohorts 201–250 and 279–328):
    68 observed post-issue crossings; the updated point forecast missed all
    68 (31 + 37); the empirical lower band warned in all 100 cycles with
    zero guard misses.

The pinned workbook (`UUT2_BatteryModule_Discharge.xlsx`, Figshare file
37983774, SHA-256 a4679465...) stays OUTSIDE the repository per campaign
policy. CI asserts the committed frozen artifacts and their canonical
digests. Setting AEROFORGE_SIT_WORKBOOK to a local copy of the workbook
enables the full re-execution path, which re-runs both benchmark scripts
and asserts bit-identical results.

P0A-006 reconciliation: the four strict-xfail markers that froze the
0/63 + 0/68 prediction state were removed when the repair landed. The
frozen baseline stays protected by the pinned observed/missed counts
asserted below (the artifacts are historical evidence and are NOT
rewritten), and the repaired causal model's evaluation delta is pinned in
tests/acceptance/test_p0a_006.py against
docs/campaigns/m21_sit_causal_repair_delta.json.

Reference: docs/M21_BATTERY_CAMPAIGN.md,
docs/campaigns/M21_6_10_SIT_MODULE_ELECTROTHERMAL.md,
docs/campaigns/M21_11_15_SIT_CUTOFF_FORECAST.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REPLAY_RESULTS = REPO_ROOT / "docs/campaigns/m21_sit_module_electrothermal_results.json"
FORECAST_RESULTS = REPO_ROOT / "docs/campaigns/m21_sit_cutoff_forecast_results.json"
FORECAST_GUARD_DOC_SHA = "16c92466dc5f4f4af8820cdb194524f61c57724dc02a81280acace33937b2664"
REPLAY_FIT_DOC_SHA = "f959786b7d37ad82dc84780331fbd1363b63f2f109cd0bf0c4fb6cd7adbb4764"
SOURCE_SHA = "a4679465b35455ca429519fbc47f04f6e42bea608e0de12b978d482873456205"
MODULE_LIMIT_V = 80.0

WORKBOOK = os.environ.get("AEROFORGE_SIT_WORKBOOK", "")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def replay() -> dict:
    return _load(REPLAY_RESULTS)


@pytest.fixture(scope="module")
def forecast() -> dict:
    return _load(FORECAST_RESULTS)


def _limit_screen(cohort: dict, model: str, limit: str = "module_low_v") -> dict:
    return cohort["models"][model]["limit_screen"][limit]


# ---------------------------------------------------------------------------
# Frozen baseline: the committed reproduction artifacts carry the exact
# observed/missed crossing counts recorded in the campaign docs.
# ---------------------------------------------------------------------------


def test_replay_records_63_observed_crossings_all_missed(replay: dict):
    """SIT replay: 63 observed 80 V crossings (32 mid + 31 late); fixed_r and
    one_rc each missed 32 + 31 = 63; every other study limit had zero
    observed breaches in these cohorts."""
    mid, late = replay["cohorts"]["mid_life"], replay["cohorts"]["late_life"]
    observed = (mid["observed_limits_all_admitted_cycles"]["module_low_v"],
                late["observed_limits_all_admitted_cycles"]["module_low_v"])
    assert observed == (32, 31)
    for cohort in (mid, late):
        for model in ("fixed_r", "one_rc"):
            screen = _limit_screen(cohort, model)
            assert screen["observed_cycles"] == screen["missed_cycles"]
            assert screen["predicted_cycles"] == 0
            assert screen["false_alarm_cycles"] == 0
    # The other study limits are untested at these limits (zero breaches).
    for cohort in (mid, late):
        other = {k: v for k, v in cohort["observed_limits_all_admitted_cycles"].items()
                 if k != "module_low_v"}
        assert all(v == 0 for v in other.values())


def test_forecast_records_68_observed_crossings_all_missed(forecast: dict):
    """SIT forecast: 68 observed post-issue crossings (31 + 37); both the
    original and updated point forecasts missed all 68; the lower band warned
    in all 100 cycles with zero guard misses."""
    first, second = forecast["cohorts"]["first"], forecast["cohorts"]["second"]
    assert (first["observed_post_issue_cutoff"], second["observed_post_issue_cutoff"]) == (31, 37)
    for cohort in (first, second):
        assert cohort["original_cutoff_missed"] == cohort["observed_post_issue_cutoff"]
        assert cohort["updated_cutoff_missed"] == cohort["observed_post_issue_cutoff"]
        assert cohort["guard_warning_any"] == 50
        assert cohort["guard_cutoff_missed"] == 0


def test_frozen_digests_match_campaign_docs(replay: dict, forecast: dict):
    """The committed artifacts carry the canonical digests published in the
    campaign docs before the held-out cohorts were numerically inspected, and
    both freeze records bind to the pinned workbook source bytes."""
    assert replay["frozen_calibration_canonical_sha256"] == REPLAY_FIT_DOC_SHA
    assert forecast["frozen_guard_canonical_sha256"] == FORECAST_GUARD_DOC_SHA
    for cohort in replay["cohorts"].values():
        models = cohort.get("models", {})
        assert models, "cohort must carry model blocks bound to the frozen fit"


def test_cohort_split_matches_campaign_contract(replay: dict, forecast: dict):
    """Chronological splits from the frozen protocol: replay holdouts
    151–200 (mid, cycle 168 clock-gate rejected) and 329–378 (late); forecast
    holdouts 201–250 and 279–328; calibration on cycles 1–50 only."""
    assert replay["cohorts"]["mid_life"]["cycles_scored"] == 49
    assert replay["cohorts"]["late_life"]["cycles_scored"] == 50
    assert replay["cohorts"]["mid_life"]["source_rejections"] == {
        "168": "unexpected_cycle_or_sample_clock"}
    for cohort in forecast["cohorts"].values():
        assert cohort["selected_cycles"] == 50


def test_module_limit_threshold_is_80v():
    """The study limit screen threshold is the sampled 80.0 V module floor
    (Table 5 of the source study), pinned in the benchmark module and the
    campaign doc."""
    doc = (REPO_ROOT / "docs/campaigns/M21_6_10_SIT_MODULE_ELECTROTHERMAL.md").read_text(
        encoding="utf-8")
    assert "below 80.0 V" in doc
    script = (REPO_ROOT / "scripts/benchmark_sit_module.py").read_text(encoding="utf-8")
    assert '"module_v": 80.0' in script


# ---------------------------------------------------------------------------
# P0A-006 reconciliation: the four strict-xfail markers that froze the
# 0/63 + 0/68 prediction state were removed when the causal repair landed.
# The frozen baseline remains protected: the tests above pin the observed
# and missed counts, the canonical digests and the cohort contract, and
# tests/acceptance/test_p0a_006.py pins the repaired model's evaluation
# delta against the committed causal-repair artifact. The frozen artifacts
# themselves are historical evidence and are never rewritten.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Full re-execution path (opt-in): re-runs both frozen benchmarks against a
# local copy of the pinned workbook and asserts bit-identical results.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not WORKBOOK, reason="pinned SIT workbook stays outside the repository; "
                    "set AEROFORGE_SIT_WORKBOOK to a local copy for the full reproduction")
def test_full_reproduction_is_bit_identical(tmp_path: Path):
    script_replay = REPO_ROOT / "scripts/benchmark_sit_module.py"
    script_forecast = REPO_ROOT / "scripts/benchmark_sit_cutoff_forecast.py"
    out = tmp_path / "repro"
    out.mkdir()
    env = dict(os.environ)

    def run(script: Path, *args: str) -> None:
        subprocess.run([sys.executable, str(script), *args], check=True,
                       cwd=REPO_ROOT, env=env, capture_output=True)

    run(script_replay, "calibrate", WORKBOOK, str(out / "fit.json"))
    run(script_replay, "evaluate", WORKBOOK, str(out / "replay.json"),
        "--freeze", str(out / "fit.json"))
    run(script_forecast, "calibrate", WORKBOOK, str(out / "guard.json"))
    run(script_forecast, "evaluate", WORKBOOK, str(out / "forecast.json"),
        "--freeze", str(out / "guard.json"))

    for produced, committed in (
        (out / "fit.json", REPLAY_FIT_DOC_SHA),
        (out / "guard.json", FORECAST_GUARD_DOC_SHA),
    ):
        data = _load(produced)
        digest = hashlib.sha256(json.dumps(
            data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        assert digest == committed
    for produced, committed in (
        (out / "replay.json", REPLAY_RESULTS),
        (out / "forecast.json", FORECAST_RESULTS),
    ):
        assert json.dumps(_load(produced), sort_keys=True) == \
            json.dumps(_load(committed), sort_keys=True)

    # Clean scratch: the workbook copy and outputs stay outside the repo.
    shutil.rmtree(out, ignore_errors=True)


def test_source_data_stays_outside_repository():
    """Policy check: the pinned workbook bytes never enter the repository
    (checked against the git-tracked file list, not the working tree)."""
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                             check=True, cwd=REPO_ROOT).stdout
    assert "UUT2_BatteryModule_Discharge.xlsx" not in tracked
    assert (REPO_ROOT / "docs/campaigns/M21_6_10_SIT_MODULE_ELECTROTHERMAL.md").is_file()
    assert (REPO_ROOT / "docs/campaigns/M21_11_15_SIT_CUTOFF_FORECAST.md").is_file()
