"""Contract test: adapters must structurally satisfy jarvis.ports.secret.SecretPort."""

from __future__ import annotations

from jarvis.adapters.secret import SecretServiceAdapter
from jarvis.ports.secret import SecretPort


def test_secret_service_adapter_satisfies_secret_port() -> None:
    """SecretServiceAdapter is structurally a SecretPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores a callable), so this needs no D-Bus connection.
    """
    adapter = SecretServiceAdapter()

    assert isinstance(adapter, SecretPort)


def test_an_object_missing_get_secret_does_not_satisfy_secret_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotASecretSource:
        """Deliberately lacks get_secret()."""

    assert isinstance(NotASecretSource(), SecretPort) is False
