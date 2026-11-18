# 12. The demo unpacks wheels directly and fetches Pyodide at build time

Status: Accepted

## Context

Record 10 says the demo page serves Pyodide and the wheels from its own origin, with a Content-Security-Policy of connect-src 'self'. Two questions were left open. How does the page install the ledgercheck and synthbiz wheels, and how do the Pyodide core files get into the Pages site without a CDN and without a large binary in git.

## Decision

The page installs wheels with fetch and pyodide.unpackArchive(buffer, "wheel"). It does not use micropip and does not call loadPackage. Both wheels are pure Python with no dependencies, so unpacking them into site-packages is all that is needed, and no request can go to PyPI or to the Pyodide package index.

scripts/build_site.py builds _site/ and nothing from Pyodide is committed. The script:

- downloads pyodide-core-314.0.8.tar.bz2 from the official Pyodide GitHub release into a gitignored cache folder,
- checks its sha256 against a constant in the script and stops on a mismatch,
- reads five files out of the archive by name (pyodide.js, pyodide.asm.mjs, pyodide.asm.wasm, python_stdlib.zip, pyodide-lock.json) and writes them as plain bytes,
- checks that pyodide.js has the sha384 that jsdelivr publishes for v314.0.8, an independent source of the same file,
- builds the ledgercheck wheel and the synthbiz wheel from the commit pinned in pyproject.toml,
- writes manifest.json with the wheel file names for the page.

Nothing from the download is run. It is hashed, read and copied.

The CSP is default-src 'none', script-src 'self' with 'wasm-unsafe-eval' and 'unsafe-eval', connect-src 'self', style-src 'self', img-src 'self' data:, base-uri 'none' and form-action 'none'. Both script keywords are needed: the page failed to start when 'unsafe-eval' was removed, and WebAssembly needs 'wasm-unsafe-eval'. There is no worker, so no worker-src.

Options considered:

- micropip with a local index. More code to serve, and it can still reach other hosts unless it is cut off.
- Commit the Pyodide files. A 13 MB binary in history for every upgrade, and a reviewer cannot tell what changed.
- Fetch at build time with a pinned sha256 (chosen). The repo stays small and a changed file fails the build.

## Consequences

The build needs network access to github.com and, for the synthbiz wheel, to the synthbiz repo. An upgrade of Pyodide changes the version, URL, sha256 and sha384 in one file. The Pages site is about 13.6 MB, mostly pyodide.asm.wasm (9.6 MB) and python_stdlib.zip (2.5 MB). Pyodide (MPL-2.0) and the CPython standard library (PSF License) are now shipped in the site, so THIRD_PARTY_NOTICES.md lists them. The browser test in CI fails on any request to a host other than the local server.
