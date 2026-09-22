"""Run focused persistence mutations in memory without editing shared source."""

import io
from pathlib import Path
import sys
import types
import unittest

root = Path(__file__).resolve().parents[3]
package = root / "tools" / "plimsoll"
sys.path.insert(0, str(package))
sys.path.insert(0, str(package / "tests"))
import test_project_store

source = (package / "project_store.py").read_text(encoding="utf-8")
original = test_project_store.project_store
mutations = [
    ("omit_atomic_replace", "os.replace(temporary_path, destination)", "pass",
     "test_chinese_roundtrip_preserves_identity_unknown_zero_and_sources"),
    ("omit_owned_cleanup", "temporary_path.unlink(missing_ok=True)", "pass",
     "test_replace_failure_preserves_previous_file_and_cleans_only_owned_temp"),
    ("resolve_against_cwd", "Path(project_path).absolute().parent", "Path.cwd()",
     "test_reference_resolution_uses_project_directory_without_reading_or_mutating"),
    ("unknown_to_zero", "return _normalize(json.load(stream))",
     "return json.loads(json.dumps(_normalize(json.load(stream))).replace('null', '0'))",
     "test_chinese_roundtrip_preserves_identity_unknown_zero_and_sources"),
]
for name, before, after, test_name in mutations:
    assert source.count(before) == 1, name
    mutant = types.ModuleType("project_store_mutation")
    exec(compile(source.replace(before, after), str(package / "project_store.py"), "exec"),
         mutant.__dict__)
    test_project_store.project_store = mutant
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output).run(unittest.TestSuite([
        test_project_store.TestProjectStore(test_name),
    ]))
    test_project_store.project_store = original
    print(f"{name}: {'DETECTED' if not result.wasSuccessful() else 'SURVIVED'}")
    if result.wasSuccessful():
        raise SystemExit(1)
print("4/4 focused mutations detected; production files untouched")
