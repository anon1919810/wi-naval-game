# Plimsoll Web Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a locally runnable, privately multi-user Plimsoll website with email-code login, editable persistent ship projects, background calculations, traceable results, and in-site reports.

**Architecture:** A React/TypeScript browser client talks to a thin FastAPI service. PostgreSQL stores users, challenges, sessions, immutable project revisions and calculation runs; a single database-claiming worker invokes the existing pure `plimsoll.analysis.compute_project` package. The API never reimplements ship calculations or resolves arbitrary project-supplied server paths.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, PostgreSQL, Alembic, React, TypeScript, Vite, Vitest, and the existing Plimsoll Python package. Production dependency versions must be locked before deployment; local tests may use SQLite for HTTP behavior but PostgreSQL is required for queue-claim and migration integration.

**Spec:** [`docs/superpowers/specs/2026-09-23-plimsoll-web-design.md`](../specs/2026-09-23-plimsoll-web-design.md)

## Global Constraints

- Preserve `analysis.compute_project(project, condition_id, options=None, *, cancel_check=None)` and `plimsoll-analysis-1`; keep its 15-stage envelopes, diagnostics, validity axes, provenance and fingerprints unchanged.
- Default to light theme; save the optional dark theme per user; first UI language is Chinese.
- Self-registration and login use email one-time codes only. No QQ login, public sharing, collaboration, Unity integration, Windows packaging or game-specific path discovery.
- Users may access only their own projects, revisions, runs, reports and exports; authenticate and authorize on every server route.
- A saved revision and normalized request are frozen before a run; never calculate an unsaved browser draft while presenting it as a saved run.
- Queen Mary is an engineering proxy, not a historically certified stability result. Unknown is not zero; `completed` is not an applicability or historical-validation verdict.
- The initial production process budget is one API instance and one bounded calculation worker on a 2-core/2-GB host. Actual limits and worker count are set from measurement, not an assumed throughput.
- Do not request or commit server, SMTP or database credentials. This plan stops at local product verification and a deployment runbook; live deployment requires separate domain, HTTPS and mail-delivery checks.
- Per the user's test-cost preference, write focused failing checks for each functional cluster and run that cluster once after its group of edits; run the calculation-core full regression only once at the final boundary unless a core change requires another run.

## Review Focus

1. A project ID or run ID belonging to another account must look inaccessible on **every** read, write, cancel and export route, even if the ID is known; Task 3 and Task 4 tests exercise both users.
2. A stale browser tab saving revision N after N+1 exists must get `409` with the current revision, without silently overwriting either copy; Task 3 tests this.
3. A 2.6-MB Queen Mary project must pass the input limit, while an oversized or `offsets_reference` project must fail before persistence or calculation; Task 3 and Task 4 tests this.
4. An expired/reused code, email-provider failure, or duplicate concurrent verification must never create two usable sessions or reveal whether an email existed; Task 2 tests this.
5. A worker crash, cancel request, or `partial`/`model_limit` result must remain visible with its real status and diagnostics; no green “safe” badge or fabricated report value; Task 4 and Task 6 tests this.

## File map and interfaces

| File | Responsibility |
| --- | --- |
| `web/backend/pyproject.toml`, `web/backend/alembic.ini`, `web/backend/alembic/` | Locked backend dependencies and schema migrations |
| `web/backend/plimsoll_web/config.py`, `db.py`, `models.py` | Environment config, SQLAlchemy session, PostgreSQL schema |
| `web/backend/plimsoll_web/auth.py`, `mailer.py` | Email challenge and session lifecycle; mail adapter |
| `web/backend/plimsoll_web/projects.py` | Owner-scoped project CRUD, canonical normalization and immutable revisions |
| `web/backend/plimsoll_web/runs.py`, `worker.py` | Request validation, queued runs, bounded worker, cancel and export |
| `web/backend/plimsoll_web/main.py` | FastAPI route assembly and request/response error mapping |
| `web/backend/tests/conftest.py`, `web/backend/tests/test_*.py` | Shared disposable client/mail/database fixtures and focused HTTP/worker tests; PostgreSQL integration test when available |
| `web/frontend/src/api.ts`, `types.ts` | Typed browser API for session, project and run contracts |
| `web/frontend/src/App.tsx`, `pages/`, `components/`, `styles/`, `__tests__/fixtures.ts` | Auth, library, workbench, provenance panel, report, theme and explicit browser-test fixtures |
| `web/frontend/package.json`, `vite.config.ts` | Browser build, focused tests and local API proxy |
| `docs/plimsoll-1.0/web-local-operations.md` | Local run, mail test adapter, migration, backup/restore and deployment readiness |

