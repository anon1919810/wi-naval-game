"""Subprocess acceptance for the bundled `readme` command.

The guide is the only command that computes nothing, so what is worth pinning
down is everything around it: that the bytes on stdout are exactly the bundled
resource, that nothing else is touched, and that a missing or corrupt resource
is an ordinary structured CLI error rather than a traceback.
"""

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


TOOLS = Path(__file__).resolve().parents[2]
PACKAGE = TOOLS / "plimsoll"
README = PACKAGE / "CLI_README.md"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import app  # noqa: E402


class ReadmeSubprocessTests(unittest.TestCase):
    def run_cli(self, arguments, cwd):
        env = dict(
            os.environ,
            PYTHONIOENCODING="utf-8",
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=str(TOOLS),
        )
        return subprocess.run(
            [sys.executable, "-B", "-m", "plimsoll", *map(str, arguments)],
            cwd=cwd, env=env, capture_output=True, check=False,
        )

    def test_stdout_is_the_bundled_resource_byte_for_byte(self):
        with tempfile.TemporaryDirectory(prefix="指南-") as temp:
            result = self.run_cli(["readme"], temp)
        expected = README.read_bytes()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        # Exact bytes, not a re-encoded or platform-newlined rendering: a caller
        # can compare stdout against the file it ships with.
        self.assertEqual(result.stdout, expected)
        self.assertGreater(len(expected), 0)
        # It is the one payload that has to be readable as UTF-8 Markdown.
        text = result.stdout.decode("utf-8")
        self.assertTrue(text.startswith("# "))
        self.assertIn("\n## ", text)

    def test_runs_from_an_unrelated_cwd_and_creates_nothing(self):
        # The guide must not depend on the working directory and must not write
        # to it: the directory is empty before and empty after.
        with tempfile.TemporaryDirectory(prefix="无关目录-") as temp:
            before = sorted(Path(temp).iterdir())
            result = self.run_cli(["readme"], temp)
            after = sorted(Path(temp).iterdir())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(after, before)
        self.assertEqual(result.stdout, README.read_bytes())

    def test_runs_with_no_project_loading_or_geometry_anywhere_in_reach(self):
        # An empty working directory is the whole world this command can see.
        # It cannot find a project, a condition or geometry because it never
        # looks: the same bytes come out of a directory that has neither.
        with tempfile.TemporaryDirectory(prefix="空世界-") as temp:
            result = self.run_cli(["readme"], temp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, README.read_bytes())

    def test_help_advertises_it_beside_every_existing_command(self):
        with tempfile.TemporaryDirectory(prefix="帮助-") as temp:
            result = self.run_cli(["--help"], temp)
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("analyze", "batch", "sweep", "import-geometry", "readme"):
            self.assertIn(command, result.stdout.decode("utf-8"))


class ReadmeIsolationTests(unittest.TestCase):
    """In-process: the guide performs no computation and writes no file."""

    def test_calls_no_calculation_exporter_or_project_loader(self):
        compute = mock.Mock(side_effect=AssertionError("readme must not calculate"))
        stdout = StringIO()
        with (
            mock.patch.object(app, "analysis", mock.Mock(compute_project=compute), create=True),
            mock.patch.object(app, "project_store", mock.Mock(
                load=mock.Mock(side_effect=AssertionError("readme must not load a project"))), create=True),
            mock.patch.object(app, "exports", mock.Mock(
                write_report=mock.Mock(side_effect=AssertionError("readme must not write a report")),
                serialize_report=mock.Mock(side_effect=AssertionError("readme must not serialize")),
                serialize_document=mock.Mock(side_effect=AssertionError("readme must not serialize"))),
                create=True),
            redirect_stdout(stdout),
        ):
            exit_code = app.main(["readme"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), README.read_text(encoding="utf-8"))
        compute.assert_not_called()

    def test_reads_only_the_one_fixed_package_resource(self):
        opened = []
        real_open = Path.read_bytes

        def watched(self, *args, **kwargs):
            opened.append(self)
            return real_open(self, *args, **kwargs)

        stdout = StringIO()
        with (
            mock.patch.object(Path, "read_bytes", watched),
            redirect_stdout(stdout),
        ):
            self.assertEqual(app.main(["readme"]), 0)
        self.assertEqual([path.resolve() for path in opened], [README.resolve()])
        self.assertEqual(stdout.getvalue(), README.read_text(encoding="utf-8"))

    def test_takes_no_arguments_and_refuses_them_as_usage_errors(self):
        for extra in (["extra"], ["--json"], ["--output", "x"]):
            with self.subTest(extra=extra):
                stdout, stderr = StringIO(), StringIO()
                with redirect_stdout(stdout), mock.patch("sys.stderr", stderr):
                    exit_code = app.main(["readme", *extra])
                self.assertEqual(exit_code, 2)
                self.assertEqual(stdout.getvalue(), "")
                payload = json.loads(stderr.getvalue())
                self.assertEqual(payload["schema"], "plimsoll-cli-error-1")
                self.assertEqual(payload["command"], "readme")
                self.assertEqual(payload["code"], "cli.usage")


