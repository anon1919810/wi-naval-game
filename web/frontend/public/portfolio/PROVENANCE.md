# Reference artwork

## Lossless WebP derivatives

On 2026-10-10 each of the three line sheets gained a **lossless WebP** derivative
alongside its PNG. The PNGs are the archival originals and are **unchanged**;
current checksums are in `docs/formfield/assets/source-sha256.csv` and the
original supplied files are named below.

| Sheet | PNG | WebP | WebP / PNG | Decoded pixels |
|---|---:|---:|---:|---|
| ship-plan-01 | 235,564 B | 96,662 B | 0.410 | identical |
| ship-plan-02 | 344,997 B | 145,820 B | 0.423 | identical |
| ship-plan-03 | 314,169 B | 133,054 B | 0.424 | identical |

Generated with Pillow's bundled WebP encoder as `lossless=True, quality=100,
method=6, exact=True`. **Nothing is redrawn, resampled, re-toned or cropped**:
the decoded RGB pixel buffer of each WebP was compared against the PNG's and is
byte-for-byte identical, at the same intrinsic dimensions. These are the same
scans in a smaller container, not new artwork — roughly 58% less to fetch for the
same image.

`src/portfolio/plans.ts` points its `href` at the WebP; the crop metadata, the
source coordinates and the tonal profiles are unchanged, because none of them
depend on the file format.

## Report screenshot

Retired from the project detail on 2026-10-07. The screenshot and its caption are no longer rendered, and the `REPORT_IMAGE` constant has been removed. The original asset remains unchanged as historical evidence; the paragraph below records its original use.

`plimsoll-report.jpg` is a byte-for-byte copy of `docs/plimsoll-1.0/evidence/public-report-2026-10-04.jpg` (41094 bytes, 856×751, SHA-256 `790e2a70c02a44e26a1566bca0e49b24fc52e391bf6d1ea5df9150853cf25e61`), made on 2026-10-05 for the work detail page. It is a real screenshot of a real report from the public deployment, taken during the 2026-10-04 launch acceptance. It carries no credentials, tokens or personal data: the visible content is the report header, the display-unit selectors and a hull section outline. Nothing is redrawn, retouched or cropped. Its page caption carries no file paths; this file and the constant in `src/portfolio/ProjectDetail.tsx` are the provenance.

## Line sheets

The three PNG sheets were supplied by the user for this portfolio on 2026-10-04:

- ship-plan-01.png: 1fd9fa6e3e59c33810b83d592c6f0445.png, 1000×451.
- ship-plan-02.png: fa34fa309156a46639b14f6711071f66.png, 1018×451.
- ship-plan-03.png: e0f79109169de78baa73c0505855ffc7.png, 1063×542.

This supersedes the earlier geometric redraw: `src/portfolio/VesselDrawing.tsx` now renders these PNGs faithfully. It nests an SVG whose viewBox is the reference band and places the whole original sheet as an `<image>` at its intrinsic pixel size, with a clipPath in source coordinates so nothing outside the band leaks in. Nothing is redrawn, traced, simplified or generated. Reference bands: 01 at y=290..451, 02 at y=290..451, 03 at y=360..542. The enhanced sheets replace the untouched scans in place; the original scans remain in Git history (see the 2026-10-05 note below).

Tone is themed with a restrained SVG filter: inverse luminance becomes alpha, one per-sheet/per-theme gamma function (amplitude · density ^ exponent + offset; sheet 01 unchanged at 1.2 / -0.05 light and 1.08 / -0.035 dark, sheets 02 and 03 eased so their dense deck hatch and flat gray fills read with the same hierarchy) settles the mid ink and suppresses near-paper speckle, then ink color is flooded and composited in. The result is bound to source alpha. Paper is transparent and the source's own gray fills are retained as proportionally lighter ink. No blur, morphology, convolution, edge detection or superresolution is applied; output is limited to the sheets' intrinsic resolution, so enlarging the rendered artwork only enlarges existing pixels, and as any tonal threshold does, very faint marks may be attenuated.

2026-10-05 clarity pass: the archived PNGs were enhanced in place (same dimensions, same filenames) with conservative tonal processing only — paper normalized to white from the reference band's 99.7 percentile, ink deepened, sheet 02's deck fill lifted (median 147→184) and its scan grain smoothed inside the fill range only, sheet 03's fills harmonized, and a gentle unsharp mask (radius 1.0) applied. No redrawing, tracing, morphology or resampling; every original mark survives. The pre-enhancement bytes remain in Git history at commit `fc71434`; current checksums are in `docs/formfield/assets/source-sha256.csv`.

The one geometric element is a broad smooth hull approximation used solely as the decoration mask so construction lines do not cross the deck. It is never displayed and is not part of the reference.

Construction geometry is decorative composition, not measured naval engineering data. Reference sheets are visual studies for Plimsoll, not three separate tools or verified interchangeable Queen Mary plans.
