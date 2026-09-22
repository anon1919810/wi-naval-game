# Connected quasi-static flooding API

`tools.plimsoll.flooding` implements method
`connected-quasi-static-flooding-1`:

```python
simulate_flooding(project, condition_id, scenario, options=None) -> dict
```

The API normalizes the canonical project, resolves the selected loading, and
uses `stability.solve_loaded_equilibrium` at the initial state and after every
accepted water transfer. Tank centroids come only from Task 5
`tank_geometry.liquid_state`. Scenario water is additional mass; it is not a
lost-buoyancy subtraction and receives no second free-surface correction.

## Scenario input

A scenario uses schema `plimsoll-flooding-scenario-1`:

```json
{
  "schema": "plimsoll-flooding-scenario-1",
  "id": "single-hole",
  "duration_s": 60.0,
  "time_step_s": 0.5,
  "source": {"kind": "declared_scenario"},
  "estimate": false,
  "sea": {
    "id": "sea",
    "fluid_density_t_m3": 1.025,
    "source": {"kind": "declared_density"},
    "estimate": false
  },
  "tanks": [
    {
      "id": "room-a",
      "length_m": 4.0,
      "beam_m": 2.0,
      "height_m": 4.0,
      "x_m": 0.0,
      "y_m": 0.0,
      "keel_to_bottom_m": 0.0,
      "permeability": 1.0,
      "free_surface": true,
      "fluid_density_t_m3": 1.025,
      "initial_volume_m3": 8.0,
      "source": {"kind": "declared_geometry"},
      "estimate": false
    }
  ],
  "connections": [
    {
      "id": "sea-hole",
      "from": "sea",
      "to": "room-a",
      "x_m": 0.0,
      "y_m": 0.0,
      "z_m": 0.1,
      "area_m2": 0.1,
      "discharge_coefficient": 0.6,
      "fluid_density_t_m3": 1.025,
      "open": true,
      "source": {"kind": "declared_aperture"},
      "estimate": false
    }
  ]
}
```

Tank, sea and connection IDs are explicit. IDs are unique, every connection
must resolve both ends, and the sea ID must differ from every tank ID. Tank IDs
must also be absent from the resolved base weight-item ledger. This catches a
direct duplicate-water path; callers remain responsible for not representing
the same physical liquid under unrelated IDs.

All connected nodes and edges declare the same positive
`fluid_density_t_m3`. `initial_volume_m3` is physical liquid volume, not a fill
percentage. Task 5 validates it against permeability-scaled capacity. Missing
`discharge_coefficient` is invalid; the API never inserts a default. Area or Cd
may be explicit zero, producing zero flow. `open` must be boolean. Source and
estimate metadata are required on the scenario, sea, every tank, every
connection, and supplied downflooding opening. `source` must be either a
non-empty string or a non-empty object. Null, blank-string, and empty-object
placeholders produce a blocking `flooding.source_invalid` diagnostic at the
exact field path.

Connections are the only flow edges. Project or scenario downflooding points
are never converted into connections. Scenario `openings` overrides project
openings. An explicit empty array means supplied knowledge of no open points.
An explicit scenario `null` is the sanctioned bridge for preserved unknown
opening knowledge: it remains `null` in the result scenario and physical-input
fingerprint and produces unknown downflooding even if normalized project data
contains an empty array. Absence from both project and scenario also leaves
downflooding unknown and emits a diagnostic.

An optional positive `aperture_height_m` requests a finite-height
applicability check. If an active liquid surface crosses that height, the
point-orifice model stops at a visible model limit. A closed or zero-flow edge
does not trigger that limit and does not deactivate the liquid free surface.
Exact equal heads are classified as zero flow before the finite-height check,
so an aperture touching both equal surfaces does not create a false partial-
aperture limit.
Pressure fields are rejected because compressed-air and pressure-network flow
are outside this version.

## Options

| Option | Meaning |
| --- | --- |
| `gravity_m_s2` | Positive finite gravity; default `9.80665` |
| `max_steps` | Positive accepted-step limit; default `100000` |
| `max_step_halvings` | Per-step coupled retry count in `[0,60]`; default `40` |
| `equilibrium` | Task 4 solver options except `liquid_loads`, which flooding owns |
| `cancel_check` | Optional callable receiving the last accepted timeline state |
| `remaining_gz_angles_deg` | Optional strictly increasing sampled-curve angles |
| `remaining_gz_snapshot` | `final` or `each_state`; default `final` |

The equilibrium ambient density must equal scenario sea density. The same
explicit density, datum, bounds, and current liquid loads are passed to every
remaining-GZ sample. `cancel_check` is operational state and is excluded from
the deterministic physical-input fingerprint.

## Flow and timestep method

