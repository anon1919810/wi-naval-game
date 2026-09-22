# Task 8B coordinator checkpoint — frozen, incomplete acceptance

2026-09-22. Stopped at the user's request to finish promptly with project report and handoff. Current repository HEAD: `4bec0818b5fccda5dc060e18425bc9762dc13a19`. This phase began from `3dd85fbcc6e3f77336aa748151b4e3aee21bca5d`; other owners' commits advanced HEAD. All 19 paths below are now stable and frozen, but the new coordinator is **uncommitted work in progress, not independently reviewed or release accepted**. No staging, commit, full-suite run, new subagents or extra feature work was performed during checkpoint recovery.

## Implemented at this checkpoint

- Public `analysis.compute_project`, `materialize_reference_project`, `apply_mass_proposal`, and structured `AnalysisInputError`; ordinary package/direct imports. Stable request/result contract is in `docs/plimsoll-1.0/analysis-api.md`. Fifteen blocks live only under `result.stages`, with explicit status, validity axes, diagnostics, dependencies, provenance and identity.
- Immutable normalized selected-loading snapshot and request identity; dependencies run the reviewed geometry/equilibrium/GZ/grid/Bonjean/deck kernels. Reference-only geometry remains unavailable until explicit import/materialization. Diagnostics preserve native records and their stage/source paths.
- Actual selected plane and volume feed explicitly requested resistance. The longitudinal-trim proxy is always estimated, non-primary and `model_applicable=false`; no levelled historical/design plane is substituted. Explicit QPC and sensitivities produce power rows. Taylor may read only the declared bundled raw-byte-hash-verified table; caller/project file discovery is prohibited.
- Selected fuel bindings, native propulsion/endurance adapters, exact-condition historical comparisons, and opening-knowledge bridging into flooding. Native flooding result, stop information and native identity are retained rather than replaced with a synthetic timeline.
- Selected-condition mass-proposal acceptance recomputes the actual systems proposal and current normalized request identity without expensive geometry solves. It preserves base/other-condition ledger data and records per-field override provenance and prior mass.
- Canonical generator adds typed propulsion/fuel facts, explicitly estimated deck/study scenarios and conservative opening markers. Queen Mary now has explicit `holtrop-support-normal-engineering` and `holtrop-support-deep-engineering` scenarios derived from reviewed actual equilibrium and occupied station support, including geometry/loading derivation hashes, plane and volume. These are estimated station-support perpendicular proxies, not historical AP/FP. The full-envelope `holtrop-trim-study` remains an honestly unavailable Queen Mary example; no length tolerance was weakened. Generic uses `holtrop-trim-study`. Both have `taylor-trim-study` and `steady-cruise-study`. Existing anchor and generator determinism tests pass; no Task 6 generic flooding fixture was edited.
- The carried 8A minor is narrowly fixed: optional KG/reference-displacement estimate defaults are reported only when the associated quantity exists. Upfront present-field validation remains unchanged.

## Exact checkpoint verification

Working directory for every command: `C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`.
Interpreter invocation prefix: `$env:PYTHONIOENCODING='utf-8'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B` (actual Python 3.13.14).

| Command suffix | Result |
|---|---|
| `-m unittest discover -s tools/plimsoll/tests -p 'test_analysis*.py'` | 17 tests PASS, 13.469 s |
| `-m unittest discover -s tools/plimsoll/tests -p test_project_cases.py` | 9 tests PASS, 11.588 s |
| `-m unittest discover -s tools/plimsoll/tests -p test_geometry_analysis.py` | 31 tests PASS, 1.418 s |
| `git diff --check -- <the 19 paths listed below>` | Exit 0; no output |

These are 57 focused tests, not a full regression. The analysis cases exercise both normal/deep Queen Mary and generic conditions with actual nonzero trim, selected mass/volume identity, explicit Holtrop study power and selected fuel/endurance. Flooding coordinator tests cover persisted unknown/legacy-ambiguous/supplied markers at duration zero and a canceled generic request; they **do not establish a successful nonzero-duration Queen Mary timeline**.

During recovery the first geometry run after the narrow fix had 31 tests with one failure and one error: the older default-flags test expected a reference-mass flag while providing no reference mass, and the new absence test incorrectly expected a native KG trace row when no KG exists. The existing positive case now supplies a reference mass; the absence test checks null KG and no fabricated trace row. The final 31-test run above passed. Prior to compaction, the added absence regression was RED against the previous implementation (one failure). No remaining checkpoint test failures were suppressed.

Earlier RED/GREEN development evidence retained from the active phase: coordinator absent-module RED then initial 5 GREEN; adapter/replay RED then 8 GREEN; resistance 3 missing-helper errors then 3 GREEN; proposal 2 absent-API tests then 2 GREEN; grid/flooding RED exposed native result-status and cancellation/replay mismatches, then combined 16 GREEN. Canonical support scenarios initially failed because actual selected support length differs from the full hull envelope; explicit derived scenarios resolved this without changing kernels. The final 17-test run is the current evidence, not those earlier intermediate results.

## Pending work and known review concerns

