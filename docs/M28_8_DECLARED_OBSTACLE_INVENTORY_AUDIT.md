# M28.8 — Fail-closed declared aircraft obstacle inventory

Provides `physics.structures.obstacle_inventory.audit_declared_obstacle_inventory`, a read-only wrapper over M28.7 rotor-versus-obstacle bounding sphere separation that **cannot silently omit any obstacle appearing in the declared target inventory**.

The operator must supply 1–128 unique expected obstacle IDs and the exact same set of explicitly enclosed obstacle spheres (frame, landing gear, payload, antennae, battery compartment, supports, etc.). Any omitted, unexpected or duplicated ID prevents analytical acceptance. Once inventory IDs exactly agree, check every rotor against every listed obstacle using full three-dimensional worst-case enclosing spheres and declared center/radius hard error bounds. Return per-pair reports and a deterministic SHA-256 digest of the declared inventory identity and source.

This is **only completeness relative to an operator-declared list**. A user could omit a real frame component from both the expected list and the supplied envelopes. The system does not independently authenticate installed hardware, geometry hard bounds, full-aircraft CAD, blade dynamics, real collision measurements or physical release eligibility. All these claims remain explicitly false regardless of an analytical pass.

Synthetic-only tests: `python -m pytest tests/physics/test_obstacle_inventory.py -q`. Actual installed geometry and independently verified obstacle inventories remain required.
