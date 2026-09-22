# Task 6 independent fix review — round 1

Review target: `93218ff03bada4754b98435be94c3b559dfb87ab` →
`96555848fd8640d3e1700a2aed1c6f00a6d32af0`.

Scope: all six Task6 paths in `task-6-review-93218ff-9655584.diff` (five
changed paths, including the new generic fixture; damage-presets.json unchanged).
Read the full task brief, all four Important/two Minor round-0 findings,
the appended producer fix report and the complete filtered diff. I did not
produce Task6 implementation. My schema/coordinator work remained frozen and
was not included in this review.

**Specification verdict: APPROVED.** All six original findings are addressed.

**Code-quality verdict: APPROVED.** The fixes preserve solver ownership, signed
transfer conservation and accepted-state ownership. The changed control flow,
validation and failure envelopes are consistent with their documented contracts.
No new blocking issue or actionable new breakage was found in the fix diff.

## Per-finding disposition

| Original finding | Disposition | Evidence |
| --- | --- | --- |
| Important 1: equal heads incorrectly hit partial-aperture limit | ADDRESSED | `_flooding_kernel.py:247` classifies exact equal heads as zero flow before the finite-height gate at line 249. Closed/zero-area branches remain first; nonzero-head intersections still reach the existing model limit. `test_flooding.py:219` covers equal surfaces through the aperture. The old partial-aperture test moves the centre from 1 to 0.9 at line 214 so its source head is genuinely nonzero; this preserves, rather than weakens, the intended gate. |
| Important 2: four generic presets have no shipped project | ADDRESSED | `cases/projects/generic_flooding_box.project.json:3` supplies exactly generic-box-fixture, with the normal condition at line 82, explicit supplied/empty openings at lines 90–91, and self-contained rectangular polygons. Its 20×10×6 m envelope and 401.8 t base match the declared synthetic fixture; no historical hull is substituted. The unchanged preset project/condition IDs at damage-presets.json:7–8,29–30,52–53,74–75 now resolve. |
| Important 3: public validity omits separate numerical convergence | ADDRESSED | `flooding.py:470–478` gives pre-equilibrium invalid input a default null; initial failed equilibrium uses false at line 570; the late kernel rejection retains the already established true at line 598. The trajectory envelope at lines 738–744 is false on ultimately failed equilibrium and true for converged accepted states at other stops. Completion/applicability remain separate. `flooding-api.md:196` documents these trajectory semantics; tests at 333,382,390,401,411,509 cover completed/canceled/failed/event/invalid/model-limit cases. |
| Important 4: null/empty source silently accepted | ADDRESSED | Public `_source` at `flooding.py:72` requires a nonblank string or nonempty object and emits contextual blocking flooding.source_invalid. Scenario, sea, tanks, connections and supplied openings all route through it. Private `_flooding_kernel.py:37` enforces the same source shape on tank/sea/edge inputs. Estimate validation remains intact on the public boundary. The public source table at test_flooding.py:468 tests each required component; private tests begin at line 302. |
| Minor 1: preset tests prove labels, not usability | ADDRESSED | `test_flooding.py:554–582` builds the shipped project-ID registry, checks every referenced condition, deep-copies each scenario to duration zero and calls public simulate_flooding for all six presets. Assertions require scheduled completion and explicit convergence, retaining the Queen Mary proxy attribution checks. |
| Minor 2: late kernel validation loses known identity/context | ADDRESSED | `_invalid_result` now accepts copied context at `flooding.py:470–486`. The initial evaluate_flows exception branch at lines 590–598 passes the established input/project fingerprints, resolved loading, normalized scenario, opening origin and convergence. It still emits an invalid-input result with no fabricated accepted row. The injected boundary test at test_flooding.py:511 checks the actual returned context and diagnostic. |

Paths above are relative to `tools/plimsoll`, except flooding-api.md under
`docs/plimsoll-1.0`. Line numbers refer to reviewed HEAD9655584.

## New-breakage assessment

- The equal-head reordering changes only a rate already determined to be exact
  zero by the declared point-head model. It does not bypass a finite-aperture
  gate when differential head is nonzero or introduce a tolerance/calibration.
- The source check is an explicit schema completeness decision permitted by
  the original finding. It preserves caller metadata rather than inventing a
  replacement source; nonempty object content is retained as supplied, not
  claimed independently verified.
- New convergence is about equilibrium states of the reported trajectory.
  Canceled/model-limited trajectories can be numerically converged without being
  complete/applicable. Optional remaining-GZ output retains its own convergence
  and validity; callers must not replace those dimensions with the trajectory
  flag. The candidate retry/last-failure branches are consistent with the new
  envelope condition.
- The generic fixture does not alter existing case generation or preset
  equations. Its identity and explicit opening knowledge satisfy the newly
  validated schema without touching another agent's data.
- The only injected mock is the otherwise difficult late invariant boundary;
  the test inspects public result identity/context. Real preset wiring remains
  a public simulator call. No numerical oracle/tolerance was relaxed.

## Verification and boundaries

Read-only review plus
`git diff --check 93218ff 9655584 --` followed by the six scoped paths passed.
The controller independently matched all six producer hashes. The producer's
14 focused tests (12.812s) and 97 targeted tests (115.889s) are accepted prior
evidence, not represented as reviewer execution. No concrete uncovered doubt
required another numerical probe, so I did not rerun those tests or the full
suite. The controller's concurrent shared regression is a separate gate.

No production/test/index changes were made; only this review report was written.
Opening-definition persistence/coordinator bridging, unified request identity,
JSON/CSV and CLI bindings remain later integration obligations. This review
does not approve my own schema implementation or claim full calculation-core
completion. UI, deployment and packaging are outside the current user scope.
