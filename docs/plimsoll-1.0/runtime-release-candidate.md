# Windows release runtime candidate

Preparation recorded 2026-09-22. No release has been built or accepted yet.

Use the official CPython Windows embeddable distribution as the release
candidate. This replaces the earlier proposal to curate the developer's custom
Workbuddy runtime, whose directory name and some dependency versions could not
establish a reproducible binary source. Development test evidence remains tied
to its captured Python 3.13.14 executable and must not be relabelled.

The [official Python 3.13.15 release page](https://www.python.org/downloads/release/python-31315/)
provides the AMD64 embeddable ZIP, SHA-256, software bill of materials and
Sigstore bundle. Staying on the 3.13 maintenance line avoids a feature-series
migration; the release still needs its own complete regression and workflow
acceptance on the actual bundled runtime.

| Candidate asset | Downloaded size | SHA-256 |
|---|---:|---|
| `python-3.13.15-embed-amd64.zip` | 11,009,825 bytes | `d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf` |
| matching `.spdx.json` | 15,341 bytes | `ba428f93acb06764f0005246f8ca48bb1c04feef64ce7db0b177fb2fd371c423` |
| matching `.sigstore` | 7,164 bytes | `3e487c064a40d94a59476eb05e2d6225c325665590797e0a03cd33592b617137` |

The archive digest matches the published release-page digest. The signature
bundle was retained but has not been independently verified with Sigstore.
TLS verification remained enabled during download. PowerShell's HTTP client
failed TLS negotiation; Python's standard urllib client succeeded without
certificate-validation overrides.

Archive inspection, without executing its binaries, found 34 distribution
entries and 541 standard-library entries. The standard-library ZIP includes
`unittest`, `multiprocessing`, `http.server`, `json` and `hashlib`; this is an
inventory, not import or application acceptance. The official archive's
`LICENSE.txt` was preserved verbatim. Its bundled dependency versions must
come from this distribution's records, not the custom development runtime.
The SPDX document can include source components not actually shipped in this
Windows archive; final binary inventory and notice mapping must distinguish
them.

## Isolated candidate smoke check

The unmodified 34-file archive was subsequently extracted into a dedicated
Chinese-named scratch directory and executed with isolated mode and UTF-8 enabled.
It reports Python 3.13.15, OpenSSL 3.0.21, SQLite 3.50.4 and Expat 2.8.2.
The executable SHA-256 is
`85b71d8c6ec1905935f74be0c9869aae198d00e98f39df699ec66f9c5a84cecd`.
All original archive file hashes remained unchanged; `sys.path` contained only
that runtime directory and its own standard-library ZIP.

The probe imported the required standard-library families, received a 200 KB
result from a spawned child before joining it, terminated and reaped an owned
worker, and saved/reopened UTF-8 JSON through atomic replacement. It did not
exercise Plimsoll, browser interactions, application cancellation or performance.
The raw report and probe hash are preserved in scratch `runtime-smoke.json`;
application acceptance must still use the actual built release.

Pinned upstream notice bytes for CPython 3.13.15, OpenSSL 3.0.21, Expat 2.8.2,
XZ 5.2.5, mpdecimal 4.0.0 and zlib 1.3.1 were fetched with normal TLS verification.
Their source URLs, Git blob IDs and SHA-256 digests are retained in the candidate's
`notices/sources.json`. These are preparation inputs; matching every shipped
component and preserving its applicable notices remains a packaging requirement.

## Packaging direction and remaining checks

- Prefer preserving this small official embeddable distribution, its license
  and its matched component notices over manually pruning standard-library
  dependencies. Do not add developer `site-packages`, tools or absolute paths.
- Configure only the documented application search path/launcher needed for
  the packaged Plimsoll module. Record changes to `python313._pth`; keep
  interpreter binaries unchanged and retain their file hashes.
- Audit the actual packaged dependency/notice set, including the matched
  CPython incorporated-software notice text. Do not reuse a 3.13.14 dependency
  notice merely because it was downloaded earlier; check its actual version.
- Test the package from a clean working directory and a Chinese path without
  developer PYTHONPATH or installed Python. Exercise real process spawn,
  cancellation, SHA-256, save/reopen, all numerical tests and browser workflows.
- Record actual release-runtime version, binary hashes, output identities,
  measured timings and offline behavior separately from development evidence.

During development the downloaded source assets and read-only inventory are in
this plan's ignored `runtime-official-3.13.15` scratch directory. The packager
must preserve the required artifacts in the reproducible release inputs and
notices before the development scratch directory is removed.
