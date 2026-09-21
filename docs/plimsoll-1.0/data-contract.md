# Plimsoll 1.0 data contract

`plimsoll-project-1` is the canonical input contract for Plimsoll 1.0. It is a
JSON object. Canonical values use metres, metric tonnes, knots, kilowatts and
degrees. Callers may display or import other units, but must convert them with
`units.convert`; a field named `*_m` is never silently interpreted as feet.

Unknown values are JSON `null`. Zero is a known value and is never treated as
missing. Boolean values are not numbers. Numeric inputs must be finite JSON
numbers, so `NaN` and infinities are invalid.

## Coordinates and units

Every normalized project contains these exact objects:

```json
{
  "units": {
    "length": "m",
    "mass": "t",
    "speed": "kn",
    "power": "kW",
    "angle": "deg"
  },
  "coordinates": {
    "x_positive": "forward",
    "x_origin": "midships",
    "y_positive": "starboard",
    "z_origin": "keel"
  }
}
```

`x_m` is positive forward from midships, `y_m` is positive to starboard and
`kg_m` is positive upward from the keel. A geometry model has its own explicit
`keel_offset_m`; callers must not infer it from a waterline or model origin.

The supported explicit conversions are:

| Dimension | Units | Definition |
| --- | --- | --- |
| mass | `t`, `kg`, `long_ton` | `1 kg = 0.001 t`; `1 long_ton = 1.0160469088 t` |
| length | `m`, `ft` | `1 ft = 0.3048 m` |
| speed | `kn`, `m_s` | `1 kn = 1852 / 3600 m/s` |
| power | `kW`, `shp` | `1 shp = 0.7456998715822702 kW` |
| angle | `deg`, `rad` | `180 deg = pi rad` |

These precise definitions supersede rounded constants used by some legacy
calculators. Legacy results may differ only by the rounding implied by those
older constants. Cross-dimension conversions are errors.

## Top-level project

The canonical shape is:

```json
{
  "schema": "plimsoll-project-1",
  "id": "stable-project-id",
  "name": "Ship or study name",
  "revision": 0,
  "units": {},
  "coordinates": {},
  "hull": {},
  "geometry": null,
  "weight_groups": [],
  "loading_conditions": [],
  "systems": {},
  "compartments": [],
  "openings": [],
  "sources": {}
}
```

`id` and `name` are non-empty strings. `revision` is a nonnegative integer.
`new_project(name, project_id=None)` supplies these schema defaults and returns
an editable draft. Empty hull, geometry, weights and loading conditions produce
warnings because a draft need not yet describe a calculable ship.

`hull` may contain the existing dimension and coefficient fields. Unknown
dimensions remain `null`. Source-specific facts, assumptions and citations stay
attached to their original fields or under `sources`; normalization does not
replace them.

`geometry` is either `null` or an object with:

- `kind`: one of `parameters`, `offsets` or `offsets_reference`;
- `source`: source metadata;
- `estimate`: a boolean;
- `keel_offset_m`: a finite real number or `null`;
- the one payload matching its kind.

The payload validation at this layer is structural. `offsets_reference`
requires a `reference` object with a non-empty string `path`. `parameters`
requires a non-empty `parameters` object; it may remain partial and combine
with hull fields. Materialized `offsets` requires an `offsets` object with a
non-empty `stations` array. Empty payloads, wrong payload types, payloads that
do not match their kind and unsupported kinds are errors. Domain completeness
and hull physics remain the geometry loader's responsibility.

An unresolved external offsets file uses a typed reference, for example:

```json
{
  "kind": "offsets_reference",
  "source": "legacy hull offsets_path",
  "estimate": true,
  "keel_offset_m": null,
  "reference": {"path": "ship_offsets.json"}
}
```

The project loader resolves references explicitly. Core project I/O does not
scan repository paths.

`systems` remains separate from weight items. `compartments` and `openings` are
arrays reserved for their canonical domain payloads. Later Plimsoll tasks may
add optional, schema-preserving sections; they must validate those sections
without changing the meanings defined here.

Stored calculation output is not project input. Top-level `result`, `results`,
`cache`, `cache_key` and `input_fingerprint` fields are rejected, preventing a
stored result from changing its own input fingerprint.

## Weight groups and items

A weight group is:

```json
{
  "id": "machinery",
  "label": "Machinery",
  "required": true,
  "items": []
}
```

Group IDs are unique. `required` is a boolean; an empty required group produces
an incompleteness warning. Item IDs are unique across every group, not merely
within their containing group.

A weight item is:

