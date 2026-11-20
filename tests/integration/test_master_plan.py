"""Guard the executable planning handoff, dependency order and completion evidence."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_master_plan", ROOT / "scripts/check_master_plan.py")
plan_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan_module)


def test_master_document_and_issue_receipt_match_the_canonical_plan():
    plan = plan_module.load_plan()
    plan_module.validate(plan)
    assert (ROOT / plan_module.MASTER).read_text(encoding="utf-8-sig") == plan_module.render(plan)
    plan_module.check_sync(plan)
    assert len(plan["tasks"]) == 150
    assert sum(t["stage"].startswith("0") for t in plan["tasks"]) == 118


def test_dependency_cycle_cannot_publish_an_executable_plan():
    plan = deepcopy(plan_module.load_plan())
    task = next(t for t in plan["tasks"] if t["id"] == plan["first_build_task"])
    task["dependencies"].append(task["id"])
    with pytest.raises(ValueError, match="Dependency cycle"):
        plan_module.validate(plan, check_receipts=False)


def test_completed_task_cannot_omit_its_evidence():
    plan = deepcopy(plan_module.load_plan())
    plan["tasks"][0]["completion_evidence"] = []
    with pytest.raises(ValueError, match="Completed task needs evidence"):
        plan_module.validate(plan, check_receipts=False)


def test_first_implementation_cannot_bypass_owner_plan_approval():
    plan = deepcopy(plan_module.load_plan())
    next(t for t in plan["tasks"] if t["id"] == plan["first_build_task"])["dependencies"] = []
    with pytest.raises(ValueError, match="First implementation must depend on plan approval"):
        plan_module.validate(plan, check_receipts=False)
