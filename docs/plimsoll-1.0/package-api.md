# Python package import contract

Plimsoll's existing Python modules can be imported as a package when the
repository's `tools` directory is on `PYTHONPATH`. The current version authority
remains `plimsoll.__version__`.

```python
import plimsoll
from plimsoll import geometry
from plimsoll import resistance, systems
```

The package entry point continues to export only the established modules:
`hydrostatics`, `geometry`, `geometric`, `offsets`, `freesurface`, and `damage`.
Other implemented core modules are ordinary qualified submodules and are loaded
explicitly as `plimsoll.<module>`; they are not new eager package exports.

## Import identity and side effects

Package imports use relative module references. A qualified module is loaded
once under its qualified name, so `plimsoll.geometry` is the same module object
as `importlib.import_module("plimsoll.geometry")`, and internal class and
exception references retain that identity. Package import does not add paths to
`sys.path`, install top-level aliases, replace unrelated entries in
`sys.modules`, inspect the repository working directory, or create local files.
Importing the calculation package does not initialize GUI or network clients.

This contract supports imports from any working directory. The caller remains
responsible for making `tools` importable, for example through its existing
process environment:

```powershell
$env:PYTHONPATH = 'C:\path\to\repository\tools'
python -c "import plimsoll; print(plimsoll.__version__)"
```

## Direct legacy mode

Existing direct scripts and top-level module imports remain supported where the
repository already uses them. In that mode, the package directory itself is on
the import path and a module keeps its historical top-level name. Direct CLI
signatures, `--selftest`, help output, calculation output, and source/deck
precedence are unchanged.

Package-qualified and legacy top-level modules are two explicit import modes.
If a caller deliberately loads both modes in one process, Python may create two
module objects; the implementation does not merge them through global path or
module-table mutation.

## Current boundary

This import contract does not install Plimsoll as a distributable package and
does not add `python -m plimsoll`, modern batch/sweep commands, result exporters,
or missing analysis modules. Those interfaces require their separately reviewed
implementation phases.