```json
{
  "id": "main-engines",
  "mass_t": 1500.0,
  "x_m": -8.0,
  "y_m": 0.0,
  "kg_m": 4.2,
  "source": "builder weight return",
  "estimate": false,
  "uncertainty": {
    "mass_t": [1450.0, 1550.0],
    "x_m": [-8.5, -7.5],
    "y_m": [-0.2, 0.2],
    "kg_m": [4.0, 4.4]
  },
  "includes": ["machinery.main-engines", "machinery.thrust-blocks"]
}
```

All four numeric values may be `null`. `mass_t` and `kg_m` are nonnegative;
`x_m` and `y_m` are signed. Missing source metadata and each unknown numeric
value produce diagnostics. Normalization never invents a mass or centre of
gravity and never changes source metadata.

`estimate` is `true` for an estimate, `false` for explicitly confirmed
non-estimated provenance, and `null` when that provenance is unknown. A missing
item `estimate` normalizes to `null` and produces a warning; it is never
silently treated as `false`. Declared booleans are preserved. Legacy migration
may conservatively assign `true` when a legacy item omitted the field, while
retaining the untouched legacy payload under `legacy_inputs` and disclosing
the migration provenance.

`uncertainty` is optional. It is an object whose optional keys are exactly
`mass_t`, `x_m`, `y_m` and `kg_m`. Each value is a two-element inclusive range
`[lower, upper]` of finite real numbers. Lower must not exceed upper. Mass and
KG bounds are nonnegative; x and y bounds may be signed. A supplied range must
contain its known nominal item value, including either boundary. A range
without a known nominal is invalid.

`includes` is optional. It is an array of unique, non-empty string component
tokens recording ownership. Tokens do not add mass and are not nested weight
items. Loading resolution flags the same token owned by more than one item
whose effective mass is nonzero; project I/O only validates token shape.

## Loading conditions

A loading condition is:

```json
{
  "id": "normal",
  "label": "Normal",
  "reference_displacement_t": 26770.0,
  "overrides": {
    "fuel-oil": {"mass_t": 2200.0, "x_m": -3.0}
  }
}
```

Loading IDs are unique. `reference_displacement_t` is nonnegative or `null`.
An override key must name an existing weight item. Its value may contain only
`mass_t`, `x_m`, `y_m` and `kg_m`. Only fields present in an override replace
the base item value; omitted fields retain the base value. A present `null`
therefore explicitly makes that value unknown. Loading resolution, rather than
project I/O, applies overrides and detects duplicate active `includes` tokens.

Normal and deep reference displacements are checks, not residual-mass plugs.
They never fabricate an unlisted fuel, stores or payload difference.

## Diagnostics and normalization

Every diagnostic has this shape:

```json
{
  "code": "value.unknown",
  "severity": "warning",
  "path": "$.weight_groups[0].items[0].x_m",
  "message": "value is unknown; downstream calculations must not substitute zero",
  "blocking": false
}
```

Severity is `info`, `warning` or `error`. Errors are blocking malformed-input
conditions. Draft incompleteness, unknown values and absent provenance are
warnings at this layer; downstream calculations decide whether a particular
warning blocks their requested output.

`validate_project(payload)` returns the complete diagnostic list.
`normalize_project(payload)` deep-copies its input, supplies schema defaults and
raises `ProjectValidationError` when any error diagnostic exists. The exception
retains all diagnostics on its `diagnostics` attribute. Unsupported schema
versions are errors. Normalization never mutates the caller's object.

## Legacy migration

`migrate_legacy(ship, weights=None)` accepts `plimsoll-ship-1` and an optional
`plimsoll-weights-1` payload. It:

- retains exact deep copies under `legacy_inputs.ship` and
  `legacy_inputs.weights`;
- copies the legacy hull and converts a declared `long_ton` displacement to
  metric tonnes with the precise public conversion;
- records the source and target mass units under `sources.migration`;
- marks an absent or explicitly unconfirmed legacy tonne convention as
  estimated instead of declaring it measured;
- creates `normal` and `deep` loading references, leaving unavailable values
  `null` and never inferring a load difference;
- maps legacy weight items, preserving their source and estimate status, while
  leaving missing x/y coordinates `null` so validation emits structured
  diagnostics; and
- retains an offsets path as an unresolved `offsets_reference` geometry object.

Migration is deterministic for the same legacy inputs when the ship lacks an
explicit ID.

## Input fingerprint

`input_fingerprint(project)` normalizes and validates the project, serializes it
as UTF-8 canonical JSON with recursively sorted object keys and no nonfinite
numbers, and returns the lowercase SHA-256 digest. Dictionary insertion order
does not affect the digest. Any retained project input change does; array order
remains significant.
