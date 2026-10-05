# Self-hosted fonts

## archivo-latin-var.woff2

- **Family**: Archivo, Omnibus-Type (Omnibus Type / Ângelo Dibensedetto, Pablo Cosgaya, Andrés Torresi).
- **Axes kept**: `wght` 400–900 (variable), `wdth` fixed at 100% (normal width), upright only. No italic file is shipped; no italic is requested.
- **Format**: WOFF2, Latin subset only (`unicode-range` in `src/styles/tokens.css` matches the Google Fonts `latin` block exactly).
- **Size**: 34,928 bytes (34.1 KiB), variable `wght` 400–900.
- **SHA-256**: `8f704806dbedeaaeca334b11ec348bc3ac3a439d6431544b3afb54f534ee4967`
- **Licence**: SIL Open Font License 1.1, Copyright 2020 The Archivo Project Authors. Full text alongside the file as `Archivo-OFL.txt` (4,388 bytes, SHA-256 `108b4e57c9c796d3d38d0428ca7ee39de47ad93187302718d9b2d8864b9b716b`). OFL permits self-hosting and bundling with an application; the reserved Font Name rules mean the family is **not** renamed and this file is not sold on its own.
- **Official sources**
  - Project: <https://www.omnibus-type.com/fonts/archivo/>
  - Source repository and licence: <https://github.com/Omnibus-Type/Archivo>
  - Binary fetched through the official Google Fonts CSS API v2, `https://fonts.googleapis.com/css2?family=Archivo:wght@400..900&display=swap`, whose Latin block resolves to `https://fonts.gstatic.com/s/archivo/v25/k3kPo8UDI-1M0wlSV9XAw6lQkqWY8Q82sLydOxI.woff2` (Google Fonts serves Omnibus-Type's official binaries).
- **Why one subset**: the public shell and the workbench UI are English/Latin with Chinese text falling through to the system CJK sans already in `--font-sans`. Shipping only the Latin subset keeps one small file instead of three, and avoids a multi-megabyte CJK webfont that the project deliberately does not host.

### Loading

`<link rel="preload" as="font" type="font/woff2" crossorigin>` in `index.html` (the preload is cross-origin-safe because the file is same-origin and `crossorigin` is present), `@font-face` with `font-display: swap` in `src/styles/tokens.css`. Text is always legible in the fallback stack before the variable font arrives; no layout depends on the download.