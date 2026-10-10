# Numerical convergence study implementation plan

> **For agentic workers:** Implement the checked tasks with `superpowers:executing-plans`. The user's execution method is OpenCode implementation with Codex review and acceptance. The user has already requested automatic execution and continuation; no additional approval gate or worker commit is required.

**Goal:** Produce a reproducible, offline study that separates hull discretization, GZ sampling and flooding time integration errors against independent analytic answers.

**Architecture:** A standalone study tool uses public Plimsoll functions, a small fixture module and independent math-only oracles. It writes JSON, CSV and Markdown evidence, retaining failed samples rather than dropping them. Existing runtime algorithms and public commands stay unchanged.

**Tech stack:** Python 3.12 and the standard library; existing pytest for acceptance.

**Spec:** `docs/plimsoll-1.0/geometry-analysis-validation.md`, `equilibrium-validation-design.md`, `flooding-validation-design.md`, and the bounded study specification below.

## Global constraints

- Work only in the current checkout; preserve other files and all frozen release contents.
- Add no dependencies, numerical algorithm changes, API/UI changes, live server operations or Git commits.
- Oracles import only the standard library and must never call Plimsoll to generate expected answers.
- All tolerances below are declared before this study is run. Report a failing tolerance; do not loosen it or alter an oracle to make a result pass.
- Numerical convergence tests the implemented model. It does not establish physical accuracy, statutory stability compliance, historical ship accuracy or SPS superiority.
- Outputs contain units, fixture provenance, method versions, source hashes, actual run status, time and refinement settings. JSON rejects non-finite numbers.

## Bounded study specification

1. **Geometry:** Use the existing sliced ellipsoid oracle in `evidence/coupled_ellipsoid_oracles.py`: semi-axes 20/5/5 m, centre z=5 m, p=.01, q=.1, d=4 m, rho=1.025 t/m³, KG=3 m, nonzero prescribed GZ=.15 m. Build section polygons by analytic ellipse sampling. Refine cosine-spaced longitudinal stations 41/81/161 at 128 section vertices, then section vertices 32/64/128 at 161 stations. Evaluate the specified plane directly and the free and prescribed heel public equilibrium solver. Retain volume, buoyancy centre, p/q/d/GZ, absolute/relative errors and scaled solver residuals. The fixed other axis introduces a discretization floor; observed order is evidence, not a guaranteed pure order. At the shared finest mesh require volume relative error <=1e-3, each buoyancy centre error <=.01 m, d error <=.01 m, p error <=1e-4 and prescribed GZ error <=.001 m. Every declared solved state must converge with scaled residual <=1e-6.
2. **GZ sampling:** Use a sealed, empty rectangular prism L=40 m, B=10 m, depth=10 m, draft=4 m, KG=3 m, rho=1.025, mass=1640 t, no openings/liquids, 21 stations. Sample 0..30 degrees inclusive with steps 5/2.5/1.25/.625 degrees. A new independent oracle derives `BM=B²/(12T)`, `GM=T/2+BM-KG`, `GZ=(GM+BM*tan(phi)²/2)*sin(phi)` from integrating h(y)=T+y*tan(phi); its exact area in radians is `GM*(1-cos(P)) + BM/2*(1/cos(P)+cos(P)-2)`. Check bounds `abs(tan(phi))*B/2 < min(T,depth-T)`. Every valid GZ sample must match within 1e-6 m. Trapezoidal area errors must decrease across the four levels and finest relative area error <=1e-4. Report area order, sample count, common-angle agreement, sampled maximum and endpoint separately. There is no AVS or unrestricted-angle validation in this range; no claim that a smaller step improves the solver at a fixed angle.
3. **Flooding:** Use the existing independent `flooding_oracles.py` coupled-heave answer: centred 20x10x6 m hull, base mass401.8 t at KG1, 4x2x4 m vented tank with initial volume8 m³, sea rho1.025, Cd.6, area.1 m², point z=.1 m, duration5 s. Refine dt .5/.25/.125/.0625/.03125 s, retaining completion/stop reason, accepted timeline steps, influx, final draft, conservation and max equilibrium residual. Influx and draft-change normalized errors must decrease; finest <=1%. Volume conservation error <=1e-9 m³, mass conservation <=4.1e-8 t, scaled equilibrium residual <=1e-6. Report observed time order, not an automatic claim of higher-order integration. Finite, completed, scheduled-completion states alone can pass.

## Review focus

1. Failed or model-limited samples must remain in every evidence format, fail acceptance and produce CLI exit1.
2. NaN/Infinity or absent required solver values must never be converted into a passing zero error.
3. Fixed-angle GZ accuracy and curve-area sampling convergence must be represented as different metrics.
4. Study results must not depend on current working directory or mutate the supplied fixtures.
5. Source identity must cover actual kernels, fixture builders, oracles and study code, without hashing the generated report into itself.