The private `_flooding_kernel.py` owns only the vented pressure-head network.
It compares tank and sea planes along the shared unit normal

```text
n = (-tan(trim), -tan(heel), 1) / sqrt(1+p²+q²)
```

and uses

```text
Q = Cd A sign(hi-hj) sqrt(2 g abs(hi-hj)).
```

Tank/aperture z coordinates are above keel. The geometry keel offset is applied
before comparing them with Task 4's geometry-datum waterline. The slope
intercept `waterline_d_m` is converted to a unit-normal sea offset; raw body-z
subtraction is never used at inclination.

Each edge creates one signed transfer. Internal edges apply the same transfer
with opposite signs to their endpoints. Before a candidate is formed, all
incoming and outgoing rates are aggregated by tank and the duration is bounded
against dry-out and receiver capacity. There is no independent post-update
clamp. The coupled driver then resolves full equilibrium and reevaluates all
heads. It halves and retries before accepting a head reversal, unsupported
aperture state, unresolved liquid geometry, or failed equilibrium. Exhausting
the explicit retry bound stops visibly and retains the last accepted state.

The time method is bounded first-order explicit Euler. Refinement evidence is
reported separately from exact arithmetic conservation; numerical ODE error
never relaxes the volume/mass ledger criterion.

For a full tank, the head reference is the rectangular tank's upper support
plane along the common normal, permitting directed outflow. Continued inflow
to a full receiver stops with `receiver_capacity`. The model does not invent
overflow or pressure and does not discard excess water.

## Result and stop semantics

Result schema is `plimsoll-flooding-result-1`. `timeline[0]` is the accepted
initial equilibrium at `t=0`; later accepted times are strictly increasing.
Each row contains:

- actual accepted `dt`, tank volumes and Task 5 liquid snapshots/centroids;
- a compact Task 4 equilibrium with force/moment residuals;
- individual signed flow and transfer records;
- step and cumulative sea volume/mass exchange;
- total onboard water volume/mass and independent conservation residuals;
- the supplied-opening clearance assessment.

The normalized scenario and loading are stored once at the result level; full
source geometry and loading are not repeated in every timeline row. A failed
candidate is placed in `failed_attempt`, never appended as a successful state.

Statuses and stop reasons are distinct:

| Status | Meaning |
| --- | --- |
| `completed` / `scheduled_completion` | Requested duration reached |
| `completed` / `equal_heads_or_no_open_flow` | Network reached zero active flow |
| `canceled` | Callback requested cancellation after the last accepted state |
| `equilibrium_failure` | No acceptable Task 4 solution within bounded retries |
| `model_limit` | Capacity, dry-out, partial aperture, timestep or step limit |
| `downflooding_event` | A supplied open point is immersed at an accepted state |
| `invalid_input` | Project, scenario, metadata or option validation failed |

Downflooding event time is the accepted state where immersion was first
observed and is labelled `immersed_at_accepted_state`; it is not presented as
an interpolated exact crossing. Completion, convergence, model applicability,
historical validation and safety remain separate. Positive GM or positive
sampled GZ never sets `safe=true`.

`validity.numerical_convergence` is an independent three-state field. It is
`null` when validation rejects input before any equilibrium solve, `false`
when the initial or an ultimately required candidate equilibrium does not
converge, and `true` when every state accepted into the reported trajectory
has a converged equilibrium. `true` does not imply scheduled completion or
model applicability: cancellation, downflooding, capacity and partial-
aperture stops can retain a converged last accepted state.

## Presets and legacy migration

`cases/projects/damage-presets.json` contains deterministic generic single,
two-connected, asymmetric and closed-valve scenarios plus Queen Mary layout
proxies. Every preset resolves to a shipped canonical project and loading
condition. The generic presets use
`cases/projects/generic_flooding_box.project.json`, an analytic rectangular
fixture that explicitly declares `opening_definition: supplied` with no
downflooding points. Queen Mary tank boundaries and apertures are explicitly
estimated and are not historical subdivision or damage evidence.

Legacy `damage.solve_flooded_equilibrium` and `run_damage_scenario` remain
callable compatibility paths. They use upright centroids, scalar FSC/upright
KM approximations, and a small-angle heel estimate. Their `stable` flag is not
the new API's safety result. New work should use `simulate_flooding`, which
uses moving Task 5 liquid centroids and Task 4 projected three-axis equilibrium
without adding legacy FSC or lost buoyancy.

## Applicability

This version models a single incompressible vented liquid, static ambient sea
surface, constant Cd, rectangular tanks, and fully submerged point orifices.
It excludes compressed air, pressure networks, partially wetted finite
openings, unmodeled overflow, waves, sloshing, structural failure and
dynamically changing damage geometry. Its oracle agreement validates the
declared equations and numerical refinement, not historical ship behavior.