class ReadmeResourceFailureTests(unittest.TestCase):
    """A missing or corrupt bundled resource is one structured CLI error."""

    def run_copy(self, mutate):
        """Run `readme` from a real copy of the package with one change applied."""
        with tempfile.TemporaryDirectory(prefix="缺指南-") as temp:
            root = Path(temp)
            copy = root / "plimsoll"
            shutil.copytree(PACKAGE, copy,
                            ignore=shutil.ignore_patterns("tests", "__pycache__"))
            mutate(copy)
            env = dict(
                os.environ,
                PYTHONIOENCODING="utf-8",
                PYTHONDONTWRITEBYTECODE="1",
                PYTHONPATH=str(root),
            )
            before = sorted(p.name for p in root.iterdir())
            result = subprocess.run(
                [sys.executable, "-B", "-m", "plimsoll", "readme"],
                cwd=root, env=env, capture_output=True, check=False,
            )
            after = sorted(p.name for p in root.iterdir())
        return result, (before, after)

    def assert_structured_failure(self, result):
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(result.stdout, b"")
        payload = json.loads(result.stderr.decode("utf-8"))
        self.assertEqual(payload["schema"], "plimsoll-cli-error-1")
        self.assertEqual(payload["command"], "readme")
        self.assertEqual(payload["code"], "cli.readme_unavailable")
        self.assertTrue(payload["diagnostics"][0]["blocking"])
        self.assertNotIn("Traceback", result.stderr.decode("utf-8"))

    def test_missing_resource_is_one_structured_error(self):
        result, unchanged = self.run_copy(lambda copy: (copy / "CLI_README.md").unlink())
        self.assert_structured_failure(result)
        # The failure wrote nothing either.
        self.assertEqual(*unchanged)

    def test_undecodable_resource_is_one_structured_error(self):
        result, _ = self.run_copy(
            lambda copy: (copy / "CLI_README.md").write_bytes(b"\xff\xfe not utf-8")
        )
        self.assert_structured_failure(result)

    def test_other_commands_are_unaffected_by_the_missing_guide(self):
        # The guide is an addition, not a dependency of the calculation surface:
        # with CLI_README.md gone, the normal commands still work.
        with tempfile.TemporaryDirectory(prefix="无指南计算-") as temp:
            root = Path(temp)
            copy = root / "plimsoll"
            shutil.copytree(PACKAGE, copy,
                            ignore=shutil.ignore_patterns("tests", "__pycache__"))
            (copy / "CLI_README.md").unlink()
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                       PYTHONPATH=str(root))
            result = subprocess.run(
                [sys.executable, "-B", "-m", "plimsoll", "analyze",
                 str(copy / "cases" / "projects" / "generic_steamer.project.json"),
                 "--condition", "loaded", "--output", str(root / "result.json")],
                cwd=root, env=env, capture_output=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
