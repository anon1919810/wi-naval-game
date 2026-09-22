# Task 8B schema/loading review — round 0

Date: 2026-09-22  
Reviewed commit: `68f27c415905933730f5bab7232250a199ac738c`  
Base: `ed26f7e8f2f6cd996d4cd4d0c411986b91bd0b62`  
Scope: the seven paths in `task-8-review-ed26f7e-68f27c4.diff` only.

## Verdicts

**Specification verdict: NEEDS CHANGES.** The phase correctly implements persistent opening knowledge, field-level override provenance, quoted/indexed diagnostic paths, and most optional typed inputs. It also states the later proposal-application/coordinator boundary honestly. Four validation gaps remain: three Important and one Minor. No Critical finding.

**Code-quality verdict: NEEDS CHANGES.** The implementation is compact, does not invoke numerical kernels, preserves input ownership, and reuses the canonical diagnostic shape. The new validator is generally straightforward, but two permissive helper choices turn required provenance or validation into warnings/skips, and the tests do not exercise those malformed-but-accepted shapes.

The recorded 99 targeted passes and three caught mutations are credible evidence for their stated cases. I did not rerun those suites or the full suite. I ran one focused public-validator probe for the concrete uncovered cases below; all four malformed payloads produced zero error diagnostics and were accepted. The first two shell attempts failed before validator execution because of import-path/quoting setup; the corrected probe used the declared Python executable with `-B` and the repository module path.

## Findings

### Important 1 — explicit fuel ownership/absence is accepted without provenance

`tools/plimsoll/project_extensions.py:115-136` validates a present fuel binding with `_metadata(binding, ..., required=False)` at line 125. Missing/blank source and null/missing estimate therefore produce only warnings. A payload such as:

```json
{"systems":{"propulsion":{"weight_item_ids":["i"],"fuel_bindings":{"coal":{"weight_item_ids":["i"]}}}}}
```

normalizes successfully. The same applies to an explicit-empty binding with `absent: true`.

This binding determines whether selected ledger mass is known fuel and whether an empty list becomes a known zero. Under the phase contract, a present calculable ownership/absence declaration requires nonempty source and boolean estimate; omission of the whole fuel binding is the representation for unknown ownership. Allowing a present unsourced binding would let the later endurance adapter turn unknown ownership into a selected subtotal or explicit zero while claiming only a nonblocking warning.

Require provenance for every present coal/oil binding and add positive/negative cases for linked ownership and declared absence. This does not require a physical default or a new endurance calculation.

### Important 2 — a parent boundary key can bypass validation of nested system facts

`tools/plimsoll/project_extensions.py:139-159` stops recursion at line 149 whenever the current object contains `weight_item_ids`, `status`, `mass_models`, or `facts`. It validates local `facts`, if present, but does not reject or inspect child system objects before returning. Consequently this malformed object normalizes without an error:

```json
{
  "systems": {
    "weapons": {
      "status": "present",
      "main": {
        "weight_item_ids": ["i"],
        "facts": {"calibre_m": {"value": true, "source": "s", "estimate": false}}
      }
    }
  }
}
```

The boolean calibre is rejected when `main` is reached normally, but the parent `status` suppresses traversal. More generally, a boundary-bearing object can silently hide any nested `facts`. That contradicts this phase's claim that optional typed weapon/armour/propulsion facts are validated and leaves later adapters exposed to malformed data.

Define and enforce leaf/container structure: either reject nested system objects below a declared leaf boundary, or continue validating recognized descendants while excluding only known leaf payloads such as `facts` and `mass_models`. Add a regression for a boundary-bearing parent with a malformed child fact. While touching this boundary, validate any fact leaf's declared `weight_item_ids` shape/existence or explicitly document that `systems.summary` is the sole referential validator; the current `item_ids` argument is otherwise unused for those links.

### Important 3 — stored acceptance can omit its documented previous mass

`tools/plimsoll/project_extensions.py:325-359` describes an audited replacement record. `new_mass_t` is required at line 347, but `previous_mass_t` is passed to `_value` with the default `nullable=True` at line 346. Missing or null previous mass therefore emits only a warning and the project normalizes successfully.

The binding brief and `docs/plimsoll-1.0/project-extensions.md:130-145` say the record contains old/new mass so the accepted change remains reviewable after the selected-condition override replaces the prior effective value. Freshness and authorization correctly remain later responsibilities, but missing audit data is not a freshness question. Once saved, the originating selected mass may no longer be reconstructible from the current project.

Require a finite nonnegative `previous_mass_t` in a present acceptance record and add missing/null/bool cases. Keep the later application API responsible for verifying that value against the recomputed current proposal/application state.

### Minor 1 — `table_sha256` accepts arbitrary nonempty text

`tools/plimsoll/project_extensions.py:238-240` validates `table_id` and `table_sha256` identically as generic text. A strict Taylor scenario with `"table_sha256":"not-a-sha"` normalizes successfully. The field is specifically a source-table identity hash, and the same module already requires lowercase 64-character SHA-256 syntax for acceptance identities at lines 342-345.

Validate `table_sha256` as lowercase 64-character hexadecimal (or rename/document it as an opaque identifier if that is the intended contract) and add a negative case. This is Minor because the later coordinator can still refuse a mismatch, but accepting a value that cannot be a SHA weakens the schema's trace identity.

## Requirements that are satisfied in this phase

- `opening_definition` inference distinguishes absent, marker-free empty, explicit supplied-empty, and nonempty supplied openings; it persists through normalization/store/loading identity and reports ambiguity.
- Override metadata is a sibling of numeric overrides, is tied to an existing item/field, retains tri-state provenance, clears/replaces only the overridden field's uncertainty, preserves base coordinate attribution, and does not mutate base/other conditions.
- The uncertainty diagnostic now uses the actual condition array index and a JSON-quoted item key.
- Numeric bool/nonfinite guards, explicit method/attitude policy, QPC bounds/grid ordering, appendage/thruster shapes, historical condition/speed checks, and endurance fuel structure are covered for the direct shapes tested.
- Stored acceptance is explicitly documented as audit data rather than proof of freshness; the future API must recompute request/project/proposal identity.
- No coordinator, importer, exporter, package, CLI, UI, service, or numerical-completion claim is made by this commit.

## Unverified later boundaries

These are not findings against this phase: proposal recomputation/application; coordinator conversion of unknown/ambiguous openings to `None`; selected-loading systems/endurance/resistance/flooding adapters; geometry-content import; package import cleanup; calculation JSON/CSV; batch/sweep CLI; delivered seven-page bindings; performance/full-regression evidence. Task 6 flooding fixes and review also remain an independent gate.

## Focused probe evidence

The corrected read-only probe called `project_io.validate_project` on four minimal projects and printed error paths. Results:

```text
fuel_without_provenance: []
nested_fact_bypass: []
acceptance_without_previous: []
malformed_table_sha: []
```

No files were written or modified by the probe.
