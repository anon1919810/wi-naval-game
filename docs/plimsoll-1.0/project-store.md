# Project file persistence

`tools/plimsoll/project_store.py` supplies real local-file persistence for
`plimsoll-project-1`. It uses the existing project normalization and migration
contracts in [data-contract.md](data-contract.md).

```python
from plimsoll import project_store

project = project_store.load("studies/试验船.json")
project["name"] = "修改后的试验船"
project_store.save("studies/试验船.json", project)
```

`load(path) -> dict` reads UTF-8 JSON and returns a normalized independent
canonical project. `save(path, project) -> None` normalizes a copy and writes
canonical UTF-8 JSON. Neither operation mutates caller input, computes results,
increments revisions, substitutes zeros for unknowns, or fills missing geometry.
Existing parent directories are required. File, JSON, encoding and validation
errors propagate to the caller; there is no last-successful-project fallback.

Canonical normalization preserves unknown values, explicit zeros, IDs, sources,
estimate states, uncertainty, loading overrides and JSON extension fields.
Warnings remain available through `project_io.validate_project(project)`;
malformed project errors retain the complete `ProjectValidationError.diagnostics`
list. Persistence does not turn an incomplete draft into a calculable project.

Both functions also accept `plimsoll-ship-1` input through
`project_io.migrate_legacy`. Files saved by this module always use the canonical
schema and retain the original legacy ship under `legacy_inputs.ship`.
There is no sibling weights-file discovery. To include legacy weights, read the
chosen files explicitly, call `project_io.migrate_legacy(ship, weights)`, then
save the migrated project. The original weights remain in `legacy_inputs.weights`.

## External geometry references

Loading or saving a project preserves its typed `offsets_reference` object.
Neither operation reads the referenced geometry, checks its existence, searches
repository locations, imports generators, or guesses a missing keel datum.

```python
geometry_path = project_store.resolve_geometry_reference(project_file, project)
```

`resolve_geometry_reference(project_path, project) -> pathlib.Path` validates the
canonical input and requires `geometry.kind == "offsets_reference"`. It resolves
the declared `geometry.reference.path` relative to the project file's directory,
independently of the current working directory. A fully absolute declared path
is accepted. Ambiguous Windows drive-relative or rooted-without-drive paths are
rejected. The path is normalized through `Path.resolve()` (including filesystem
symlinks); no referenced content is read, and a missing target is permitted.
No path, resolved payload or machine-specific metadata is inserted into the
project. This keeps persistence and canonical input fingerprints stable.

Relative references can include `..`; this helper is a local file resolver,
not a filesystem authorization boundary. A future browser-facing import must
use user-selected content, not expose arbitrary local paths.

**Save-as is not automatic packaging:** saving the same project in another
directory keeps the literal reference path and changes its resolution base.
An external reference project is therefore not automatically portable. Explicit
content import/materialization with validated geometry, provenance and content
hash belongs to the later coordinator integration. Until that operation exists,
callers must handle unresolved geometry as unavailable rather than generate a
replacement. This phase does not implement reference-content materialization.

## Atomic save boundary

Before creating any temporary file, `save` normalizes, validates, serializes
using `allow_nan=False`, and encodes all content as UTF-8. A unique owned
temporary file is then created in the destination's directory, written, flushed,
and `fsync`ed. After closing it, `os.replace` atomically installs it. On an
ordinary write, flush or replacement failure, cleanup removes only that owned
temporary path and the previous destination bytes remain intact. Other
temporary files are never scanned or removed. Successful saves leave no owned
temporary file.
If cleanup itself raises an operating-system error after a save failure, the
original write/flush/replace exception remains the raised exception. Its notes
identify the owned temporary path and cleanup error; that path may remain for
manual cleanup. A successful replacement already consumes the temporary path
and does not attempt a second filesystem deletion.

Atomicity follows the local filesystem's replacement semantics. This is not a
multi-writer transaction or a guarantee against power loss: no directory fsync,
locking, conflict detection or backup/version history is provided. A process
crash may leave its owned temporary file behind. Validation and serialization
failures occur before the existing file is touched.

The module supports ordinary package imports and the existing direct-module
entrypoints, with no path injection or `sys.modules` aliases in this module.
The legacy package initializer's import cleanup remains a later integration task.
