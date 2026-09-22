# Task 1 review — 684768b..5e06a01

Reviewer: /root/plimsoll_contract_review. Spec partially compliant; quality Needs fixes. No Critical or Minor findings.

Strengths: exact conversions and cross-dimension rejection; null/zero distinction; IDs/override checks; deepcopy; original migration retention, explicit unit conversion, no residual fill; deterministic fingerprints.

Important findings:

1. `tools/plimsoll/project_io.py:225`: `_validate_json_value` records non-string JSON keys but `_validate_hull` calls `_hull_numeric_key`, which calls `key.endswith`. Focused probe `hull={1:2}` raises AttributeError rather than returning `json.key_invalid`. Malformed inputs must produce diagnostics, not implementation exceptions.
2. `project_io.py:117`: normalization defaults missing weight-item `estimate` to False. This invents confirmed non-estimated provenance and hashes missing like explicit false. Preserve unknown/nullable with diagnostic. Geometry does not default False; migration defaults missing legacy item estimate True conservatively.
3. `project_io.py:310`: geometry payload validation checks only non-None. `reference={}`, `offsets=""`, `parameters=False` pass despite not being usable payloads. Validate meaningful container shape and required reference data.

Review used diff and one specific malformed-key probe; no full suite repeated.

## Controller rulings for fix round 1

- Implement all three findings. Fix base is current HEAD e5f2ee0 (only controller docs followed reviewed implementation 5e06a01); reviewer initial surface remains 684768b..5e06a01.
- `estimate` may explicitly be null for unknown; missing item estimate normalizes to null, declared booleans preserved. Unknown provenance diagnostic must survive normalize/validate and be different from explicit false in fingerprint. Keep legacy conservative assumptions disclosed rather than rewriting original payload.
- Geometry validation is structural here, not a second hull solver. For `offsets_reference`, require a reference object and non-empty string `path`. For `parameters`, require a non-empty parameter object; permit partial parameters to combine with hull fields, leaving complete domain validation to loader. For materialized `offsets`, document and require an object with a non-empty stations array; validate container shape, leaving hull physics to geometry loader. Reject wrong payload type, empty payload and mismatched kind/payload. Document supported kinds; unknown kinds may be rejected explicitly until a schema-preserving adapter is added. No filesystem existence scan.
- Add actual failing tests before fixes, then covering focused tests. Run broader tests only if source changes beyond new standalone modules warrant it. Append fix report; commit only task-owned files.
