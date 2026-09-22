# Taylor–Gertler and Schoenherr validation contract

Prepared 2026-09-22 before production Task 7 changes. These are acceptance
definitions, not evidence that the production implementation passes them.

## Sources and definitions

Molland, Turnock and Hudson, *Ship Resistance and Propulsion* (2011), printed
pp. 206, 208, 236, 495–498, gives the table normalization and digitized subset.
The user-supplied excerpt was inspected; it must not be distributed in the
release. Publisher identity: https://assets.cambridge.org/97805217/60522/frontmatter/9780521760522_frontmatter.pdf .

The primary historical source is Gertler's DTMB Report 806 (1954),
*A Reanalysis of the Original Test Data for the Taylor Standard Series*.
Its identity is recorded at https://trid.trb.org/View/394446 . Normal DTIC
and linked public access failed during this audit. Do not claim primary-page
verification. Published secondary naval-architecture texts support `L=LWL`;
the exact Report 806 definition remains a disclosed source gap.

- `CR = RR / (0.5 rho S V²)` is **residuary**, not solely wave, resistance.
- `S` is static hull wetted area, excluding separate appendage contributions.
- Molland's table is headed `CR × 1000`; cells must be divided by 1000.
- `CP=CB/CM` requires a declared `CM` if `CP` is not supplied. The parent-series
  `CM≈0.925` and an estimated target-hull `CM` are not interchangeable facts.
- Source length-volume axis is `L / volume^(1/3)`. The repository stores its
  reciprocal cube, `volume / LWL³`, in ascending order. Reverse the associated
  column data with the axis; a mere heading change is insufficient. This preserves
  nodes, not the interpolant: linear interpolation in reciprocal-cube coordinates
  differs from linear interpolation in the printed length-volume coordinate.
  The source-oriented mode uses the printed coordinate; the legacy transformed
  coordinate remains a named compatibility choice, with its method in the trace.
- The stored subset has `CP=.50–.80`, `Fr=.16–.58`, and source length-volume
  ratio `5.5–10`. The broader original-series range does not expand available
  table coverage. Breadth/draft coverage also follows the populated table.

Source headings `5.5,6,7,8,9,10` map to volume ratios
`1/5.5³,1/6³,1/7³,1/8³,1/9³,1/10³`. Assert this at algebraic tolerance `1e-10`.
Populated printed `CR×1000` cells have two decimal places, giving source
rounding tolerance `5e-6` in `CR`. Taylor wetted-area coefficient `CS` has
three decimals, giving `0.0005` absolute tolerance. `S=CS sqrt(volume L)`.

Strict table conformance requires all interpolation corners actually used by
the request to exist, and requires the request to lie inside the stored axes.
Exact nodes must not fail because unrelated zero-weight corners are absent.
Missing corners and outside-domain requests return unavailable with a
diagnostic. Legacy clipping or weight renormalization may remain only as a
separately named approximation with an explicit warning; it is not a
source-authorized extension of the table.

## Implicit Schoenherr reference

The official 8th ITTC proceedings, *Skin Friction and Turbulence Stimulation,
Formal Discussion*, printed p. 104, Table 2, supplies the convention
`0.242/sqrt(CF)=log10(Re CF)` and these rounded anchors:
https://ittc.info/media/3107/subjects-2-4-skin-friction-and-turbulence.pdf .
The official indexed table was readable; the large PDF exceeded the web
reader's full-file limit. This access limitation is retained in the audit.

| Re | CF |
|---:|---:|
| 1e5 | .007179 |
| 1e6 | .004409 |
| 5e6 | .003294 |
| 1e7 | .002934 |
| 1e8 | .002072 |
| 1e9 | .001531 |
| 1e10 | .001172 |

Use `5e-7` absolute tolerance, derived from the printed six decimal places.
Additionally verify the equation residual and the independent inverse
`Re=10^(.242/sqrt(CF))/CF` for chosen `CF` values at `1e-10` numerical tolerance.
Mathematical solvability at low Re does not establish turbulent-flow validity.

Molland's rounded `1/sqrt(CF)=4.13 log10(Re CF)` has a different constant:
`1/4.13` is not exactly `.242`. Do not use it to demand exact agreement with
the above table. Name the implemented convention.

The current `0.4631/(log10(Re))^2.6` is an explicit Conn approximation, not
the implicit solution. Preserve compatibility under an explicit method name
such as `conn_1953_schoenherr_approx`; add a distinct implicit method. A ship
roughness allowance such as `.0004` is a separate term, never part of CR or
quietly included in the pure friction coefficient.

## Independent checks required

1. Raw populated cell transcription, unavailable cells, and axis association.
2. Exact nodes and an independently chosen midpoint in the declared interpolation
   coordinate within fully populated cells; invalid cells
   and bounds remain visible. Approximation mode tested separately.
3. Implicit friction anchors, inverse identity, residual, finite-input guards.
4. Chosen table node force identity `RR=.5 rho S V² CR`, with declared fluid,
   speed conversion, hull area and coefficient. This is unit/normalization
   conformance, not validation against a measured ship trial.
5. Method, units, source gap, area estimate and roughness choice survive the
   coordinator, exports and user interface without being renamed as facts.

Neither original papers nor the supplied textbook excerpt are release assets.
