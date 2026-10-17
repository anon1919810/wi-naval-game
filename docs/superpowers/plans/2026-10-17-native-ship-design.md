# Native Plimsoll Ship Design Implementation Plan

> For agentic workers: use opencode-delegate for bounded implementation; Codex owns design, review and independent acceptance. User approved autonomous execution of this unified minimum. Existing linked worktree is reused; no commits or deployment.

**Goal:** Plimsoll's ordinary project workflow natively covers the frozen SPS design capabilities with shared input, ledger, balance and report; remove the independent user mode.

**Architecture:** One ship_design declaration, pure source-method adapter, governed hull and mass-ledger projections. Existing analysis/project transactions remain authoritative for saved revisions; basic design has no CG/geometry prerequisite.

**Tech Stack:** existing Python, FastAPI and React/TypeScript, no new dependencies.

**Spec:** ../specs/2026-10-17-native-ship-design-design.md

## Global Constraints

- Preserve153 starting dirty files, historical SPS inventory/binary and current immutable runs; no git writes, deploy, package or model configuration changes.
- Defer enhancements; reuse accepted formula kernels and actual-source comparison evidence.
- OpenCode explicit free DeepSeek model only, no paid fallback. Independent Codex acceptance; failed worker output is not completion.
- Bounded central tests per unit; final actual UI/worker/export roundtrip once after shared code stabilizes.

## Review Focus

1. Same input must never have two active source declarations or two editable physical/source values.
2. Mass categories sum exactly once; use H0 hullWeightDisplayed for ledger, keep H1 only in source strength calculations.
3. Manual positions/masses and non-owned conditions survive generated estimates and source upgrades.
4. A late preview/project response cannot replace a newer draft/project; save/run blocked until all projections agree.
5. Old saved reports remain frozen; native declaration and file-export source view must retain exact source units.

## Task 1 — authoritative design and managed ledger

Files: new tools/plimsoll/ship_design.py, ship_design_mass.py, tests/test_ship_design.py, tests/test_ship_design_mass.py.

Interfaces:

- from_source(source,condition_id='design-normal')->native; to_source(native)->source-view.
- initialize(project,source=None), preview(project,command=None,design=None)->{project,design,preview,status,diagnostics}. Reply.design is source-view for reuse of existing field widgets, while reply.project.ship_design is the native authoritative declaration.
- compute(project,condition_id=None)->native result {schema,source_design,report,ledger,balance,...}; validate(project)->diagnostics with no normalization recursion.
- ship_design_mass.estimate(source_result)->role-to-metric-mass; reconcile(project,result,condition_id,bindings)->{project,bindings,summary,diagnostics}.
- bind_mass command {kind,role,item_ids,mode,mass_t?}; set_declared_mass {item_id,value}; explicit other role allowed for additional existing payload. New managed estimates only after all old non-managed items classified.
- Scoped estimate contract supersedes other-condition overrides: item.design_mass={owner:'ship_design',condition_id,mass_t,source}; preserve existing base masses and derived definitions. New items have explicit out-of-scope base0. Parent owns loading.py overlay after resolved old overrides, and systems.py suppression of superseded concept models. Native balance explicitly carries basis_condition_id.

- [x] Central failing workflow tests: fresh imported source closes one actual ledger with unknown coordinates; armour/gun edit changes same owned IDs; old manual data/other conditions untouched; duplicated owners/projection conflict refused; source input not mutated.
- [x] Implement bounded pure modules; source result unchanged numerically, native project coherent and no active legacy source section.
- [x] Acceptance: python -B -m pytest tools/plimsoll/tests/test_ship_design.py tools/plimsoll/tests/test_ship_design_mass.py -q (PYTHONPATH=./tools;./web/backend).

## Task 2 — project, server, analysis and saved exports

Files: tools/plimsoll/{project_extensions.py,_analysis_request.py,analysis.py,exports.py}; web/backend/plimsoll_web/{main.py,projects.py}, new ship_design.py adapter; new core/backend native integration tests.

Interfaces:

- New stage ship_design dependency[]; native documents default to this stage before legacy sps_compat/default selection. Native-only requests skip physical loading. Old documents/results retain previous behavior.
- Project extension calls pure validate and rejects simultaneous native/source declarations or shared-projection conflicts.
- Routes GET /api/design/catalog; POST /api/design/{initialize,preview,import-preview,from-migration}. Preview JSON={project,command?,design?}; initialize={project}; source import={project,filename,content_base64}; archive={project,migration}. Return core reply. 1MiB bounds and authentication/origin/CSRF unchanged.
- New blank web projects request template='ship_design' and initialize native design before canonical save. Old template=null API and existing templates stay intact.
- Stored native analysis data includes immutable report and source_design. TXT/RTF/SSR/sship prefer stored native stage, fall back to old saved sps_compat for old runs. JSON/CSV unchanged.

