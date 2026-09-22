# Task 8E — package import repair report

Date: 2026-09-22  
Authorized base: `ae055fc22ece8a0a546da3a813e332569cf1ef17`  
Working-tree HEAD at freeze: `92019a7f45d8403f6c154932709d9e466a810c67`  
Runtime: Python `3.13.14` (`Jun 11 2026`, MSC v.1944, AMD64), using the
declared executable whose directory is named `3.13.12`.

## Result

READY_FOR_INTEGRATION. Ordinary `plimsoll` package imports now use qualified
relative modules and preserve internal module, class, and exception identity.
Package import no longer mutates `sys.path`, creates top-level local-module
aliases, overwrites unrelated top-level modules, depends on the repository
working directory, creates files, or initializes GUI/network packages. The six
existing eager exports and the single version authority are unchanged.

Existing direct script and top-level-module modes remain explicit fallbacks.
The legacy CLI retains its existing commands, self-test, help, output behavior,
and source/deck code paths. No equation, numerical constant, function body,
schema, case data, modern CLI command, package installer, `__main__`, analysis,
or exporter was added or changed.

## Changed paths

- `tools/plimsoll/__init__.py`: removed global path injection and top-level
  aliases; retained the established exports through relative imports.
- `tools/plimsoll/cli.py`
- `tools/plimsoll/damage.py`
- `tools/plimsoll/engines.py`
- `tools/plimsoll/geometric.py`
- `tools/plimsoll/hull.py`
- `tools/plimsoll/offsets.py`
- `tools/plimsoll/run_damage_scenarios.py`

  The seven legacy modules above route imports relative to the package when
  `__package__` is set and retain their direct legacy import path otherwise.
  Their calculations and command bodies are unchanged.
- `tools/plimsoll/tests/test_package_imports.py`: subprocess coverage from
  unrelated Chinese working directories for import orders, path/file side
  effects, sentinel preservation, top-level leakage, GUI/network absence,
  qualified module/class/exception identity, public-submodule imports, a real
  hydrostatic calculation, direct top-level imports, and CLI self-test/help.
- `docs/plimsoll-1.0/package-api.md`: records qualified package use, legacy
  direct mode, existing exports, side-effect guarantees, and later boundaries.

The concurrent geometry importer and analysis work was excluded from this
inventory as directed. No file owned by those phases was edited.

## TDD evidence

All commands ran from
`C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0` with UTF-8.

The first package test was written before production changes and run as:

```powershell
$env:PYTHONIOENCODING='utf-8'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_package_imports.py -v
```

RED: 5 tests ran in 0.919s; 3 failed. The failures demonstrated leaked
top-level `damage`, `freesurface`, `geometric`, `geometry`, `hydrostatics`,
`offsets`, and `units` modules; an unrelated top-level `geometry` sentinel broke
the package's `offsets` import; and a constructed hull class reported module
`geometry` instead of `plimsoll.geometry`.

After the import-only production repair, the same command was GREEN: 5 tests in
0.903s. After adding the final direct-mode and transitive identity assertions,
the literal command remained the same and passed 6 tests in 1.141s.

The import-sensitive legacy suites used the package parent explicitly:

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH=(Resolve-Path 'tools').Path; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_damage_loop.py -v
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH=(Resolve-Path 'tools').Path; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_engines.py
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH=(Resolve-Path 'tools').Path; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_offsets_import.py
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH=(Resolve-Path 'tools').Path; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_calculation_integrity.py
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH=(Resolve-Path 'tools').Path; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_hull.py
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH=(Resolve-Path 'tools').Path; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_geometric.py
```

| Suite | Passed | Seconds |
| --- | ---: | ---: |
| package imports | 6 | 1.141 |
| damage loop | 11 | 86.865 |
| engines | 25 | 0.003 |
| offsets import | 16 | 6.176 |
| calculation integrity | 15 | 4.530 |
| hull | 32 | 1.091 |
| geometric | 35 | 7.081 |
| **Total** | **140** | |

An earlier exploratory compatibility invocation omitted `PYTHONPATH`. Its ten
direct-module cases completed, but `test_import_plimsoll_callables` failed with
`ModuleNotFoundError` because that legacy test assumes the package parent is
already importable. The corrected literal command above passed all 11 cases.
This was a runner setup error, not a changed code expectation.

No full suite or costly numerical refinement suite was run.

## Scoped checks and frozen hashes

`git diff --check` passed for all ten Task 8E paths. Final SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `tools/plimsoll/__init__.py` | `3789D6F6EAE2512E779D97BDFBAD61435A411FBED2D95A93810350E284C578BD` |
| `tools/plimsoll/cli.py` | `926F4DC7DDB3D6803AEB080731A3DC89C8ABB38F92CD4804FFFC12A1F511197F` |
| `tools/plimsoll/damage.py` | `55ACE3E243370DAD39ED19F9BD094A5843DA36C1651BA823B91AD9CA9D6AAC97` |
| `tools/plimsoll/engines.py` | `B5F4443D60ABC5F120AB913AC943E3F2E8DFB7D28288EE58E49F3E50AC1D1673` |
| `tools/plimsoll/geometric.py` | `932CBC9B32EC9AA50C74A907B8A0AAC19E6F7E6DEDD19395C4B46CECA68EC50E` |
| `tools/plimsoll/hull.py` | `F99878D20863397B066E89D9FFD9A7C2749A4C1CDF69E4CAA6D07804F71E4BBC` |
| `tools/plimsoll/offsets.py` | `9C879B4134C8C0C3B9EB0047D38E9DF55C32E65445338512F2E5DE1269B04D0E` |
| `tools/plimsoll/run_damage_scenarios.py` | `52F0A70F3D05D344E36E0C9C59A5824207C831C4FEE0E783892343C9EA50FEDE` |
| `tools/plimsoll/tests/test_package_imports.py` | `D823942724891C2FA2C6B9C0DFB139C0AA01FB07FF70232EEDF229F10A084A89` |
| `docs/plimsoll-1.0/package-api.md` | `88827F20AF4641606050D3AC634F41A0CC86D0AF4850899D9F5A3D7D673FDE59` |

## Remaining boundaries

The package test intentionally excludes the concurrently developed
`geometry_import` and `analysis` modules until their owners freeze and release
them for integration. Installation metadata, `python -m plimsoll`, coordinator
commands, batch/sweep interfaces, and exports remain separate Task 8 phases.