1. Independent spec/quality review of these coordinator changes, shared full regression and CLI/export integration acceptance have **not** occurred. No release claim follows from the focused passes. Current default request can legitimately be partial when optional inputs are absent.
2. Queen Mary connected-flooding acceptance remains pending: the predeclared single-proxy duration 10 s, dt 1 s run must retain requested/accepted duration, accepted steps, stop/status, residual and conservation. A zero-duration run or zero accepted steps does not qualify. Performance triple repeats are also pending; no 300 s replay is implied.
3. The new derived resistance scenarios carry geometry/loading derivation hashes, but the coordinator does not yet enforce those stored hashes/condition ID against a later edited project. The explicit scenario selection and actual selected-length check remain active; an edited project should receive a dedicated stale-derivation check before this route is release accepted.
4. Proposal equality currently uses Python dictionary equality after JSON validation. Add a strict typed/canonical comparison and adversarial bool-versus-number probe; do not assume `True == 1` proves identical submitted provenance/model values. Existing stale-request/project and forged-value tests are narrower.
5. Request method-version identity currently records coordinator, geometry, stability and request versions. Audit completeness for all delegated method/software/source versions. Taylor raw source ID/hash is emitted, but full cross-stage version coverage is not yet acceptance-tested.
6. Historical adapter row-level unavailable results are retained, but aggregate stage completion when all comparisons are unavailable needs review. Similarly audit additional equilibrium liquid loads combined with flooding's own liquid bookkeeping; do not silently double count or discard an explicitly requested load.
7. Broaden focused negative acceptance for missing/mismatched Taylor resource, table holes/domain failures, heel/liquid exclusions, QPC override identity, duplicate diagnostic paths, native failed/model-limit outcomes, parameter materialization and effective source/estimate propagation. Some paths are implemented, but complete adversarial/mutation evidence is not yet present. Native propulsion compatibility traces require particular audit so unknown/estimated selected input provenance cannot become a false certainty.
8. Final 191-field/seven-page registry binding is not implemented here. Remaining native adapters/decisions include broadside kg/lb (systems currently exposes count), natural speed/form ratios, minimum-main-belt-length proxy, and complete deck segment endpoint/percentage bindings. L0 roll period and deck point clearances exist. Do not map draft/legacy dotted paths as if they were live outputs; root planned a separate bounded coverage phase.
9. Documentation currently fixes the stable public envelope and operations, but exhaustive native output-path/provenance inventory and all limitations need review/finalization. Current tests preserve accepted anchor assertions; an additional explicit full physical-field diff against the original canonical inputs was not run during this checkpoint.

No further fixes for these concerns were attempted after the stop request. Importer, CLI, exporters, package repair and field-registry ownership remain separate; this report makes no acceptance statement about their current working files. Scope remains calculation core/Python/CLI/JSON/CSV; UI, HTML, service/deployment, game export and Windows bundle remain deferred.

## Frozen SHA-256 manifest

Hashes are raw file bytes, collected after the final edits and targeted tests.

```text
249ff374d57926971911edc901812baa6b1dfa293a6697610730c460549588a5  tools/plimsoll/analysis.py
2d24f4ec656b3228efb71bf6bf937f37eab7c58b34869eae76e5de1eabec1553  tools/plimsoll/_analysis_request.py
2a6a6a4ed9bca93a71b8fbf21f8494e3ef8a4894ada7348d2b2f0374af5eeb47  tools/plimsoll/_analysis_bindings.py
305117ee7790a4a2c51a9da19e14460679e92dc60b0e6e1f2759308311e5d3b9  tools/plimsoll/_analysis_resistance.py
58cd5d44a7d340021f6a03c7f49ee9593204a3e486d013392799b34298676e99  tools/plimsoll/_analysis_proposals.py
0f9ed68372706545884f0c1019c75c421f4389a47826817ee3f706fdba2283dd  tools/plimsoll/tests/test_analysis.py
6797198aee469052803cb59fd8c9831d9555d5b12f208ac37bca6ab3879b3556  tools/plimsoll/tests/test_analysis_cases.py
8a0563f81d7aed1dbfb69931e5aec615ecf19922ad17d15be577379381a2f2c3  tools/plimsoll/tests/test_analysis_flooding.py
7cf5dddbcfda8efeada72c1d9b7062b7224813a408f607364db36658be6e2328  tools/plimsoll/tests/test_analysis_proposals.py
e44551e8728aef0685729cc23f31ff43ce4817610860fa1b292649f0572b7776  tools/plimsoll/tests/test_analysis_resistance.py
570be1a45a1badcb9091320fd3dcebfdaed64b9da0c74d5d774b13cad6ee31d6  docs/plimsoll-1.0/analysis-api.md
47ca813ef0531d027681a2c6410a41c64e0789bd1a058226a0b76b25dae7259b  tools/plimsoll/geometry_analysis.py
f8fb66c9e93c7387be8e16e231ff1be0f148cff56ad0c5e2bfbaee9c633a9d36  tools/plimsoll/tests/test_geometry_analysis.py
ad1c334087de80f498a3fc99aee373f4f9b6607c0c29e66631ff605c94464a80  docs/plimsoll-1.0/geometry-analysis-api.md
5c0d120cc5160a47b21ea5f0f36c548c7967156e6b98e5cc960e7531354b14bb  tools/plimsoll/tools/gen_project_cases.py
21002213a7705afb811b1305d9e78e35c3cf6f1f1ea618d5ce3a0188f7ce0524  tools/plimsoll/tests/test_project_cases.py
24d5dfd5029c18e15581e7e3d1935a689a5b77fc7d2cd771871a7f36a2caccaf  tools/plimsoll/cases/projects/analytic_box.project.json
220b5268fdfbd96e40fb268c3f47124858146a6ff4386bcea4f23b4f8a4f5bef  tools/plimsoll/cases/projects/generic_steamer.project.json
31c8d35706b9b6f21bced6bb206251523628aaae7e8ff93c6d20de9061645d51  tools/plimsoll/cases/projects/queen_mary_1913.project.json
```
