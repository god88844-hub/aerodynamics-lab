"""Render/check the numbered product plan and generate issue checklist blocks.

This checks planning structure and declared receipts, not physical truth or authority.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import posixpath

ROOT = Path(__file__).resolve().parents[1]
PLAN = "docs/planning/tasks.json"
MASTER = "docs/MASTER_PLAN.md"
SYNC = "docs/planning/github_sync.json"
START = "<!-- AERODYNAMICS_MASTER_PLAN_START -->"
END = "<!-- AERODYNAMICS_MASTER_PLAN_END -->"


def load_plan(root=ROOT):
    return json.loads((root / PLAN).read_text(encoding="utf-8-sig"))


def plan_digest(root=ROOT):
    return sha256((root / PLAN).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def validate(plan, root=ROOT, *, check_receipts=True):
    tasks = plan["tasks"]
    by_id = {t["id"]: t for t in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("Duplicate task ID")
    packages = {p["number"]: p for p in plan["work_packages"]}
    if set(packages) != set(range(1, 13)):
        raise ValueError("All twelve work packages are required")
    expected_stages = {"0A", "0B", "0C", "0D", "1", "2", "3", "4"}
    if {t["stage"] for t in tasks} != expected_stages:
        raise ValueError("Every phase/slice requires a concrete checklist")
    seen_numbers = {}
    covered = set()
    for task in tasks:
        stage = task["stage"]
        seen_numbers[stage] = seen_numbers.get(stage, 0) + 1
        if task["id"] != f"P{stage}-{seen_numbers[stage]:03}":
            raise ValueError("Task numbering must be unique, ordered and consecutive per stage")
        if task["status"] not in {"done", "todo"} or task["actor"] not in {"builder", "owner", "custodian", "reviewer"}:
            raise ValueError("Unknown task status or responsible actor")
        if not task["acceptance"] or not task["proof_file"]:
            raise ValueError("Task needs a concrete acceptance condition and exact proof path")
        for path in [task["proof_file"], *task["planned_tests"]]:
            if Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError("Task artifacts must remain inside the repository")
        if task["actor"] == "builder" and task["status"] == "todo" and not task["planned_tests"]:
            raise ValueError("Builder implementation needs a declared verification target")
        if stage.startswith("0") and not task["work_packages"]:
            raise ValueError("Every Phase 0 task needs a work package")
        for wp in task["work_packages"]:
            if wp not in packages or stage not in packages[wp]["slices"]:
                raise ValueError("Task work-package/slice mapping disagrees with the plan")
            covered.add(wp)
        for dependency in task["dependencies"]:
            if dependency not in by_id:
                raise ValueError("Unknown prerequisite task")
        if task["status"] == "done":
            if not task["completion_evidence"]:
                raise ValueError("Completed task needs evidence")
            if any(by_id[d]["status"] != "done" for d in task["dependencies"]):
                raise ValueError("Completed task has an unfinished prerequisite")
            if check_receipts:
                for proof in task["completion_evidence"]:
                    if "://" not in proof and not (root / proof).is_file():
                        raise ValueError("Completed-task receipt is missing: " + proof)
    if covered != set(packages):
        raise ValueError("A work package has no executable task breakdown")
    active, visited = set(), set()

    def visit(ident):
        if ident in active:
            raise ValueError("Dependency cycle")
        if ident in visited:
            return
        active.add(ident)
        for dependency in by_id[ident]["dependencies"]:
            visit(dependency)
        active.remove(ident)
        visited.add(ident)

    for ident in by_id:
        visit(ident)
    for section in plan["slices"]:
        for key in ("entry", "software_exit", "physical_exit"):
            if section[key] not in by_id:
                raise ValueError("Slice entry/exit gate is missing")
    previous = plan["slices"][-1]["phase_exit"]
    for phase in plan["future_phases"]:
        if previous not in by_id[phase["entry"]]["dependencies"]:
            raise ValueError("Future phase bypasses its prerequisite phase exit")
        previous = phase["exit"]
    authorization = by_id[plan["authorization_task"]]
    if authorization["actor"] != "owner" or authorization["gate"] != "execution_authorization":
        raise ValueError("Owner plan-lock authorization gate is required")
    if plan["authorization_task"] not in by_id[plan["first_build_task"]]["dependencies"]:
        raise ValueError("First implementation must depend on plan approval")


def local_link(path):
    return path if "://" in path else posixpath.relpath(path, "docs")


def render(plan):
    lines = ["# Master task and execution plan", "", "21 November 2026. **Full standalone software plan; owner approval pending.**",
             "", "Qualification is complete. The primary product is `apps/desktop/`, the standalone Godot 3D application; shared engineering services remain usable without an HTTP server. `apps/web/` is frozen legacy (security and minimal compatibility only). Historical qualification receipts remain evidence, not a recurring development stage.",
             "", f"Tracking: [master issue #{plan['plan_issue']}](https://github.com/{plan['repository']}/issues/{plan['plan_issue']}), [PR #126](https://github.com/{plan['repository']}/pull/126). Proposed release marker: **`{plan['proposed_tag']}`**. This document does not approve merge, tagging, physical testing or physical acceptance.",
             "", "## Next action and execution rules", "",
             f"The next action is **{plan['authorization_task']}**, owner approval/merge/tag. After that approval is recorded, the first software task is **{plan['first_build_task']}**, reproducing the M21 cutoff failures. Do not restart qualification or start code execution from this planning PR.",
             "", "1. Read `AGENTS.md`, this task's section, the linked fundamentals and acceptance ledger. Use only the canonical local workspace in `WORKSPACE.md`.",
             "2. Pick the first unchecked builder task in document order whose prerequisites are checked. A pending owner/custodian/reviewer task requires its real receipt; a builder cannot self-approve it or invent data.",
             "3. Approval of the plan authorizes dependency-ordered Phase 0 software work. WP7–WP9 begin only at their listed tasks/prerequisites; no separate repeated qualification permission is implied. Phases 1–4 remain interfaces/registries only until their explicit entry gates.",
             "4. Implement the named normal desktop/headless behavior and its verification target. Each unchecked test path below is a **planned acceptance test to implement**, not a claim that the file already exists.",
             "5. Record the exact proof, update the canonical JSON, regenerate this document and sync every affected issue checklist. Commit after a completed milestone; merge only with the required final-head CI green.",
             "6. Checkbox completion is a scoped task result. Scientific status is tracked separately in `ACCEPTANCE_LEDGER.md`; code, a shader, optimization or synthetic sensor output never counts as physical validation.",
             "", "## Proof contract and blocked evidence", "",
             "Every future `docs/acceptance/TASK-ID.md` must contain the normal entry-point command/journey; frozen project/model/controller/dependency and input hashes; test/CI URL and exact head; expected condition and measured outcome; failures/exclusions and supported domain. Physical comparisons additionally require raw dataset identity/rights, matching actual hardware/geometry/firmware/conditions, calibrated instrument/clock uncertainty, predeclared criteria and independent whole-experiment partitions/review. Targets without numbers must be frozen before confirmatory reveal; unset criteria are INCONCLUSIVE. Mark unsourced parameters `UNVERIFIED_ESTIMATE`.",
             "", "A **software exit** allows the next software slice only after its specified functionality and verification pass and all physical gaps are disclosed. It does not close a **physical exit**. Independent measurements can remain blocked while dependency-ready software progresses; never check blocked evidence as complete. Final Phase 0 acceptance and future-phase entry require the explicit release/scientific gates. Work may use any suitable reference hardware, but every prediction/measurement comparison must match its own registered configuration.",
             "", "Canonical state: [`planning/tasks.json`](planning/tasks.json). `python scripts/check_master_plan.py --check` verifies rendering, numbering, dependencies, coverage and the recorded GitHub-sync digest. It does not authenticate approvals, instruments or physical truth. Edit the JSON, then run `python scripts/check_master_plan.py --render`; direct checkbox-only edits fail the check.",
             "", "## Work packages and slice mapping", "", "| WP | Issue | Scope | Slices |", "| --- | --- | --- | --- |"]
    for p in plan["work_packages"]:
        lines.append(f"| {p['number']} | [#{p['issue']}](https://github.com/{plan['repository']}/issues/{p['issue']}) | {p['title']} | {', '.join(p['slices'])} |")
    lines += ["", "Tasks with several WPs appear in each relevant issue but retain one canonical ID/status; do not count their copies as extra tasks.",
              "", "## Milestone checklists", ""]
    by_id = {t["id"]: t for t in plan["tasks"]}
    for section in plan["slices"]:
        for label, key in (("software", "software_exit"), ("physical", "physical_exit")):
            ident = section[key]
            lines.append(f"- [{'x' if by_id[ident]['status']=='done' else ' '}] Slice {section['stage']} {label} exit — **{ident}**")
    for p in plan["future_phases"]:
        lines.append(f"- [{'x' if by_id[p['entry']]['status']=='done' else ' '}] Phase {p['stage']} entry — **{p['entry']}**; prerequisite **{by_id[p['entry']]['dependencies'][0]}**")
        lines.append(f"- [{'x' if by_id[p['exit']]['status']=='done' else ' '}] Phase {p['stage']} exit — **{p['exit']}**")
    lines += ["", "## Legacy M21–M30 acceptance crosswalk", "", "| Major gate | Required task/evidence anchors | Current status |", "| --- | --- | --- |"]
    for gate in plan["legacy_gates"]:
        lines.append(f"| {gate['id']} — {gate['title']} | {', '.join(gate['tasks'])} | OPEN; see scientific ledger |")
    for section in [*plan["slices"], *plan["future_phases"]]:
        stage = section["stage"]
        lines += ["", f"## {'Slice' if stage.startswith('0') else 'Phase'} {stage} — {section['title']}", ""]
        if not stage.startswith("0"):
            lines += [f"**Locked future implementation.** Entry: **{section['entry']}**; prerequisite **{by_id[section['entry']]['dependencies'][0]}**; exit **{section['exit']}**. Until entry approval, contracts and dataset registries only.", ""]
        for task in [t for t in plan["tasks"] if t["stage"] == stage]:
            ident = task["id"]
            packages = ", ".join("WP"+str(w) for w in task["work_packages"]) or "future phase"
            lines += [f'<a name="{ident.lower()}"></a>', f"- [{'x' if task['status']=='done' else ' '}] **{ident} — {task['title']}** ({packages}; actor: {task['actor']})",
                      f"  - Prerequisites: {', '.join(task['dependencies']) or 'none'}. Proof: [{task['proof_file']}]({local_link(task['proof_file'])}).",
                      f"  - Acceptance: {task['acceptance']}"]
            if task["planned_tests"]:
                lines.append("  - Planned verification: " + "; ".join("`pytest "+p+"`" for p in task["planned_tests"]) + "; required current-head CI.")
            if task["completion_evidence"]:
                lines.append("  - Recorded evidence: " + ", ".join(f"[{p}]({local_link(p)})" for p in task["completion_evidence"]) + ".")
            lines.append("")
    done = sum(t["status"] == "done" for t in plan["tasks"])
    lines += [f"Unique task count: **{len(plan['tasks'])}**; checked **{done}**, unchecked **{len(plan['tasks'])-done}**. These are planning tasks, not a count of physically validated milestones. All ten legacy major acceptance families and all twelve broad Phase 0 package issues remain open until their own actual exit evidence exists.", ""]
    return "\n".join(lines)


def issue_blocks(plan):
    mapping = {}
    for p in plan["work_packages"]:
        mapping[p["issue"]] = (f"WP{p['number']} — {p['title']}", [t for t in plan["tasks"] if p["number"] in t["work_packages"]])
    for phase in plan["future_phases"]:
        mapping[phase["issue"]] = (f"Phase {phase['stage']} — {phase['title']}", [t for t in plan["tasks"] if t["stage"] == phase["stage"]])
    mapping[plan["plan_issue"]] = ("Master execution checklist", plan["tasks"])
    result = {}
    for number, (title, tasks) in mapping.items():
        lines = [START, "## " + title, "", f"Generated from the [review plan](https://github.com/{plan['repository']}/blob/feature/foundation-spec-lock/docs/MASTER_PLAN.md) in [PR #126](https://github.com/{plan['repository']}/pull/126). After merge, use `docs/MASTER_PLAN.md` on main. Canonical state is `docs/planning/tasks.json`; repeated task IDs share one status.",
                 "", f"Qualification is complete. Owner merge/tag approval is **{plan['authorization_task']}**; the first implementation task afterward is **{plan['first_build_task']}**. This checklist confers no physical acceptance. Custodian/reviewer gates need real independent receipts.", ""]
        for t in tasks:
            lines.append(f"- [{'x' if t['status']=='done' else ' '}] **{t['id']}** — {t['title']} (deps: {', '.join(t['dependencies']) or 'none'}; {t['actor']}). Proof: `{t['proof_file']}`.")
        lines += ["", "For exact acceptance conditions and planned verification files, follow the matching numbered task in MASTER_PLAN. Keep unsupported/scientific status separate in ACCEPTANCE_LEDGER.", END]
        result[str(number)] = "\n".join(lines)
    return result


def check_sync(plan, root=ROOT):
    receipt = json.loads((root / SYNC).read_text(encoding="utf-8-sig"))
    if receipt["plan_sha256_lf"] != plan_digest(root):
        raise ValueError("GitHub checklist receipt belongs to a different plan")
    blocks = issue_blocks(plan)
    for number, block in blocks.items():
        if receipt["issues"].get(number, {}).get("checklist_sha256") != sha256(block.encode()).hexdigest():
            raise ValueError("Missing or stale GitHub checklist receipt: #" + number)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--issue-blocks", action="store_true")
    args = parser.parse_args()
    plan = load_plan()
    validate(plan, check_receipts=args.check)
    if args.issue_blocks:
        print(json.dumps(issue_blocks(plan), ensure_ascii=False))
        return
    expected = render(plan)
    if args.render:
        (ROOT / MASTER).write_bytes(expected.encode())
    if args.check:
        if (ROOT / MASTER).read_text(encoding="utf-8-sig") != expected:
            raise SystemExit("Master plan drift: edit canonical JSON and regenerate")
        check_sync(plan)
    print(f"Master plan verified: {len(plan['tasks'])} numbered tasks, 12 packages, 8 stages; next owner action {plan['authorization_task']}, first software task {plan['first_build_task']}")


if __name__ == "__main__":
    main()
