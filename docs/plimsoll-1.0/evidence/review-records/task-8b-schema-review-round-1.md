# Task 8B schema/loading review — round 1

Date: 2026-09-22  
Reviewed commit: `92019a7f45d8403f6c154932709d9e466a810c67`  
Base: `68f27c415905933730f5bab7232250a199ac738c`  
Scope: the three changed paths in `task-8-review-68f27c4-92019a7.diff` only.

## Verdicts

**Specification verdict: APPROVED.** All three Important findings and the one
Minor finding from round 0 are addressed within the schema/loading phase. The
fix preserves the single-ledger boundary, nullable descriptive facts, omitted
fuel ownership as unknown, and the later coordinator/application boundary.

**Code-quality verdict: APPROVED.** The validators now fail closed at the four
reviewed audit/provenance boundaries, the tests separate provenance failures
from ownership and value failures, and the documentation matches the enforced
shapes. I found no new breakage in the three-path fix.

The producer recorded 103 focused passing tests across project extensions,
loading, project I/O/store, canonical cases, and systems integration, with
changed-path hashes independently matched by the controller. Per the review
brief, I did not rerun those accepted suites or the full suite because the
filtered diff left no concrete unresolved doubt requiring a probe.

## Round-0 dispositions

### Important 1 — ADDRESSED: present fuel declarations require provenance

`tools/plimsoll/project_extensions.py:120-141` now calls `_metadata(...,
required=True)` for every present coal/oil binding. Missing, null, blank, empty
object, or non-boolean provenance is therefore blocking for owned fuel and for
explicit absence, while omitting a binding still represents unknown ownership.
`tools/plimsoll/tests/test_project_extensions.py:158-180` covers both declaration
forms, invalid provenance variants, valid string/object sources, both boolean
estimate values, and the omitted-binding case. The existing ownership-error
tests now carry valid provenance so each contract is tested independently.

### Important 2 — ADDRESSED: leaf boundaries cannot hide nested systems

`tools/plimsoll/project_extensions.py:144-175` distinguishes the current leaf
boundary from descent below that boundary. It still validates local facts and
walks potential child systems, while excluding the documented leaf payloads
`facts`, `mass_models`, `source`, and `fuel_bindings`. Any nested facts or new
boundary below a declared leaf produces a blocking diagnostic. Fact-bearing
leaf `weight_item_ids` are also checked as a unique array of existing ledger
IDs. `tools/plimsoll/tests/test_project_extensions.py:182-208` exercises all
three boundary keys across propulsion, weapons, and armour, including an
intermediate container and malformed/valid link shapes. Present/absent policy,
shared ownership, and accounting remain with `systems.summary`, as documented.

### Important 3 — ADDRESSED: previous acceptance mass is required

`tools/plimsoll/project_extensions.py:345-364` now validates
`previous_mass_t` with `nullable=False`, using the same finite, nonnegative,
non-boolean numeric policy as the stored replacement audit. Tests at
`tools/plimsoll/tests/test_project_extensions.py:112-138` cover missing, null,
boolean, negative, nonfinite, and explicit-zero cases. Freshness and comparison
against the recomputed selected condition correctly remain later application
responsibilities.

### Minor 1 — ADDRESSED: table hashes use strict SHA-256 syntax

`tools/plimsoll/project_extensions.py:81-83` supplies one strict lowercase
64-hex validator, used by resistance table identity and acceptance identities.
`tools/plimsoll/tests/test_project_extensions.py:210-219` covers a valid hash
and wrong text, case, alphabet, length, empty, null, and boolean values.
`docs/plimsoll-1.0/project-extensions.md:116-122` states the same contract.

## Findings

No Critical, Important, or Minor findings in the round-1 fix.

## Unverified later boundaries

This approval is only the schema/loading phase gate. It does not verify proposal
recomputation/application, selected-loading numerical coordination, geometry
content import, package imports, result export, batch/sweep CLI, seven-page
bindings, or whole-core regression. Those remain the explicitly later phases.
