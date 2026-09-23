# Core performance measurement protocol

Declared before the final coordinator/CLI benchmark. These are measurement
inputs and reporting rules, not passing results or a new physical calibration.
The current user scope is calculation-core delivery, so this protocol does not
require a server, browser, Windows bundle or installer.

## Environment and identity

Use the actual delivered source commit, its documented interpreter, and public
calculation interfaces. Capture exact Python version/executable/hash, OS/CPU/RAM,
project byte hashes, canonical input/request identities, effective options,
geometry station/vertex counts and named method versions. Existing hardware
preflight is context; unit-test elapsed time is not an application benchmark.

Record a cold process/import/startup measurement separately. For each workload,
retain at least three complete raw elapsed samples, median and maximum; use a
monotonic high-resolution clock. State whether input parsing and output
serialization are inside the measured interval. Record notable concurrent load
and never report only the fastest sample. No hardware-independent response-time
limit is inferred from a single machine.

## Workloads

1. Single condition: Queen Mary `normal-engineering`, loading + systems + free
   equilibrium + selected-plane hydrostatics, with actual default tolerances.
2. Batch: both canonical conditions of analytic box, generic steamer and Queen
   Mary, using the real batch route and the same requested stage set. Report
   per-case and total timing, failures and unavailable-stage reasons.
3. GZ: Queen Mary `normal-engineering`, requested angles 0 through 60 degrees
   in 5 degree increments. Retain all requested row statuses, model/downflooding
   boundaries and scaled residuals; a failed or inapplicable row is not silently
   discarded to improve elapsed time. Distinguish curve processing completion
   from availability of a physically valid full curve.
4. Flooding: the delivered `queen-mary-single-proxy` scenario with a clearly
   recorded performance-request duration of 10 seconds and step of 1 second,
   plus the delivered generic two-connected scenario shortened to 10 seconds
   at 0.5 second steps. The full 60-second generic stress request is outside
   the class-SPS core performance gate.
   Report scenario hash/source, initial volumes, requested and accepted duration,
   step count, retries, stop reason, conservation and equilibrium residuals.
   The shortened Queen Mary request measures a declared workload, not the
   original 300 second scenario's complete replay. Formula/refinement acceptance
   remains governed by flooding-validation-design.md, not this timing sample.

The generic preset must resolve to a delivered public fixture and condition;
a unit-test-only constructor does not establish a runnable user example.
The independent correctness run must also exercise a nonzero-duration Queen
Mary timeline, rather than treating the earlier zero-duration initialization as
full damage acceptance.

## Reporting and checks

Every measured result must retain its expected project/loading identity,
diagnostics, nonfinite rejection, actual solver residuals and numerical/method
applicability distinction. Results must be equivalent across repeated runs under
the declared deterministic options; don't reuse cached results as computation
timings. If a workload stops at a model boundary, disclose that boundary and
time/step count and do not rename it a scheduled-completion benchmark.

Preserve the script, literal commands and machine-readable raw evidence. A
CLI interruption/error-recovery check must confirm that a failed command does
not replace a valid saved project or masquerade as a successful result. The
later web phase will separately measure queueing, browser responsiveness and
owned-worker cancellation; none is claimed by this core benchmark.

## Measured results (partial, 2026-09-23)

Commit under test `0a84c51`; interpreter 3.13.14; 16 logical CPUs; 29.86 GB RAM;
monotonic `time.perf_counter_ns`; 3 samples per workload, median and maximum
reported (never only the fastest).

| workload | median | max | inside the interval |
|---|---|---|---|
| cold process + `import plimsoll.analysis` | 0.232 s | 0.249 s | interpreter start + import |
| single condition (QM `normal-engineering`, loading+systems+equilibrium+hydrostatics) | 2.989 s | 3.069 s | calculation only (no parse/serialize) |
| batch CLI, 6 case-condition pairs | 9.088 s | 9.401 s | whole subprocess: parse + calculate + serialize |
| per-case in-process, 18 runs (6 pairs × 3) | 24.5 s total | — | calculation only |
| GZ curve 0–60° step 5° (13 angles) | 19.379 s | 20.429 s | calculation only |
| flooding `queen-mary-single-proxy` requested 10 s / 1 s | 18.736 s | 19.874 s | calculation only |
| generic two-connected, requested 10 s / 0.5 s (post-fix) | 4.035 s | 4.055 s | calculation only |

The first six rows are pre-fix samples and remain representative, not an exact
final-source benchmark. The short generic row was measured after the numerical
hydraulic-equilibrium fix. The 60-second stress run was deliberately canceled;
it is not counted as a passing performance sample. The final full regression
contains 691 passing tests, including a bounded 60-second-request correctness
check that exits at hydraulic equilibrium without claiming elapsed time.

The original 60-second three-repeat generic stress measurement was stopped after
nearly 50 minutes. A bounded diagnostic traced the cost to flow-reversal step
halving near hydraulic equilibrium: at 20.33 s the two tanks held about 6 m³
each, while the remaining head difference was about 3×10⁻¹⁰ m. The method now
reports a separate tolerance-based hydraulic-equilibrium stop at a declared
1×10⁻⁸ m head difference, preserving conservation and actual accepted duration.
The class-SPS core benchmark uses 10 s for the generic fixture. Reproduce with:

```
PYTHONPATH=tools python -B docs/plimsoll-1.0/evidence/core_performance_benchmark.py
```

(the script writes its JSON after **every** workload, so an interruption
keeps everything measured so far). Raw evidence: `evidence/core-performance-benchmark.json`; batch
manifest and the first two batch summaries are kept under
`evidence/_bench_tmp/kept/` (the per-case result files were removed as scratch —
25 MB — and are reproducible from the manifest).

Nothing here is a hardware-independent response-time limit, and unit-test
elapsed time is not an application benchmark.
