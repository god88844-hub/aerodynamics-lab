"""P0D-013: PX4 controller lockstep support and refusal of unsupported firmware/modes."""

from __future__ import annotations

import pytest

from physics.autonomy.sitl_and_swarms import SitlLockstepBridge, run_sitl_closed_loop_mission


def test_p0d_013_px4_mission_reproducibility_and_unsupported_refusal():
    px4_a = run_sitl_closed_loop_mission(firmware_kind="px4", seed=123)
    px4_b = run_sitl_closed_loop_mission(firmware_kind="px4", seed=123)
    assert px4_a == px4_b
    assert px4_a["firmware_kind"] == "px4"
    assert px4_a["verdict"] == "NO_MODELED_LIMIT_BREACHED"

    with pytest.raises(ValueError, match="Unsupported firmware_kind"):
        SitlLockstepBridge(firmware_kind="unsupported_custom_fc")
