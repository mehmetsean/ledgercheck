# Third-party notices

The ledgercheck code, docs and examples are all rights reserved, see LICENSE.
The parts below belong to other people and keep their own licenses.
None of them are copied into this repo or shipped in the ledgercheck package. The one exception is the demo site described below, which ships Pyodide and the CPython standard library.

## Runtime

ledgercheck has no runtime dependencies. It uses only the Python standard library.

## Optional extras

The eval extra installs synthbiz. The dev extra installs synthbiz and the other tools in the table below. They are used to make synthetic data, test and check the code only.

| Part | Version checked | License |
| --- | --- | --- |
| synthbiz (eval and dev extras) | 0.1.2 | All rights reserved, by the same author |
| pytest | 9.2.0 | MIT |
| pytest-cov | 7.1.0 | MIT |
| hypothesis | 6.170.15 | MPL-2.0 |
| ruff | 0.17.5 | MIT |
| mypy | 2.4.1 | MIT |

These packages pull in their own dependencies. Each keeps its own license.

## Demo site

The Pages site built by scripts/build_site.py serves these files from its own origin. They are downloaded at build time and are not committed to this repo.

| Part | Version | License |
| --- | --- | --- |
| Pyodide (pyodide.js, pyodide.asm.mjs, pyodide.asm.wasm, pyodide-lock.json) | 314.0.8 | MPL-2.0 |
| CPython standard library (python_stdlib.zip) | the version built into Pyodide 314.0.8 | PSF License |
| synthbiz wheel | the commit pinned in pyproject.toml | All rights reserved, by the same author |

Source and license texts are at https://github.com/pyodide/pyodide and https://docs.python.org/3/license.html. The browser test tool Playwright (Apache-2.0) is used in CI only and is not shipped.

## Build tool

The build backend is hatchling, as set in pyproject.toml. It keeps its own license.

To check a package license, install it and run `pip show <name>`, or read the License fields in its metadata.
