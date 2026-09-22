# Task 8E independent review — round 0

Review range: `ae055fc22ece8a0a546da3a813e332569cf1ef17..7a673b97279866d9a052efadaf0dbf46de58a02b`  
Reviewed artifact: `task-8-review-ae055fc-7a673b9.diff`  
Scope: the ten Task 8E package-import paths listed in the review brief  
Production/index/HEAD handling: read-only

## Specification verdict: APPROVED

The implementation satisfies the package-import phase contract.

- `plimsoll.__init__` no longer mutates `sys.path` or installs top-level module
  aliases. Its six established eager exports and `__version__ = "0.4.2"`
  remain unchanged in authority and public scope.
- The seven changed legacy modules select explicit relative imports whenever
  `__package__` is set and retain their historical direct-module imports when it
  is not. The filtered diff changes import routing only: it contains no equation,
  numerical constant, data, schema, output formatting, CLI signature, command
  body, or source/deck precedence change.
- The subprocess tests exercise both package-first and submodule-first order,
  qualified module/class/exception identity, an unrelated top-level `geometry`
  sentinel, absence of local top-level leakage, unchanged `sys.path`, no cwd
  files, public core submodule imports, a real qualified hydrostatic calculation,
  legacy top-level imports, and direct CLI self-test/help.
- The package contract document accurately distinguishes qualified package mode
  from explicit legacy direct mode and does not claim the later installer,
  `python -m plimsoll`, coordinator, batch/sweep, or exporter phases.

The review brief specifically called out flooding with prepared geometry and
systems/engines/resistance as transitive identity risks. I therefore inspected
the unchanged import blocks in `flooding.py`, `stability.py`, `systems.py`, and
`resistance.py` in addition to the filtered diff. Flooding and stability select
their qualified dependencies in package mode, systems and resistance introduce
no local-module alias, and the accepted clean-process submodule test imports all
four. This bounded inspection found no ownership extension or Task 8E defect.

The producer intentionally excluded concurrently developed `geometry_import`,
analysis, export, and later CLI entrypoints. The review brief makes those later
integration surfaces outside this gate, so their absence from this import-only
acceptance is not a finding.

## Quality verdict: APPROVED

The import repair is small and direct. It removes global interpreter mutation
instead of recreating identity through `sys.modules`, and uses the same explicit
two-mode pattern consistently. Imports remain local inside functions where they
were already lazy, avoiding unrelated initialization changes. Removed imports
are no longer needed. Documentation matches behavior and the tests use isolated
processes and unrelated Chinese working directories, which is the meaningful
boundary for import-cache and path-side-effect assertions.

The producer report records 140 targeted passes across package imports, damage,
engines, offsets, calculation integrity, hull, and geometric suites. Per review
instructions I accepted that evidence and did not rerun tests or the full suite.
The earlier invocation without `PYTHONPATH` is correctly identified as runner
setup: the contract requires the package parent to be importable.

All ten current file SHA-256 values match the producer's frozen hash table.

## Findings

- Critical: 0
- Important: 0
- Minor: 0

## Gate

**APPROVED for Task 8E integration.** This verdict covers only the ordinary
package-import and legacy direct-mode phase. It is not whole-core completion or
acceptance of the coordinator, exporter, modern CLI, packaging, or deployment.
