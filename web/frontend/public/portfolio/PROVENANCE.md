# Reference artwork

The three PNG sheets were supplied by the user for this portfolio on 2026-10-04:

- ship-plan-01.png: 1fd9fa6e3e59c33810b83d592c6f0445.png, 1000×451.
- ship-plan-02.png: fa34fa309156a46639b14f6711071f66.png, 1018×451.
- ship-plan-03.png: e0f79109169de78baa73c0505855ffc7.png, 1063×542.

This supersedes the earlier geometric redraw: `src/portfolio/VesselDrawing.tsx` now renders these PNGs faithfully. It nests an SVG whose viewBox is the reference band and places the whole original sheet as an `<image>` at its intrinsic pixel size, with a clipPath in source coordinates so nothing outside the band leaks in. Nothing is redrawn, traced, simplified or generated. Reference bands: 01 at y=290..451, 02 at y=290..451, 03 at y=360..542. The enhanced sheets replace the untouched scans in place; the original scans remain in Git history (see the 2026-10-05 note below).

Tone is themed with a restrained SVG filter: inverse luminance becomes alpha, a mild component transfer (per theme; light slope 1.2 / intercept -0.05, dark slope 1.08 / intercept -0.035) lifts mid ink and suppresses near-paper speckle, then ink color is flooded and composited in. The result bound to source alpha. Paper is transparent and the source's own gray fills are retained as proportionally lighter ink. No blur, morphology, convolution, edge detection or superresolution is applied; output is limited to the sheets' intrinsic resolution, and as any tonal threshold does, very faint marks may be attenuated.

2026-10-05 clarity pass: the archived PNGs were enhanced in place (same dimensions, same filenames) with conservative tonal processing only — paper normalized to white from the reference band's 99.7 percentile, ink deepened, sheet 02's deck fill lifted (median 147→184) and its scan grain smoothed inside the fill range only, sheet 03's fills harmonized, and a gentle unsharp mask (radius 1.0) applied. No redrawing, tracing, morphology or resampling; every original mark survives. The pre-enhancement bytes remain in Git history at commit `fc71434`; current checksums are in `docs/formfield/assets/source-sha256.csv`.

The one geometric element is a broad smooth hull approximation used solely as the decoration mask so construction lines do not cross the deck. It is never displayed and is not part of the reference.

Construction geometry is decorative composition, not measured naval engineering data. Reference sheets are visual studies for Plimsoll, not three separate tools or verified interchangeable Queen Mary plans.
