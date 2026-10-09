"""Public CLI protocol and malformed extension regressions."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from plimsoll import project_io

TOOLS = Path(__file__).resolve().parents[2]
PROJECT = TOOLS/'plimsoll/cases/projects/analytic_box.project.json'


class CliRuntimeAuditTests(unittest.TestCase):
    def cli(self, args):
        return subprocess.run([sys.executable, '-m', 'plimsoll', *map(str, args)],
            env=dict(os.environ, PYTHONPATH=str(TOOLS), PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8'),
            capture_output=True, text=True, encoding='utf-8', timeout=30)

    def error(self, result):
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        error = json.loads(result.stderr)
        self.assertEqual(error['schema'], 'plimsoll-cli-error-1')
        return error

    def test_usage_errors_are_structured_and_help_is_normal(self):
        for args in ([], ['unknown'], ['analyze'], ['analyze', PROJECT, '--condition', 'loaded', '--invalid']):
            with self.subTest(args=args):
                self.error(self.cli(args))
        help_result = self.cli(['--help'])
        self.assertEqual(help_result.returncode, 0)
        self.assertIn('usage:', help_result.stdout)
        self.assertEqual(help_result.stderr, '')

    def test_analyze_failed_output_reports_actual_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = root/'options.json'
            options.write_text('{"stages":["loading"]}', encoding='utf-8')
            base = ['analyze', PROJECT, '--condition', 'loaded', '--options', options]
            error = self.error(self.cli([*base, '--csv', root]))
            self.assertEqual(error['calculation_status'], 'completed')
            self.assertEqual(error['persisted_outputs'], [])
            output = root/'result.json'
            error = self.error(self.cli([*base, '--output', output, '--csv', root]))
            self.assertEqual(error['persisted_outputs'], [str(output.resolve())])
            self.assertTrue(output.is_file())

    def test_sweep_field_shape_error_has_its_exact_path(self):
        for field in ([], {}):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = root/'sweep.json'
                manifest.write_text(json.dumps(dict(schema='plimsoll-sweep-1', project=str(PROJECT),
                    condition_id='loaded', base_options={}, axes=[dict(field=field, values=[1], source='test', estimate=True)])), encoding='utf-8')
                error = self.error(self.cli(['sweep', manifest, '--out', root/'out']))
                self.assertIn('$.axes[0].field', [d['path'] for d in error['diagnostics']])

    def test_malformed_system_containers_have_structured_errors(self):
        base = project_io.new_project('Draft', 'draft')
        for path in (('systems',), ('systems', 'armour'), ('systems', 'armour', 'fixed')):
            for value in ([], [{}]):
                p = copy.deepcopy(base)
                cursor = p
                for key in path[:-1]:
                    cursor = cursor.setdefault(key, {})
                cursor[path[-1]] = value
                with self.subTest(path=path, value=value), self.assertRaises(project_io.ProjectValidationError) as failure:
                    project_io.normalize_project(p)
                self.assertTrue(any(d['blocking'] for d in failure.exception.diagnostics))


if __name__ == '__main__':
    unittest.main()
