# Safe web action preconditions: browser.open_page URL scheme (WP-154, 2026-09-12)

## Status

Real, implemented. No ADR -- a new precondition check, not a new
capability/`Effect`/`Tier`, mirroring `kernel/files.py`'s own existing
`PathOutsideAllowedScopeError` precedent exactly.

## What was investigated

Whether `browser.open_page` (`kernel/browser.py`) validates its own
`url` argument before acting on it. **Real finding, confirmed by
direct inspection and a live reproduction, not assumed**: `url` was
passed completely unvalidated straight through to
`browser_automation.open_page(url)` -- a real, live check confirmed a
`file:///etc/passwd` URL is accepted exactly like any `https://` URL.

This matters specifically for `browser.open_page`, not for
`desktop.brave_open_url` (checked and deliberately left unchanged):
the former opens a **headless**, CDP-controlled page whose content can
then be pulled out programmatically via `browser.screenshot`/
`browser.inspect_dom` -- a `file://` URL would let a capability whose
entire tier/confirmation model is built around "browsing the web"
instead read arbitrary local filesystem content, and the human
confirming the `Tier.CONFIRM` prompt sees only a URL string, with no
way to notice the scheme is not actually a web address. `desktop.
brave_open_url` opens a real, visible desktop window under the human's
own ongoing control -- a fundamentally different, already-mitigated
risk shape.

The only real, live caller of `authorize_and_open_page` today is
`jarvis browser open <url>` (a human-typed, arbitrary string) --
`job_search.py`/`job_assistance.py`/`coding.py` only mention this
function in their own docstrings by analogy, none actually call it.

## What was built

`_require_web_scheme(url)` (`kernel/browser.py`), called at the very
top of `authorize_and_open_page`, **before** `build_default_registry()`
or any authorization attempt -- the identical "reject before any
`CapabilityInvocation` is constructed" pattern
`PathOutsideAllowedScopeError` already established, including its own
identical, explicitly-stated audit-trail limitation (a rejected URL is
not recorded in the chain). Only `http`/`https` schemes (checked
case-insensitively via `urllib.parse.urlsplit`) are accepted, plus one
explicit, narrow exception: the literal string `"about:blank"` --
already used by this module's own real, pre-existing,
skipif-guarded live test to avoid depending on a real external site's
availability, and genuinely inert (no filesystem access, no script
execution, no network reach), unlike `about:config`/
`about:net-internals`-style pages this check still wants to exclude.

A new `UnsupportedUrlSchemeError` (not a `JarvisError` subclass, same
reasoning as `PathOutsideAllowedScopeError`) is raised on rejection,
wired into `cli/main.py`'s existing broad except tuple for a clean
`Error: ...` message and exit code `1`, rather than a raw exception
propagating to the browser adapter.

## What was deliberately not built

- No change to `desktop.brave_open_url` or any other capability --
  scoped to the one, real, demonstrated risk.
- No content-based validation (e.g. blocking specific domains) --
  scheme-only, matching this codebase's own established
  allowlist-over-denylist posture (`fs.read_file`'s own docstring,
  quoted by ADR-0060).
- No automatic `browser.close_page` invocation, no idle timeout --
  unrelated to this precondition, already a separately-tracked, open
  gap (WP-143).

## Testing

Real, parametrized tests prove `file://`/`javascript:`/`data:`/
`ftp://`/a schemeless string are all rejected before any authorization
attempt (no audit record is written), that `http://`/`https://` (both
cases) are unaffected, and a real, unmocked CLI invocation
(`jarvis browser open file:///etc/passwd`) exits `1` with a clean
error rather than reaching the real adapter.
