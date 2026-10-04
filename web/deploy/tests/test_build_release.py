"""Stdlib unit tests for web/deploy/build_release.py.

Run from the repository root:
    & web/backend/.venv/Scripts/python.exe -m unittest discover -s web/deploy/tests -v
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

_DEPLOY_DIR = Path(__file__).resolve().parents[1]
_MODULE_PATH = _DEPLOY_DIR / "build_release.py"
_SPEC = importlib.util.spec_from_file_location("plimsoll_build_release", _MODULE_PATH)
build_release = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = build_release
_SPEC.loader.exec_module(build_release)

ReleaseError = build_release.ReleaseError

TRACKED = (
    "tools/plimsoll/hydrostatics.py",
    "tools/plimsoll/cases/templates/generic_cargo.json",
    "tools/plimsoll/tests/test_stability.py",
    "web/backend/alembic.ini",
    "web/backend/alembic/env.py",
    "web/backend/alembic/versions/6226f03d283f_initial_web_workspace_schema.py",
    "web/backend/pyproject.toml",
    "web/backend/plimsoll_web/__init__.py",
    "web/backend/plimsoll_web/asgi.py",
    "web/backend/plimsoll_web/worker.py",
    "web/backend/plimsoll_web/__pycache__/asgi.cpython-312.pyc",
    "web/backend/.pytest_cache/CACHEDIR.TAG",
    "web/backend/plimsoll_web.egg-info/PKG-INFO",
    "web/backend/.venv/Lib/site-packages/fastapi/__init__.py",
    "web/backend/.env",
    "web/backend/production.env",
    "web/backend/tests/test_auth_anonymous.py",
    "docs/plimsoll-1.0/spec.md",
    "data/plimsoll-local.db",
    "queen_mary_v4/Gameplay.fbx",
)
DEPLOY = ("web/deploy/Dockerfile", "web/deploy/tests/test_build_release.py")
DIST = ("web/frontend/dist/index.html", "web/frontend/dist/assets/index-BtMdWUKy.js")


def write(repo_root: Path, member: str, text: str = "x\n") -> None:
    path = repo_root / member
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed(repo_root: Path) -> None:
    for member in TRACKED + DEPLOY + DIST:
        if build_release.is_denied_path(member) and member not in DEPLOY:
            continue
        write(repo_root, member)


def build(repo_root: Path, output_dir: Path, **kwargs):
    parameters = {
        "tracked_files": TRACKED,
        "deploy_files": DEPLOY,
        "dist_files": DIST,
        "head": "0" * 40,
        "dirty": False,
        "allow_missing_git": True,
    }
    parameters.update(kwargs)
    return build_release.build_release(repo_root, output_dir, **parameters)


class IncludeCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self.output = Path(self._tmp.name) / "out"
        seed(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_core_backend_templates_and_dist_assets_are_archived(self) -> None:
        manifest = build(self.repo, self.output)
        paths = {entry["path"] for entry in manifest["files"]}
        for expected in (
            "tools/plimsoll/hydrostatics.py",
            "tools/plimsoll/cases/templates/generic_cargo.json",
            "web/backend/alembic/versions/6226f03d283f_initial_web_workspace_schema.py",
            "web/backend/alembic.ini",
            "web/backend/plimsoll_web/asgi.py",
            "web/backend/pyproject.toml",
            "web/deploy/Dockerfile",
            "web/deploy/tests/test_build_release.py",
            "web/frontend/dist/index.html",
            "web/frontend/dist/assets/index-BtMdWUKy.js",
        ):
            self.assertIn(expected, paths)

        archive_path = Path(manifest["archive_path"])
        self.assertTrue(archive_path.is_file())
        with tarfile.open(archive_path, "r:gz") as archive:
            names = archive.getnames()
        prefix = manifest["archive"]["prefix"]
        self.assertEqual(
            sorted(name for name in names if "/tools/" in name or "/web/" in name),
            sorted(f"{prefix}/{member}" for member in paths),
        )
        self.assertFalse(any(name.startswith("/") or ".." in name for name in names))

    def test_manifest_hashes_match_bytes_on_disk(self) -> None:
        manifest = build(self.repo, self.output)
        for entry in manifest["files"]:
            absolute = self.repo / entry["path"]
            self.assertEqual(entry["sha256"], build_release.sha256_file(absolute))
            self.assertEqual(entry["bytes"], absolute.stat().st_size)
        archive_path = Path(manifest["archive_path"])
        self.assertEqual(
            manifest["archive"]["sha256"], build_release.sha256_file(archive_path)
        )
        self.assertEqual(manifest["file_count"], len(manifest["files"]))
        manifest_path = Path(manifest["manifest_path"])
        self.assertEqual(
            json.loads(manifest_path.read_text(encoding="utf-8"))["archive"]["sha256"],
            manifest["archive"]["sha256"],
        )


class DeploymentConfigTest(unittest.TestCase):
    """Static sanity checks on the shipped deploy configuration."""

    def test_compose_build_context_is_the_repo_root(self) -> None:
        text = (_DEPLOY_DIR / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("context: ../..", text)
        self.assertIn("dockerfile: web/deploy/Dockerfile", text)
        # A context of "." would resolve the Dockerfile to web/deploy/web/deploy/...
        self.assertNotIn("context: .\n", text)
        # compose lives in web/deploy, so ../.. must reach the release/repository root.
        self.assertEqual(
            (_DEPLOY_DIR / ".." / "..").resolve(),
            Path(build_release.default_repo_root()).resolve(),
        )

    def test_only_api_publishes_a_port_and_keeps_its_healthcheck(self) -> None:
        text = (_DEPLOY_DIR / "compose.yaml").read_text(encoding="utf-8")
        services = _service_blocks(text)
        self.assertEqual(set(services), {"db", "migrate", "api", "worker"})
        self.assertNotIn("ports:", services["db"])
        self.assertNotIn("ports:", services["worker"])
        self.assertNotIn("ports:", services["migrate"])
        self.assertIn("127.0.0.1:18000:8000", services["api"])
        # api inherits the image HEALTHCHECK that probes /api/health.
        self.assertNotIn("healthcheck:", services["api"])
        # The image HEALTHCHECK probes /api/health, which worker and migrate never serve.
        for name in ("worker", "migrate"):
            self.assertIn("disable: true", services[name])
        # api and worker start only after the one-shot migration succeeded.
        for name in ("api", "worker"):
            self.assertIn("service_completed_successfully", services[name])
            self.assertIn("service_healthy", services[name])
        # migrate waits for a healthy database and nothing else.
        self.assertIn("service_healthy", services["migrate"])
        self.assertNotIn("service_completed_successfully", services["migrate"])
        for name in ("api", "worker", "migrate"):
            self.assertNotIn("PLIMSOLL_LOCAL_HTTP", services[name])
            self.assertNotIn("PLIMSOLL_LOCAL_MAIL_TEST", services[name])
            self.assertNotIn("PLIMSOLL_SMTP", services[name])

    def test_runtime_image_is_shared_and_non_root(self) -> None:
        text = (_DEPLOY_DIR / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("image: plimsoll/runtime:local", text)
        self.assertEqual(text.count("image: plimsoll/runtime:local"), 1)
        dockerfile = (_DEPLOY_DIR / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:3.12-slim", dockerfile)
        self.assertIn("USER plimsoll", dockerfile)
        self.assertIn("PYTHONPATH=/app/tools", dockerfile)
        self.assertIn("--no-deps", dockerfile)

    def test_nginx_redirect_targets_the_rendered_server_name(self) -> None:
        text = (_DEPLOY_DIR / "nginx" / "plimsoll.conf.template").read_text(
            encoding="utf-8"
        )
        # An untrusted $host in the redirect would bounce visitors to an unknown Host.
        self.assertNotIn("return 308 https://$host", text)
        self.assertIn("return 308 https://__PLIMSOLL_SERVER_NAME__$request_uri", text)
        self.assertIn("proxy_pass http://127.0.0.1:18000;", text)
        self.assertIn("X-Forwarded-For $remote_addr", text)
        self.assertIn("client_max_body_size 8m;", text)
        self.assertIn("/var/www/acme", text.replace("__PLIMSOLL_ACME_ROOT__", "/var/www/acme"))


def _service_blocks(text: str) -> dict[str, str]:
    """Minimal indentation parser: enough to sanity-check this hand-written file.

    Service names sit two spaces under ``services:``; their keys sit four.
    """
    blocks: dict[str, list[str]] = {}
    inside = False
    current = ""
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("services:"):
            inside = True
            continue
        if not inside:
            continue
        if line.startswith("volumes:"):  # top-level named volume, not a service
            inside = False
            continue
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            current = line.strip().rstrip(":")
            blocks[current] = []
            continue
        if current and (line.startswith("    ") or line.startswith("      ")):
            blocks[current].append(line)
    return {name: "\n".join(lines) for name, lines in blocks.items()}


class ExclusionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self.output = Path(self._tmp.name) / "out"
        seed(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_secrets_caches_tests_and_foreign_trees_are_excluded(self) -> None:
        manifest = build(self.repo, self.output)
        paths = {entry["path"] for entry in manifest["files"]}
        for forbidden in (
            "web/backend/.env",
            "web/backend/production.env",
            "web/backend/plimsoll_web/__pycache__/asgi.cpython-312.pyc",
            "web/backend/.pytest_cache/CACHEDIR.TAG",
            "web/backend/.venv/Lib/site-packages/fastapi/__init__.py",
            "web/backend/plimsoll_web.egg-info/PKG-INFO",
            "web/backend/tests/test_auth_anonymous.py",
            "tools/plimsoll/tests/test_stability.py",
            "docs/plimsoll-1.0/spec.md",
            "data/plimsoll-local.db",
            "queen_mary_v4/Gameplay.fbx",
        ):
            self.assertNotIn(forbidden, paths)
        self.assertIn("web/backend/plimsoll_web/worker.py", paths)

        with tarfile.open(manifest["archive_path"], "r:gz") as archive:
            names = archive.getnames()
        self.assertFalse([name for name in names if ".env" in name])
        self.assertFalse([name for name in names if "__pycache__" in name])

    def test_missing_frontend_dist_is_refused(self) -> None:
        with self.assertRaises(ReleaseError) as caught:
            build(self.repo, self.output, dist_files=())
        self.assertIn("frontend/dist", str(caught.exception))

    def test_dist_without_index_is_refused(self) -> None:
        with self.assertRaises(ReleaseError) as caught:
            build(
                self.repo,
                self.output,
                dist_files=("web/frontend/dist/assets/index-BtMdWUKy.js",),
            )
        self.assertIn("index.html", str(caught.exception))

    def test_walk_dist_reads_real_assets_and_refuses_missing_root(self) -> None:
        members = build_release.walk_dist(self.repo)
        self.assertEqual(sorted(members), sorted(DIST))
        with self.assertRaises(ReleaseError):
            build_release.walk_dist(self.repo, "web/frontend/dist-missing")


class RefusalTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self.output = Path(self._tmp.name) / "out"
        seed(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_traversal_and_absolute_names_are_refused(self) -> None:
        for unsafe in (
            "../outside.py",
            "web/../../outside.py",
            "..\\outside.py",
            "/etc/passwd",
            "C:/windows/system32",
            "",
            "./",
        ):
            with self.subTest(name=unsafe):
                with self.assertRaises(ReleaseError):
                    build_release.normalize_member_name(unsafe)

    def test_symlinked_input_is_refused(self) -> None:
        target = self.repo / "web/backend/plimsoll_web/asgi.py"
        link = self.repo / "web/backend/plimsoll_web/aliased.py"
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError) as error:  # Windows without developer mode
            self.skipTest(f"symlink creation unavailable: {error}")
        tracked = TRACKED + ("web/backend/plimsoll_web/aliased.py",)
        with self.assertRaises(ReleaseError) as caught:
            build(self.repo, self.output, tracked_files=tracked)
        self.assertIn("symlink", str(caught.exception))

    def test_link_probe_refusal_is_enforced_on_every_platform(self) -> None:
        original = build_release.is_link

        def probe(path: Path) -> bool:
            return os.path.basename(str(path)) == "aliased.py" or original(path)

        tracked = TRACKED + ("web/backend/plimsoll_web/aliased.py",)
        with mock.patch.object(build_release, "is_link", side_effect=probe):
            with self.assertRaises(ReleaseError) as caught:
                build(self.repo, self.output, tracked_files=tracked)
        self.assertIn("symlink", str(caught.exception))

    def test_missing_allowlisted_input_is_refused(self) -> None:
        tracked = TRACKED + ("web/backend/plimsoll_web/absent.py",)
        with self.assertRaises(ReleaseError) as caught:
            build(self.repo, self.output, tracked_files=tracked)
        self.assertIn("missing input file", str(caught.exception))

    def test_missing_deploy_file_is_refused(self) -> None:
        deploy = DEPLOY + ("web/deploy/nginx/absent.conf",)
        with self.assertRaises(ReleaseError) as caught:
            build(self.repo, self.output, deploy_files=deploy)
        self.assertIn("missing input file", str(caught.exception))


class FreezeReportingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self.output = Path(self._tmp.name) / "out"
        seed(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_dirty_worktree_cannot_be_confirmed_frozen(self) -> None:
        with self.assertRaises(ReleaseError) as caught:
            build(self.repo, self.output, dirty=True, confirm_source_frozen=True)
        self.assertIn("dirty", str(caught.exception))

    def test_manifest_keeps_dirty_flag_and_freeze_state_honest(self) -> None:
        manifest = build(self.repo, self.output, dirty=True)
        self.assertIs(manifest["git"]["dirty"], True)
        self.assertFalse(manifest["git"]["source_freeze_confirmed"])
        name = manifest["archive"]["name"]
        self.assertIn("-dirty", name)

        confirmed = build(
            self.repo,
            self.output,
            dirty=False,
            confirm_source_frozen=True,
        )
        self.assertIs(confirmed["git"]["dirty"], False)
        self.assertTrue(confirmed["git"]["source_freeze_confirmed"])
        self.assertNotIn("-dirty", confirmed["archive"]["name"])

    def test_output_directory_is_created(self) -> None:
        nested = self.output / "nested" / "releases"
        manifest = build(self.repo, nested)
        self.assertTrue(Path(manifest["archive_path"]).is_file())
        self.assertTrue(Path(manifest["manifest_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
