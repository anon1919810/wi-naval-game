# Task 8A independent review — round 0

Review target: `df9e835..1a482a1912520424ecdac804e850943820857cd4`

Scope: the eight persistence/geometry paths named in
`task-8a-review-brief.md`. Coordinator, exports, CLI, field registry, UI,
Task 6 production, and other integrated commits are outside this review.

## Verdicts

**Specification verdict: NEEDS CHANGES.** The persistence implementation meets
the released phase contract by inspection, including canonical normalization,
explicit legacy migration, literal reference preservation, same-directory owned
temporary replacement, and failure-before-replace behavior. The selected-plane
geometry follows the declared p/q/d plane, uses occupied intervals, keeps
inclined quantities separate from upright empirical eligibility, and labels the
station-girth surface approximation. The predeclared box, triangle, datum,
refinement, and loaded-solver evidence is consistent with the implementation.

Two input/provenance behaviors do not meet the binding requirement that malformed
numeric/provenance input be rejected and unknown provenance remain explicit.
They are observable before any later coordinator exists, so they belong to this
phase rather than a later integration gate.

**Code-quality verdict: NEEDS CHANGES.** The modules are small, cohesive, avoid
new solver duplication, copy caller-owned data, and document numerical limits
well. The main quality issue is validation after early returns: the same public
request is interpreted differently according to physical state, allowing invalid
fields to survive as ordinary `unavailable`/`model_limit` results. Diagnostic
routing also has one incorrect default path. I found no Critical issue.

## Findings

### Important

1. **Malformed provenance, estimate, datum, and deck values bypass validation on
   early-return paths.**

   - `tools/plimsoll/geometry_analysis.py:86-90` returns an L0 `unavailable`
     result before validating estimate flags and `sources` at lines 108-117.
   - `tools/plimsoll/geometry_analysis.py:101-107` likewise returns
     `model_limit` before those validations.
   - `tools/plimsoll/geometry_analysis.py:442-454` validates the deck and keel
     only by calling `deck_clearance` for a converged sample. If every supplied
     equilibrium failed, a non-null malformed deck and a nonfinite keel datum
     are accepted as an ordinary unavailable event series.

   This makes request validity depend on model outcome. For example, an
   infeasible L0 shape with `kg_is_estimate="invalid"` and `sources=[]` returns
   `status="model_limit"`; an event request with `source=None`, a string estimate,
   a NaN deck ordinate, a NaN keel datum, and one failed equilibrium returns an
   unavailable row. These are malformed inputs under the public contract, not
   unknown physical results. Downstream code can therefore persist or export a
   apparently structured result without learning that provenance or numeric
   input was invalid.

   Validate all fields that are present before missing/model-state early returns.
   `deck=None` may retain its documented unknown result, but a supplied deck and
   keel datum need validation even when no sample converged.

2. **An empty source map is treated as complete provenance rather than unknown.**

   At `tools/plimsoll/geometry_analysis.py:114-131`, only `sources is None`
   produces `l0.sources_unknown`. An explicit or normalized empty mapping uses
   the same no-source fallback inside the legacy calculator but emits no unknown
   provenance diagnostic. Reference displacement then carries `source=None` at
   lines 138-140 without a corresponding missing-source diagnostic. This is a
   common input shape because canonical data uses objects for source maps.

   The result therefore distinguishes null from `{}` syntactically while giving
   `{}` a stronger epistemic meaning than its contents support. The L0 contract
   requires actual input/default/reference provenance and explicit unknowns.
   Treat an empty map as supplying no provenance, and diagnose missing provenance
   for any direct input whose source dependency is absent. Preserve the literal
   input map in `inputs`; this does not require inventing a source.

### Minor

1. **The L0 shape-limit diagnostic is routed to the geometry path.**

   `tools/plimsoll/geometry_analysis.py:104-107` calls `_diagnostic` without a
   path, so the default at line 22 assigns `$.geometry`. The fields named by this
   diagnostic are under `$.hull`. A UI or export grouping diagnostics by JSON
   path will direct the user to the wrong object. Use `$.hull` or emit field-level
   diagnostics for the dimensions/coefficients that violate the limit.