Route contract: `POST /api/auth/request-code`, `/api/auth/verify-code`, `/api/auth/logout`, `GET /api/me`, `PATCH /api/me/preferences`; `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/{project_id}`; `GET/POST /api/projects/{project_id}/runs`, `GET /api/runs/{run_id}`, `POST /api/runs/{run_id}/cancel`, `GET /api/runs/{run_id}/export?format=json|csv`. `GET /api/me` returns user ID, email, theme and the session's CSRF token after authentication. Authenticated writes require that token in `X-CSRF-Token` plus an accepted Origin; unauthenticated code endpoints require JSON content type and an accepted Origin. Owner mismatch returns `404`. `POST /api/projects` accepts `{template: null | "analytic_box" | "generic_steamer" | "queen_mary_1913", name}`; `PUT` accepts `{base_revision, project}` and returns `{project_id, revision, project}`. Run creation accepts `{revision, condition_id, options}`; run polling returns `{id, status, result, error}`. The result is the original `plimsoll-analysis-1` document.

---

### Task 1: Backend skeleton and persistent schema

**Files:** Create `web/backend/pyproject.toml`, `web/backend/plimsoll_web/{__init__,config,db,models,main}.py`, `web/backend/alembic.ini`, `web/backend/alembic/env.py`, `web/backend/alembic/versions/0001_initial.py`, `web/backend/tests/conftest.py`, `web/backend/tests/test_health.py`.

**Interfaces:** `create_app(settings: Settings) -> FastAPI`; `session_scope() -> Iterator[Session]`; tables `users`, `email_challenges`, `user_sessions`, `projects`, `project_revisions`, `calculation_runs`. `Settings.database_url` is mandatory outside tests; no credentials in defaults. `users.theme` is `light|dark`. Test fixtures in `conftest.py`: `engine` (disposable DB), `client` (unauthenticated), `outbox` (captured codes), `alice`/`bob` (authenticated TestClients with CSRF header), `project_id` (Alice-owned analytic box), `saved_document` (its canonical document), `worker_once` (one DB job), `run_id` (completed Alice run), `restart_client` (new app instance, same DB).

- [ ] **Step 1: Add a failing app and schema smoke check.**

```python
def test_health_returns_version(client):
    assert client.get('/api/health').json() == {'service': 'plimsoll-web', 'status': 'ok'}

def test_schema_has_owner_and_revision_columns(engine):
    from sqlalchemy import inspect
    names = set(inspect(engine).get_table_names())
    assert {'users', 'projects', 'project_revisions', 'calculation_runs'} <= names
  assert {'owner_id', 'current_revision'} <= {c['name'] for c in inspect(engine).get_columns('projects')}
```

- [ ] **Step 2: Implement settings, app factory and six tables.** Use UUID primary keys; unique normalized email; challenge hash/expiry/attempts; session token hash/CSRF token/expiry; project owner/current revision; immutable revision JSON and creation time; run owner/project/revision/request/status/result/error/timestamps. Enforce `(project_id, revision)` uniqueness and foreign keys. The app factory mounts `/api/health`; startup does **not** call `create_all` against production. Export `app = create_app(Settings.from_env())` for Uvicorn and inject explicit test settings in `conftest.py`.