## Task 1: Independent fixtures and GZ oracle

**Files:** Create `tools/plimsoll/tools/convergence_fixtures.py`, `docs/plimsoll-1.0/evidence/wall_sided_box_oracle.py`; test in `tools/plimsoll/tests/test_convergence_study.py`.

**Interfaces:** Provide deterministic fresh fixture dictionaries for ellipsoid meshes, box loading and flooding cases; `wall_sided_box_oracle.oracle()` returns parameters/valid range/exact area and a math-only `gz_m(angle_deg)` returns the analytic lever.

- [ ] Write failing tests for analytic values at 0/30 degrees, bounds rejection, independently integrated area and fixture immutability.
- [ ] Run those tests and retain the failure evidence.
- [ ] Implement deterministic builders and the independently derived, bounded oracle. Do not import existing tests or change existing oracles.
- [ ] Run the focused tests; verify the oracle imports no Plimsoll modules.

## Task 2: Study runner and honest evidence

**Files:** Create `tools/plimsoll/tools/convergence_study.py`; extend `tools/plimsoll/tests/test_convergence_study.py`.

**Interfaces:** Expose `run_study(suite='all') -> dict`, writers for JSON/CSV/Markdown and `main(argv=None) -> int`. Support `--suite all|geometry|gz|flooding` and required `--output-dir PATH`. Default CLI runs the complete bounded study, no network or production writes. Output names: `convergence-study.json`, `convergence-study.csv`, `convergence-study.md`.

- [ ] Write failing tests for required metadata/error metrics, failed and non-finite sample retention, exit code, no partial pass, valid absolute path execution from another cwd and distinct GZ sampling metrics.
- [ ] Run the new tests and record the failures.
- [ ] Implement the three prescribed sequences and error/order calculations; use public APIs, preserve input hashes before/after, and capture failure statuses explicitly. Null/zero reference values need absolute error, with relative error unavailable when division is undefined. An observed order is unavailable for zero or invalid error pairs.
- [ ] Write complete evidence even when study acceptance fails; no threshold tuning. Bound invalid `--suite` and handle unwritable paths with a clear error. `--help` must not run studies or write output.
- [ ] Run the full prescribed study once and the related geometry/GZ/flooding test cluster.

## Task 3: Explain the findings and limitations

**Files:** Create `docs/plimsoll-1.0/numerical-convergence-study-2026-10-10.md`.

- [ ] Describe the reproducible command, formula derivation, predeclared limits, actual observed errors/orders and source identity. Use real runner output, never hand-authored numerical claims.
- [ ] Explain the fixed-axis geometry floor and the distinction between GZ solver error and curve quadrature error.
- [ ] Record external experimental/model-basin validation as pending. If a tolerance fails, report the failure and the next investigation rather than changing runtime code.
- [ ] Report changed files, exact commands/results and remaining limitations to Codex; do not commit or deploy.

## Acceptance commands (PowerShell from repository root)

```powershell
& web/backend/.venv/Scripts/python.exe -m pytest tools/plimsoll/tests/test_convergence_study.py tools/plimsoll/tests/test_stability_loading.py tools/plimsoll/tests/test_flooding.py -q
& web/backend/.venv/Scripts/python.exe tools/plimsoll/tools/convergence_study.py --output-dir C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/numerical-convergence-2026-10-10/opencode
git diff --check
```

Codex independently reads every new source and report, re-runs acceptance in a different output directory, checks the oracle derivations and verifies protected runtime hashes before accepting.

## Codex acceptance checkpoint

Completed 2026-10-10. OpenCode implemented the bounded files and addressed two
review rounds. Codex then corrected remaining reporting issues (unsupported
round-off attribution, the retained reason for a NaN direct buoyancy centre, and
maxima over incomplete flooding timelines, and input hash changes omitted from
suite acceptance), with reproduced failing tests before the fixes. Independent
commit review then tightened GZ applicability to boolean true, included separate
final states in all-state residual limits, preserved failed intermediate levels
in observed orders, and retained non-finite flag failures in strict JSON, again
with reproduced red tests before the fixes. Independent
final whole-core pytest: 895 passed, 594 subtests passed; study:
98/98; separate adversarial cases: 21/21. Thirteen study sources and all 100
frozen runtime files matched their recorded hashes. The verified JSON snapshot
and findings are retained in `docs/plimsoll-1.0/evidence/` and the linked study
document. The public runtime remains the separately verified `a863b0e` release.
