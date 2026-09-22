### Spec Compliance

- ❌ Issues found: the numerical implementation substantially matches Task 4, but first-immersion opening attribution can be wrong (`tools/plimsoll/stability.py:471`), and malformed nested input escapes the documented structured-failure contract (`tools/plimsoll/stability.py:171`, `:361`, `:392`). Details and reproductions below.
- ✅ Scope checked: the five-path diff implements the new equilibrium/curve API, adds behavioral tests, repairs the shared chord measure and labels legacy trim honestly. `damage.py` was an optional integration change, so its absence is not a missing requirement. The fifth curve options argument and explicit rejection of parameter-only geometry follow the controller's rulings (`docs/plimsoll-1.0/stability-api.md:7`, `:33`).
- ⚠️ Cannot verify from this diff: later coordinator hashing of effective options, named parameter materialization, supplied real deck-profile events, downstream UI/export behavior and historical ship validation. These are explicitly outside this task gate; they are not findings against Task 4. No real deck profile is established here (`docs/plimsoll-1.0/stability-api.md:93`, `:116`).

### Strengths

- `tools/plimsoll/stability.py:171`: the trial evaluator consistently uses one plane and the projected orthonormal axes, including the prescribed-heel longitudinal coupling term. Base KG and moving-liquid centroids are converted into the geometry datum before moments are combined. Requested liquid volume determines conserved mass; no additional FSC is applied.
- `tools/plimsoll/stability.py:171`: bounded iteration, residual scaling, slope-aware intercept support, explicit singular/exhaustion failures and a final residual reevaluation keep failed iterates from becoming reusable equilibrium results. Convergence, applicability, historical validation and safety have separate fields.
- `tools/plimsoll/tests/test_stability_loading.py:82`, `:118`, `:223`, `:319`: tests reconstruct physical arms independently and cover constrained coupling, liquid-induced initial slope and translated inclined datums. The archived four selected mutations each failed assertions with zero test errors, including the otherwise easy-to-miss p*q term and datum conversion.
- `tools/plimsoll/tests/test_stability_loading.py:177`, `:275`: non-box simultaneous and separate station/section refinements use analytical fixtures, rather than fitting expectations to production output. Primitive contact and disconnected-waterplane tests exercise the shared kernel change (`:52`, `:63`, `:70`).
- `tools/plimsoll/stability.py:392`: missing openings remain unknown; sampled maxima and endpoints are distinct from bracketed roots; roots after observed immersion do not become intact AVS. Provenance, loading identity and uncertainty survive in the equilibrium payloads.

### Issues

#### Critical (Must Fix)

- None found within the reviewed scope.

#### Important (Should Fix)

1. **First immersion reports the wrong opening when the controlling minimum changes inside a bracket.** `tools/plimsoll/stability.py:471` computes the correct root using the minimum clearance, but assigns `opening_id=clear[1]` from the later sampled angle instead of the solved immersion state. Focused reproduction with the existing 40×10×10 box, default load and angles `[0,20]`: opening `first=(0,5,4.5)` immerses at `atan(0.1)=5.7105931375°`; opening `later=(0,10,6)` immerses at `atan(0.2)=11.3099324740°`. Actual result was `{angle_deg: 5.71059312671423, kind: 'bracketed_immersion', opening_id: 'later'}`. The angle and named physical opening describe different events, which corrupts the event's audit trail and any opening-specific follow-up. Select the opening from `clearance(crossing[1])` when a root exists, and add a two-opening regression where their clearance ordering changes across the bracket.

2. **Malformed structured inputs escape the failure API as raw AttributeError.** `tools/plimsoll/stability.py:171`, `:361`, `:392` use `.get()` on nested `initial`, liquid `tank` and eventually the curve's state without validating their object types; the exception boundaries do not catch this error. The focused probe observed raw `AttributeError` for all three calls: `solve_loaded_equilibrium(box(), load(), {'initial': None})`; `solve_loaded_equilibrium(box(), load(), {'liquid_loads': [{'tank': None, 'volume_m3': 1, 'fluid_density_t_m3': 1}]})`; and `stability_curve(box(), None, [0,10])`. This contradicts the explicit failed-result behavior promised for invalid loading/options and lets ordinary JSON nulls abort callers instead of producing blocking diagnostics. Validate nested containers before member access, and use the same guarded state/fingerprint handling throughout curve construction. For invalid curve request structures, consistently use the documented ValueError boundary. Add focused malformed-container coverage; do not merely swallow all AttributeError, which could hide implementation defects.

#### Minor (Nice to Have)

- None additional.

### Checks and boundaries

- Read the supplied diff once, in three sequential chunks; no changed source file was separately reread, no Git command was run, and no subagent was dispatched.
- Read the binding brief, implementation report and two supplied analytical/coordinate designs. Checked the frozen regression manifest and archived mutation/numerical evidence directly; the manifest records 482 tests, zero failures/errors, unchanged before/after scope hashes. The report records 137.817 s test time. The full suite was not rerun.
- One focused runtime check for the named risk **opening identity changes during minimum-clearance root refinement**: executed the two-opening fixture above; confirmed wrong attribution while the angle remained correct.
- One focused runtime check for the named risk **nested null input bypasses explicit failure handling**: executed the three public-API malformed-input cases above; all raised AttributeError. Both checks shared one `python -B` invocation using the specified interpreter and UTF-8 environment, with no source mutation. No broader source crawl or package-wide tests were performed.
- Archived evidence was inspected as evidence, not regenerated. Scientific guarantees beyond the stated discretized-envelope model, global equilibrium branch uniqueness and unsampled intermediate events remain unproven; the implementation documents these limitations rather than claiming them.

### Assessment

**Task quality:** Needs fixes

**Reasoning:** The projected-axis equilibrium, liquid accounting and independent numerical tests are strong. Incorrect immersion attribution and raw exceptions for ordinary malformed JSON inputs are concrete API correctness defects that should be fixed before approving this task.