```python
@app.get('/api/health')
def health() -> dict[str, str]:
    return {'service': 'plimsoll-web', 'status': 'ok'}

class ProjectRevision(Base):
    __tablename__ = 'project_revisions'
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id'), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    document: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, 'postgresql'), nullable=False)
```

- [ ] **Step 3: Run only the backend schema cluster**, including Alembic upgrade on a disposable PostgreSQL database if `TEST_DATABASE_URL` is configured, otherwise mark the PostgreSQL integration gate pending rather than claiming it passed. Commit the schema and health endpoint.

### Task 2: Email-code authentication and private sessions

**Files:** Create `web/backend/plimsoll_web/{auth,mailer}.py`, `web/backend/tests/test_auth.py`; modify `main.py`, `models.py`, migration only if Task 1 schema needs correction.

**Interfaces:** `request_code(email, requester_ip, db, mailer) -> None`; `verify_code(email, code, db) -> SessionToken`; `get_current_user(request, db) -> User`; `require_csrf(request, session) -> None`. SMTP adapter consumes environment configuration; test adapter captures mail in memory and is never the public production default.

- [ ] **Step 1: Write focused HTTP tests** for uniform `202` responses, six-digit code expiry/reuse, five failed attempts, request throttling, SMTP failure, secure cookie attributes, CSRF rejection and two simultaneous verification attempts.

```python
def test_code_is_single_use_and_session_is_private(client, outbox):
    assert client.post('/api/auth/request-code', json={'email': 'a@example.test'}).status_code == 202
    code = outbox.last_code_for('a@example.test')
    first = client.post('/api/auth/verify-code', json={'email': 'a@example.test', 'code': code})
    assert first.status_code == 200
    assert 'HttpOnly' in first.headers['set-cookie']
    assert client.post('/api/auth/verify-code', json={'email': 'a@example.test', 'code': code}).status_code == 400
```

- [ ] **Step 2: Implement auth with transactional challenge consumption.** Generate codes using `secrets.randbelow(1_000_000)`, store only HMAC digest with a server secret, and compare via `hmac.compare_digest`; create a user on first successful verification. Hash random session tokens at rest. Cookies are `HttpOnly`, `Secure` in nonlocal mode, `SameSite=Lax`, fixed lifetime. Require JSON content type and accepted Origin on auth endpoints, then a CSRF header on authenticated writes. Use database row locking for one-time challenge consumption; apply rate limits by normalized email and IP without revealing registration state. Mail delivery failures return the same `503` for both new and existing addresses, never a session. `PATCH /api/me/preferences` accepts only `{theme: 'light'|'dark'}` and persists it on the user row.

```python
@router.post('/api/auth/request-code', status_code=202)
def request_code_endpoint(body: CodeRequest, request: Request, db: Session = Depends(get_db)):
    auth.request_code(body.email, request.client.host, db, request.app.state.mailer)
    return {'message': '若该邮箱可接收邮件，验证码将很快送达'}
```

- [ ] **Step 3: Run the auth cluster once** with controlled clock and fake mail adapter; use PostgreSQL for the concurrent-consumption test. Commit after both session and CSRF checks pass.

### Task 3: Private project library and immutable revisions

**Files:** Create `web/backend/plimsoll_web/projects.py`, `web/backend/tests/test_projects.py`; modify `main.py`.

**Interfaces:** `create_project(owner_id, template, name, db) -> ProjectView`; `save_project(owner_id, project_id, base_revision, payload, db) -> ProjectView`; `get_project(owner_id, project_id, db) -> ProjectView`. The storage identifier is server-owned. Template JSON is read from the four known bundled files only; no caller-controlled path.

- [ ] **Step 1: Add ownership, size, invalid-input and conflict tests.** Use two authenticated clients. Save Queen Mary (2,552,972 bytes), reload exact canonical content; reject payloads over 8 MiB with `413`, and `geometry.kind == 'offsets_reference'` with `422`. Check no mutation when normalization fails. Exercise stale `base_revision` and all second-user routes.