- [x] Tests: unauthenticated/CSRF refused, native preview pure, fresh blank setup runnable; native stage works without CG/geometry; old/new revision exports frozen/owned; legacy default unchanged.
- [x] Implement adapters and integration, no formula duplication or automatic migration of immutable saved revisions.
- [x] Acceptance: focused new core/backend native tests only; exclude rerunning prior222-field route.

Additional accepted entry-point work: Library sends native import requests. The 2.0/3.0 codec initializes a fresh native design directly, archives the exact original bytes, and reports canonical parameter count separately from positional record count. Omitted native flag retains the legacy raw API contract.

## Task 3 — ordinary workbench and unified edit queue

Files: frontend Workbench, ProjectNav, Sps3b3Editor, sps3b3Model, StageStatus, Sps3b3Readings, api/types/i18n; new ShipDesignEditor/summary/ledger components and tests as needed. Existing source widgets are reusable adapters, not separate product UI.

Contracts:

- New helper identifies ship_design and exposes temporary source-view to existing field queue. Native confirm calls /api/design/preview with the current project and last confirmed design; returned project supplies hull/weight projections, not TS calculations.
- Preserve serial/optimistic queue and generation guards. Apply returned full projection only when it matches confirmed design, merge local unrelated fields so edits to position/source are not lost. Native switch/import invalidates old requests.
- Remove standard/SPS modeChoice and mode toggle from Workbench. Always ProjectNav. Add freeboard chapter; native fields map hull/freeboard/guns/weapons/armour/propulsion/performance to the ordinary chapters. Remove nested source-page tabs in embedded presentation; expose only relevant driver/lock/default controls per chapter.
- Fresh empty web project already has native data. Existing old source project becomes a pending-save upgraded draft through native API once, preserving old run identity. Existing physical projects get initialize/import controls in ordinary overview, no new modal mode.
- Native main dimension and armament editors replace overlapping old input forms; retained advanced geometry, item position/source and damage functions are supplementary. Weight page uses the same actual weight rows plus binding controls; computed automatic masses not directly edited through old row fields.
- Native default run={stages:['ship_design']}. Optional additional physical checks appear as extra analysis tasks, never a data mode; no CG gate for ordinary native run.
- Native overview and chapters use latest preview or exact saved native run; no huge raw JSON as primary display. Full report/diagnostics/files remain ordinary saved-run actions.

- [x] Tests: ordinary chapters accessible with no mode button, import→edit across chapters→save coherent source+hull+ledger; queue race/replacement; manual binding action; legacy project preserved; native run options require no geometry/CG.
- [x] Implement native host and reuse widgets with adapter/embedded controls; keep prior legacy source editor callable only for backward API tests/old boundaries.
- [x] Acceptance: new native frontend tests; parent runs final TypeScript/build after integration. Additional builds were limited to actual UI defects, a test typing correction and an interrupted process; final build passed.

## Task 4 — report comparison and final acceptance

Files: frontend reportMetrics and report UI paths when needed; docs/plimsoll-1.0 native delivery/evidence; chat-owned acceptance harness.

- [x] Add native key metrics with explicit source method/units; never label empirical score as physical GM.
- [x] Independent new synthetic project and original .sship on the native route compare with frozen native source readings; one hull/gun/armour edit must propagate through parameters, SI projection, actual ledger, balance and report.
- [x] Browser ordinary create/import→chapters→ledger→save→run→report/compare→download→original reopen→reload, including no-CG and one manual/second-condition guard. After a temporary browser restart, JSON backup restoration was also exercised in a fresh workspace.
- [x] One relevant integration batch, targeted review corrections, final frontend build and current-source core quick; retain errors and scope boundaries, no historical giant matrix rerun.
- [x] Update current product status only after native workflow acceptance; original compatible parity record remains historical source-method evidence.
- [x] Clean owned temporary service/browser, preserve start snapshot, no commit/push/deploy.

## Accepted outcome

Accepted locally on 2026-10-17. See ../../plimsoll-1.0/native-ship-design-2026-10-17.md and ../../plimsoll-1.0/evidence/native-unification-2026-10-17.json. The original live event sequence matched the frozen native readings; downloaded files reopened through the original file codec and Windows RichTextBox. Enhancements are deferred beyond this minimum.