2. **Defaulted estimate-state assumptions are visible only indirectly.**

   `tools/plimsoll/geometry_analysis.py:108-113` changes absent/null estimate
   flags to `True` in `effective_inputs`, but those defaults are absent from the
   `assumptions` list and have no diagnostic. This conflicts with the API
   documentation's statement that every used default is listed. The conservative
   estimate choice is reasonable; it should be serialized as an explicit
   assumption just like Cwp, roll gyration, and density.

3. **Temporary-file cleanup can mask the primary persistence failure.**

   In `tools/plimsoll/project_store.py:53-66`, an `unlink` error raised by the
   `finally` block replaces an earlier write/fsync/replace exception. The previous
   destination remains intact, but callers lose the reason the save failed and
   the owned temporary file may remain. Preserve the primary exception when
   cleanup also fails, while still limiting cleanup to the single owned path.

## Focused probe

I did not rerun the accepted persistence, geometry, stability, or L0 suites.
Code reading exposed finding 1, so I ran one direct focused probe with the
specified interpreter:

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='tools/plimsoll'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -c "import geometry_analysis as g; bad_l0={ 'lwl_m':20,'beam_m':6,'draught_m':2,'block_coeff':.9,'waterplane_coeff':.8,'kg_is_estimate':'invalid','sources':[] }; bad_deck={ 'source':None,'estimate':'invalid','points':[{'id':'p','x_m':0,'y_m':0,'z_m':float('nan')}] }; failed=[{'angle_deg':0,'equilibrium':{'converged':False}}]; print('L0',g.parameterized_hydrostatics(bad_l0)['status']); print('DECK',g.deck_immersion_events(bad_deck,failed,keel_offset_m=float('nan'))['rows'][0]['status'])"
```

Observed exit 0:

```text
L0 model_limit
DECK unavailable
```

This probe did not write production, tests, index, checkout, or branch state.

## Confirmed behavior and quality notes

- `project_store.save` normalizes/serializes/encodes before creating a temporary
  file, writes only a uniquely owned same-directory path, fsyncs before replace,
  and never scans sibling files. `load` performs no sibling discovery or geometry
  materialization. The explicit resolver preserves the project-relative base and
  permits a missing target.
- The geometry adapter reuses the existing validated stationed-hull preparation
  and clipping kernels. The interval extraction preserves concave gaps and the
  old half-width behavior.
- Selected-plane volume and centres come from the same p/q/d clipping as the
  loaded solver. Waterplane area/moments use the declared in-plane transform and
  analytical x-weighted integration. Upright derivative quantities are withheld
  for inclined planes and coincident boundary edges.
- Reference materialization requires all six shape/depth values, explicit keel,
  source, and estimate attribution; the generated geometry is always marked
  estimated and contains its method, assumptions, resolution, and content hash.
- Bonjean/hydrostatic grids are caller-supplied, finite, bounded, and retain
  contact/out-of-envelope rows. Deck event output does not fabricate a refined
  root or safety limit.

## Unverified later integration boundaries

- The immutable coordinator snapshot, request/result fingerprints, calculator
  composition, diagnostic routing across stages, and no-last-good-result behavior
  are later Task 8 phases and are not established here.
- External geometry reference content is not imported or materialized by this
  phase. Later integration must preserve selected content provenance/hash and
  must return unavailable for missing or invalid content rather than fabricate a
  hull.
- Canonical persistence currently normalizes absent openings to `[]`; that loses
  the raw distinction between unknown and explicitly supplied none across
  save/reload. The controller assigned a validated persistent knowledge/origin
  marker and end-to-end null/empty migration tests to Task 8B. This review does
  not assume that gap is already closed.
- Coordinator handling of slight loaded trim for resistance, empirical
  eligibility, selected loading provenance, and geometry/reference assumptions
  remains unverified.
- Package exports/import cleanup, CSV/JSON/HTML exports, real batch/sweep CLI,
  field registry, application/UI behavior, and the game contract remain explicit
  later requirements. Their absence is not a Task 8A defect.
- No shared full suite was rerun in this review, as directed. The accepted
  17-persistence, 25-geometry, 36-stability, 28-L0, mutation, and refinement
  evidence remains producer evidence rather than new reviewer execution.