```python
def test_stale_save_preserves_newer_revision(alice, project_id, saved_document):
    a = alice.put(f'/api/projects/{project_id}', json={'base_revision': 1, 'project': saved_document})
    b = alice.put(f'/api/projects/{project_id}', json={'base_revision': 1, 'project': saved_document})
    assert a.status_code == 200 and a.json()['revision'] == 2
    assert b.status_code == 409 and b.json()['current_revision'] == 2
```

- [ ] **Step 2: Implement an owner-filtered repository.** Deep-copy a chosen template, assign a new canonical project UUID, then call `plimsoll.project_io.normalize_project`. Use the same normalization for edits and reject external geometry references; keep inline offsets. In one transaction, compare `base_revision` while locking the project row, insert revision N+1, then update `current_revision`. List and get filter by `owner_id` in SQL; delete only an owned project and its dependent records according to the schema's cascade policy.

```python
def owned_project(db: Session, owner_id: UUID, project_id: UUID) -> Project:
    row = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == owner_id))
    if row is None:
        raise HTTPException(status_code=404, detail='project not found')
    return row
```

- [ ] **Step 3: Run the project cluster once**, including actual Queen Mary round-trip and cross-account tests. Commit CRUD and revision storage.

### Task 4: Bounded calculations, cancellation, results and export

**Files:** Create `web/backend/plimsoll_web/{runs,worker}.py`, `web/backend/tests/test_runs.py`, `web/backend/tests/test_worker_postgres.py`; modify `main.py` and `models.py` only if run state needs an additive migration.

**Interfaces:** `enqueue_run(owner_id, project_id, revision, condition_id, options, db) -> RunView`; `claim_next_run(db) -> CalculationRun | None`; `execute_run(run_id, db_factory, cancel_check) -> None`. Statuses: `queued`, `running`, `completed`, `partial`, `canceled`, `failed`. Export calls `plimsoll.exports.serialize_report` on the stored result, never recomputes.

- [ ] **Step 1: Add tests** for exact snapshot/request retention, another user's run ID, invalid condition/options diagnostics, duplicate queue claim, cancel before/while running, worker crash recovery, `partial` result visibility, and JSON/CSV identity equivalence. A run may be queued only for the current saved revision; the client cannot submit arbitrary project JSON to this route.

```python
def test_result_is_not_recomputed_for_export(alice, run_id, monkeypatch):
    monkeypatch.setattr('plimsoll.analysis.compute_project', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('recomputed')))
    response = alice.get(f'/api/runs/{run_id}/export?format=json')
    assert response.status_code == 200
    assert response.json()['schema'] == 'plimsoll-analysis-1'
```

- [ ] **Step 2: Implement the queue and worker.** At enqueue, read the owned immutable revision, validate `condition_id` and normalized options through `plimsoll._analysis_request.normalize`, and persist its canonical snapshot/request/fingerprint. Enforce an 8-MiB input limit, per-user active-run cap of 1, bounded worker wall time and a 32-MiB result limit. Claim with `SELECT ... FOR UPDATE SKIP LOCKED` on PostgreSQL and commit `running`. Run the core in one child process, monitoring its deadline and DB-backed cancel flag; pass cooperative cancellation through `cancel_check` and terminate the child if the deadline expires. Persist the exact result/status/diagnostics, or a failed-job error if no analysis document was returned. A lost process is marked failed by lease expiry and remains inspectable. Distinguish API `failed` from core `partial` and `canceled`; do not invent an analysis document for exceptions.

```python
def claim_next_run(db: Session) -> CalculationRun | None:
    stmt = (select(CalculationRun).where(CalculationRun.status == 'queued')
            .order_by(CalculationRun.created_at, CalculationRun.id)
            .with_for_update(skip_locked=True).limit(1))
    return db.scalar(stmt)
```

- [ ] **Step 3: Run the run/worker cluster once** on SQLite for HTTP behavior and disposable PostgreSQL for claim/concurrency/migration behavior. Measure Queen Mary normal and full-load requests; keep one worker unless measurements support more. Commit the worker and API.

