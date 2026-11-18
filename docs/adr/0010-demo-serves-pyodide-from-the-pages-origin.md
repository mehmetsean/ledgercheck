# 10. The demo serves Pyodide and the wheels from its own origin

Status: Accepted. Built. See docs/adr/0012-demo-unpacks-wheels-and-fetches-pyodide-at-build-time.md for how the files get into the site.

## Context

The demo page has a mode where a user chooses their own CSV files. Those files may be real client files. A page that loads scripts or wheels from a CDN, or can send requests to any host, makes it hard to show that file contents stay in the browser.

## Decision

The page serves Pyodide core files and the ledgercheck and synthbiz wheels from the Pages origin, not from a CDN. Its Content-Security-Policy sets connect-src 'self'. The File API reads files in the page, and nothing is uploaded. A stdlib-only wheel needs only the Pyodide core files. The browser test is to fail on any request to another host.

Options considered:

- Pyodide from a CDN with a pinned version and an integrity hash. Smaller repo, but a request to another host is allowed and the files after the first script are not pinned.
- Same origin files (chosen). Larger Pages site, one origin to check.

## Consequences

Upgrading Pyodide means changing the version, the URL, the sha256 and the sha384 in scripts/build_site.py. The built site is about 13.6 MB. Check with du -sh _site after python scripts/build_site.py. The Pages size limit and the load time on a phone are open risks. If the core files are too large, a pinned CDN is the fallback, and a new record must say why.
