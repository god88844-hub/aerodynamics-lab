"""Export/check the source-controlled WP1–WP3 schema and prospective policy lock."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from lab_contract import CONTRACTS, ROOT
from aeroforge_schemas.foundation import CAPABILITIES


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def generated():
    policy_path = ROOT / "docs/VALIDATION_TOLERANCES.md"
    policy = json.loads(re.search(r"```json\s*(.*?)\s*```", policy_path.read_text(encoding="utf-8"), re.S)[1])
    files = {name+".schema.json": encoded(model.model_json_schema()) for name,model in CONTRACTS.items()}
    files["capabilities.json"] = encoded(CAPABILITIES)
    files["validation-policy.json"] = encoded(policy)
    validators = ["packages/shared-schemas/aeroforge_schemas/"+name+".py" for name in ("foundation", "project", "cad")]
    validators += ["packages/desktop_worker/"+name+".py" for name in ("resources", "protocol")]
    validators += ["scripts/lab_contract.py"]
    files["lock.json"] = encoded({"contract_bundle": "wp1_wp3_1", "policy_status": policy["status"],
        "validation_policy_raw_sha256": sha256(policy_path.read_bytes()).hexdigest(),
        "validator_sources": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in validators},
        "files": {name: sha256(raw).hexdigest() for name,raw in sorted(files.items())},
        "owner_signoff": "pending", "semantics": "new semantic versions require new lock; never imply physical acceptance"})
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "docs/contracts/wp1-wp3-1"
    failures = []
    for name,raw in generated().items():
        path = folder / name
        if args.check:
            if not path.is_file() or path.read_bytes() != raw:
                failures.append(name)
        else:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    if failures:
        raise SystemExit("Contract lock differs: " + ", ".join(failures))
    print("WP1–WP3 schemas, capabilities and prospective policy lock match" if args.check else "Exported contract lock")


if __name__ == "__main__":
    main()