### Task 5: Browser entry, project library and workbench editing

**Files:** Create `web/frontend/{package.json,package-lock.json,tsconfig.json,vite.config.ts,index.html}`, `web/frontend/src/{main.tsx,App.tsx,api.ts,types.ts}`, `web/frontend/src/pages/{Login,Library,Workbench}.tsx`, `web/frontend/src/components/{ProjectNav,FactField,StatusBadge}.tsx`, `web/frontend/src/styles/{tokens,layout}.css`, `web/frontend/src/__tests__/{fixtures.ts,workbench.test.tsx}`.

**Interfaces:** `api.requestCode`, `api.verifyCode`, `api.listProjects`, `api.getProject`, `api.saveProject`, `api.enqueueRun`, `api.setTheme`; browser types mirror API JSON. The canonical project document remains the server's source of truth; a local draft is explicit and a run button first saves or requires a saved revision. `fixtures.ts` exports `partialFixture` and `completedFixture`, both shaped as `plimsoll-analysis-1` with 15 stage envelopes.

- [ ] **Step 1: Write browser component tests** for empty library, login-code errors, loading/unsaved/saved/conflict states, 0 versus unknown, Queen Mary proxy label, and keyboard reachable form controls.

```tsx
it('does not turn unknown deck coverage into zero', () => {
  render(<FactField label="装甲甲板覆盖率" value={null} unit="%" status="unknown" />);
  expect(screen.getByText('未知')).toBeVisible();
  expect(screen.queryByText('0 %')).toBeNull();
});
```

- [ ] **Step 2: Build the responsive React shell** from the committed SVG concept: quiet project navigation, prominent vessel/condition context, saved-state indicator, provenance drawer and chapter forms. Use Vite's React TypeScript template and CSS custom properties from the spec; keep light as default and store dark preference through account settings. Forms edit a deep-cloned canonical document and send `base_revision`; show structured validation paths beside fields, not only a toast. A revision conflict offers reload and copy-unsaved-changes actions.

```tsx
const save = async () => {
  const saved = await api.saveProject(projectId, { base_revision: revision, project: draft });
  setRevision(saved.revision);
  setDraft(saved.project);
};
```

- [ ] **Step 3: Run browser component tests and `npm run build` once** after the group is integrated; manually open the local build in a browser at desktop and narrow widths. Commit the browser entry/workbench.

### Task 6: Results, provenance, comparison and in-site report

**Files:** Create `web/frontend/src/pages/{Run,Report}.tsx`, `web/frontend/src/components/{StageStatus,SourceInspector,ShipProfile,StabilityPlot}.tsx`, `web/frontend/src/__tests__/{results,report}.test.tsx`; modify `api.ts`, `types.ts`, `App.tsx`, styles, `__tests__/fixtures.ts`.

**Interfaces:** `api.getRun`, `api.listRuns`, `api.cancelRun`, `api.exportRun`; `Report` consumes a stored `plimsoll-analysis-1` result. Comparing runs is allowed only when unit/condition/method definitions are shown together. No figure comes from the concept SVG's illustrative numbers.

- [ ] **Step 1: Add state and report tests** with fixture results for `completed`, `partial`, `canceled`, `not_requested`, `unavailable`, `model_limit`, zero and null; verify Queen Mary proxy caveat and matching request fingerprints in JSON/CSV links. Check that the report never interprets `completed` as historical validation.

```tsx
it('keeps a partial calculation readable and names its failed stage', () => {
  render(<Report result={partialFixture} />);
  expect(screen.getByText('部分完成')).toBeVisible();
  expect(screen.getByText('超出方法适用范围')).toBeVisible();
  expect(screen.queryByText('历史验证通过')).toBeNull();
});
```

- [ ] **Step 2: Implement stage-led report and results** from the stored result, including origin, unit, estimate, method version, diagnostic path and request identity. Print CSS uses the light palette; charts have table/text alternatives. Queue polling stops on a terminal status and survives refresh. Compare two runs only after displaying condition, units, method version and request fingerprint side by side; incompatible values get “不可直接比较”.

