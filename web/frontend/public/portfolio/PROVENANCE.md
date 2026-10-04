# Reference artwork

The three untouched PNG sheets were supplied by the user for this portfolio on 2026-10-04:

- ship-plan-01.png: 1fd9fa6e3e59c33810b83d592c6f0445.png, 1000×451.
- ship-plan-02.png: fa34fa309156a46639b14f6711071f66.png, 1018×451.
- ship-plan-03.png: e0f79109169de78baa73c0505855ffc7.png, 1063×542.

This supersedes the earlier geometric redraw: `src/portfolio/VesselDrawing.tsx` now renders these PNGs faithfully. It nests an SVG whose viewBox is the reference band and places the whole original sheet as an `<image>` at its intrinsic pixel size, with a clipPath in source coordinates so nothing outside the band leaks in. Nothing is redrawn, traced, simplified or generated. Reference bands: 01 at y=290..451, 02 at y=290..451, 03 at y=360..542. The source PNGs remain byte-for-byte untouched and archived.

Tone is themed with a restrained SVG filter: inverse luminance becomes alpha, a mild component transfer (slope 1.08, intercept -0.035) lifts mid ink and suppresses near-paper speckle, then ink color is flooded and composited in. The result bound to source alpha. Paper is transparent and the source's own gray fills are retained as proportionally lighter ink. No blur, morphology, convolution, edge detection or superresolution is applied; output is limited to the sheets' intrinsic resolution, and as any tonal threshold does, very faint marks may be attenuated.

The one geometric element is a broad smooth hull approximation used solely as the decoration mask so construction lines do not cross the deck. It is never displayed and is not part of the reference.

Construction geometry is decorative composition, not measured naval engineering data. Reference sheets are visual studies for Plimsoll, not three separate tools or verified interchangeable Queen Mary plans.
