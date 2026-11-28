"""Sync the GitHub issue checklists (issue BODIES) with the rendered
MASTER_PLAN blocks.

After docs/planning/tasks.json changes and MASTER_PLAN regeneration, this
updates each mapped issue body's rendered checklist block (between
AERODYNAMICS_MASTER_PLAN_START/END markers, preserving any surrounding
issue-specific framing) via `gh api`, then rewrites
docs/planning/github_sync.json with the fresh plan digest, checklist hashes,
task counts and timestamp.

Run:  python scripts/sync_issue_checklists.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_master_plan import (  # noqa: E402
    END,
    ROOT,
    START,
    issue_blocks,
    load_plan,
    plan_digest,
    render,
)

REPO_FULL = "god88844-hub/aerodynamics-lab"
SYNC = ROOT / "docs" / "planning" / "github_sync.json"


def gh_json(*args: str) -> Any:
    out = subprocess.run(["gh", "api", *args], capture_output=True, text=True,
                         check=True, encoding="utf-8")
    return json.loads(out.stdout)


def gh_set_body(number: int, body: str) -> None:
    subprocess.run(
        ["gh", "api", "-X", "PATCH", f"repos/{REPO_FULL}/issues/{number}",
         "-f", f"body={body}"],
        capture_output=True, text=True, check=True, encoding="utf-8")


def get_body(number: int) -> str:
    issue = gh_json(f"repos/{REPO_FULL}/issues/{number}")
    return issue.get("body") or ""


def replace_block(old_body: str, block: str) -> str:
    """Replace the text between START and END markers, keeping framing text.
    If no markers exist, the block becomes the entire body."""
    start_idx = old_body.find(START)
    end_idx = old_body.find(END)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        return block
    prefix = old_body[:start_idx]
    suffix = old_body[end_idx + len(END):]
    joined = prefix + block + suffix
    return joined


def main() -> int:
    plan = load_plan()
    blocks = issue_blocks(plan)
    old = json.loads(SYNC.read_text(encoding="utf-8-sig"))
    old_issues = old.get("issues", {})

    updated, unchanged = [], []
    issues: dict[str, dict] = {}
    for number, block in sorted(blocks.items(), key=lambda kv: int(kv[0])):
        key = str(number)
        body = get_body(number)
        new_body = replace_block(body, block)
        if body.strip() == new_body.strip():
            unchanged.append(number)
        else:
            gh_set_body(number, new_body)
            updated.append(number)
        issues[key] = {
            "url": f"https://github.com/{REPO_FULL}/issues/{number}",
            "checklist_sha256": hashlib.sha256(block.encode()).hexdigest(),
            "task_entries": len(_task_ids_for(plan, number)),
            "state": old_issues.get(key, {}).get("state", "open"),
        }

    receipt = {
        "checked_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") +
                       f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z",
        "plan_sha256_lf": plan_digest(),
        "unique_tasks": len(plan["tasks"]),
        "scope": old.get("scope", "prospective acceptance policy; all campaigns DEVELOPMENT"),
        "issues": issues,
    }
    SYNC.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"synced {len(blocks)} issue checklists; updated={len(updated)} "
          f"unchanged={len(unchanged)}; updated issues: {updated}")
    return 0


def _task_ids_for(plan, number: int | str) -> list[str]:
    mapping: dict[int, list[str]] = {}
    for p in plan["work_packages"]:
        mapping[p["issue"]] = [t["id"] for t in plan["tasks"]
                               if p["number"] in t["work_packages"]]
    for phase in plan["future_phases"]:
        mapping[phase["issue"]] = [t["id"] for t in plan["tasks"]
                                   if t["stage"] == phase["stage"]]
    mapping[plan["plan_issue"]] = [t["id"] for t in plan["tasks"]]
    return mapping[int(number)]


if __name__ == "__main__":
    raise SystemExit(main())