```tsx
const requested = Object.entries(result.stages).filter(([, stage]) => stage.requested);
return requested.map(([name, stage]) => <StageStatus key={name} name={name} stage={stage} />);
```

- [ ] **Step 3: Run results/report tests and production build once**, then inspect light/dark/print output and keyboard focus in a browser. Commit results and report.

### Task 7: End-to-end acceptance and operations handoff

**Files:** Create `web/backend/tests/test_web_acceptance.py`, `docs/plimsoll-1.0/web-local-operations.md`; modify root `README.md`, `.gitignore` for `web/frontend/node_modules`, `web/frontend/dist`, `.venv`, local `.env`.

**Interfaces:** A local operator can run migrations, API, one worker, and browser app using documented commands; health and acceptance evidence has no live secrets. `restart_client` fixture rebuilds `create_app` against the existing test DB; `worker_once` executes exactly one queued job.

- [ ] **Step 1: Write an acceptance test** that creates two accounts, saves Queen Mary under account A, rejects B's read/edit/run/export, computes A's normal-load run, restarts the API against the same database, and confirms identical result fingerprint and report/export identity. Also exercise analytic box and generic steamer, stale revision, missing source, cancellation and provider outage as focused subcases.

```python
def test_two_user_saved_run_survives_restart(alice, bob, worker_once, restart_client):
    project_id = alice.post('/api/projects', json={'template': 'queen_mary_1913', 'name': 'Queen Mary'}).json()['project_id']
    run_id = alice.post(f'/api/projects/{project_id}/runs', json={
        'revision': 1, 'condition_id': 'normal-engineering', 'options': {'stages': ['loading']},
    }).json()['id']
    worker_once()
    before = alice.get(f'/api/runs/{run_id}').json()['result']['request_fingerprint']
    assert bob.get(f'/api/runs/{run_id}').status_code == 404
    assert restart_client(alice).get(f'/api/runs/{run_id}').json()['result']['request_fingerprint'] == before
```

- [ ] **Step 2: Document exact local commands**, environment variables without values, mail test mode, PostgreSQL migration, one-worker start (`python -m plimsoll_web.worker`), API start (`uvicorn plimsoll_web.main:app`), build/serve, backup and restore drill, log locations, size limits and how to inspect failed jobs. State plainly that public release needs a real domain, HTTPS, a working mail sender and a PostgreSQL integration pass. Do not put server IP or keys in committed config.

```powershell
$env:PYTHONPATH='tools'
py -3.12 -m unittest discover -s web/backend/tests -v
py -3.12 -B tools/plimsoll/run_all_tests.py
npm.cmd --prefix web/frontend test -- --run
npm.cmd --prefix web/frontend run build
```

- [ ] **Step 3: Run one final coordinated acceptance gate:** focused backend suite, PostgreSQL migration/worker test, browser suite/build, one full calculation-core regression, and a local browser walkthrough (login → create/save → compute → report → export → reopen). Save concise evidence in the handoff doc; fix failures and rerun only the affected cluster, repeating the full core suite only if core behavior changed. Commit the handoff.

## Self-review and boundaries

The seven tasks cover the spec's identity, project library, editor, calculation queue, result/report, provenance, theme and user privacy. Report PDF, QQ, public sharing, collaboration, deployment and game integration remain deliberately outside the approved spec. The PostgreSQL-only locking path is a release gate, not silently approximated by SQLite tests. Existing `.blend`, Unity and Python calculator algorithms stay untouched unless a concrete integration defect is reproduced. No credentials are needed to implement or review this local product.

Reference docs consulted for tool behavior: [FastAPI TestClient](https://fastapi.tiangolo.com/tutorial/testing/), [SQLAlchemy transaction scopes](https://docs.sqlalchemy.org/en/20/orm/session_basics.html), [Vite React TypeScript scaffolding](https://vite.dev/guide/), and [Python secrets](https://docs.python.org/3/library/secrets.html).
