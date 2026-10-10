# web/deploy — Plimsoll production packaging

Deployment-only files. Nothing here is imported by the calculation core, the FastAPI
service or the React app, and no file in `web/backend` or `web/frontend` is modified.

| File | Purpose |
|---|---|
| `Dockerfile` | Runtime image (python:3.12-slim, non-root uid 10001, `PYTHONPATH=/app/tools`). Build context is an extracted release, not a checkout. |
| `Dockerfile.dockerignore` | Keeps a manual `docker build` from a checkout small and secret-free. |
| `requirements-runtime.txt` | Locked runtime versions taken from the tested local environment; no dev extras. |
| `requirements-build.txt` | Pinned `setuptools` satisfying the `setuptools>=75` build requirement of `web/backend/pyproject.toml`. |
| `compose.yaml` | Compose v2 project `plimsoll`: `db` (postgres:16-alpine, persistent volume, no published port), one-shot `migrate`, `api` on `127.0.0.1:18000`, `worker`. One shared image. |
| `production.env.example` | Template for `/etc/plimsoll/production.env` (the only source of secrets). |
| `nginx/plimsoll.conf.template` | HTTPS vhost template; replaces one named old site, ACME on port 80, `/api/` → `127.0.0.1:18000`, gzip/MIME/cache rules for static files and 404 for missing real paths. Hash routes remain within `/`. |
| `nginx/rate-limit-zones.conf` | Optional `limit_req_zone` definitions (general 10r/s burst 20, bootstrap 1r/s burst 5). |
| `build_release.py` | Stdlib packager: allowlist archive + JSON manifest with git head, dirty flag and SHA-256 sums. |
| `tests/test_build_release.py` | Stdlib unit tests for the packager. |

Runbook, rollback, backup/restore, certificate renewal and disposable-PostgreSQL test
commands: [`docs/plimsoll-1.0/web-production-operations.md`](../../docs/plimsoll-1.0/web-production-operations.md).

## Release build

```powershell
& 'web/backend/.venv/Scripts/python.exe' -m unittest discover -s web/deploy/tests -v
& 'web/backend/.venv/Scripts/python.exe' web/deploy/build_release.py --output .superpowers/releases
```

The frontend is never built here; `web/frontend/dist/` must already exist. Archives land
in `.superpowers/releases/` (git-ignored). See the runbook for the production variant
that requires `--confirm-source-frozen` on a clean, committed worktree.
