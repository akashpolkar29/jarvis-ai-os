"""Policy engine: the single choke point for authorizing capability effects.

Every capability invocation declares its effects (``READ_LOCAL``,
``WRITE_LOCAL``, ``DESTRUCTIVE``, ``IRREVERSIBLE``, ``CREDENTIAL``,
``EGRESS_SENSITIVE``, and so on). This subpackage evaluates those effects
against the current policy tier (``ALLOW`` / ``CONFIRM`` /
``MANUAL_ONLY`` / ``DENY``) and the provenance of the data involved. This
is the only place in the codebase that makes that decision — there is no
command blocklist anywhere else.

This is currently an empty stub: the coverage gate for this package is
wired up in CI (``--fail-under=0`` for now) so that the reporting path
itself is exercised before the policy engine has any code in it. The
actual engine arrives in a later work package.
"""
