# Explicit geometry content import API

`tools.plimsoll.geometry_import` implements method
`geometry-content-import-1`:

```python
import_geometry_content(
    project,
    content_bytes,
    *,
    format,
    keel_offset_m,
    source,
    estimate,
) -> dict
```

The function imports bytes already selected and read by a caller. It performs no
file lookup, repository scan, network request, generator execution, or project
save. The input project and bytes are not modified. The returned value is a new,
normalized canonical project with self-contained `kind="offsets"` geometry.
Call `project_store.save` separately when persistence is intended.

## Required declarations

`content_bytes` must be a `bytes` object containing strict UTF-8 JSON. The
keyword arguments are explicit:

- `format` is exactly `legacy-offsets-5` or
  `plimsoll-section-polygons-1`;
- `keel_offset_m` is a finite, nonboolean number in metres in the canonical
  geometry datum;
- `source` is a nonblank string or a nonempty JSON object describing the
  caller's selection/provenance;
- `estimate` is a boolean and is copied unchanged to `geometry.estimate`.

The importer performs no unit conversion and no origin shift. Polygon
coordinates remain exactly as supplied. The declared keel offset remains
separate and is not inferred from a polygon bound or legacy table value.

`legacy-offsets-5` requires a `plimsoll-offsets-1` object with at least five
strictly ordered five-number rows and an explicit positive `deck_z_m`. The raw
table and its deck are retained. It remains a
`legacy_offsets_5_section_generator` representation; import does not relabel it
as measured section polygons.

`plimsoll-section-polygons-1` requires that exact schema and its canonical
`stations=[[x_m, [[y_m, z_m], ...]], ...]` payload. Format/schema mismatches are
errors. The importer does not guess a format from row length.

## Validation

Parsing rejects invalid UTF-8, malformed JSON, duplicate object keys, unpaired
Unicode surrogates, `NaN`, `Infinity`, overflowing exponents, and integers
outside the supported finite numeric range. The root JSON value must be an
object.

After parsing, the importer constructs canonical materialized geometry and
calls `stability.prepare_geometry`. This shared adapter validates finite
nonboolean geometry numbers, minimum station count, strict station order,
section shape and contact, positive three-axis extent, declared datum, and
positive sealed-envelope capacity. Rows and stations are never sorted or
repaired by the importer.

The input project is normalized before replacement and the final project is
normalized again. Other hull facts, loading conditions, weights, sources,
opening knowledge, systems, deck extensions, and optional canonical metadata
remain intact apart from documented normalizer defaults.

## Provenance trace

The imported geometry has this trace shape:

```json
{
  "kind": "offsets",
  "keel_offset_m": 7.0,
  "estimate": false,
  "source": {
    "method": "geometry_content_import",
    "method_version": "geometry-content-import-1",
    "format": "plimsoll-section-polygons-1",
    "representation": "explicit_section_polygons",
    "raw_content_sha256": "...sha256 of the exact caller bytes...",
    "keel_offset_m": 7.0,
    "input_source": {"title": "selected drawing"},
    "input_estimate": false,
    "payload_provenance": {
      "source": {"title": "payload source"},
      "estimate": false
    }
  },
  "offsets": {"schema": "plimsoll-section-polygons-1", "stations": []}
}
```

The provenance wrapper keeps namespaces separate instead of merging caller and
payload objects. `payload_provenance` contains any top-level `source`,
`sources`, and `estimate` fields from the content; the complete parsed payload
also remains unchanged under `geometry.offsets`. Whitespace-only changes to the
source bytes therefore preserve parsed geometry but change
`raw_content_sha256`.

If the prior project geometry is a typed `offsets_reference`, its complete
normalized geometry object is copied to
`geometry.source.prior_offsets_reference`. The referenced path is provenance
only. Import never resolves or reads it, and the returned materialized geometry
does not depend on it after save or relocation.

The trace records supplied facts and transformations. It does not set or imply
historical validation.

## Errors and failure boundaries

Content and public-argument failures raise `GeometryImportError`, a
`ValueError` subclass with a `diagnostics` list. Each diagnostic contains
`code`, `severity`, `path`, `message`, and `blocking`. Errors from canonical
project validation retain their existing diagnostics inside the same exception
type. Parser and shared-geometry failures retain their original exception as
the Python cause, and geometry messages include the shared adapter's reason.

A failed import returns no partial project and performs no file operation. It
cannot alter the caller's project or an existing saved project. Saving remains
an explicit caller operation with `project_store.save` and its atomic replace
contract.
