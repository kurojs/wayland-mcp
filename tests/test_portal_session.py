"""When the RemoteDesktop session fails to open, the stored permission is kept or dropped.

A stale restore token should be forgotten so the user is asked again. A session
the portal refuses to create at all -- GNOME does that while the screen is locked
-- has nothing to do with the token, and must not cost the user their permission.
"""
import pytest

from wayland_mcp.backends import input_portal, portal
from wayland_mcp.backends.input_portal import PortalRemoteDesktopBackend, SessionRefused


@pytest.fixture
def stored_token(monkeypatch, tmp_path):
    """A stored token at a temporary path, so the real one is never touched."""
    path = tmp_path / "remote-desktop-token"
    path.write_text("stored-token")
    monkeypatch.setenv(input_portal.ENV_TOKEN_PATH, str(path))
    monkeypatch.delenv(input_portal.ENV_NO_PERSIST, raising=False)
    return path


def backend_whose_session_fails_with(*errors):
    """A backend whose _open_session raises *errors* in turn, then succeeds."""
    backend = PortalRemoteDesktopBackend()
    pending = list(errors)
    attempts = []

    def open_session():
        attempts.append(backend._restore_token)  # pylint: disable=protected-access
        if pending:
            raise pending.pop(0)
        backend._handle = "/session"  # pylint: disable=protected-access

    backend._open_session = open_session  # pylint: disable=protected-access
    return backend, attempts


def test_a_refused_session_keeps_the_stored_token(stored_token):
    backend, attempts = backend_whose_session_fails_with(SessionRefused("locked"))
    with pytest.raises(SessionRefused):
        backend._ensure_session()  # pylint: disable=protected-access
    assert attempts == ["stored-token"]
    assert stored_token.read_text() == "stored-token"


def test_a_rejected_token_is_forgotten_and_the_user_asked_again(stored_token):
    backend, attempts = backend_whose_session_fails_with(portal.PortalError("bad token"))
    backend._ensure_session()  # pylint: disable=protected-access
    assert attempts == ["stored-token", None]
    assert not stored_token.exists()


def test_a_caller_that_may_not_prompt_keeps_the_token(stored_token):
    """A capture gets the refusal instead of a dialog, and the token survives."""
    backend = PortalRemoteDesktopBackend(allow_prompt=False)
    attempts = []

    def open_session():
        attempts.append(backend._restore_token)  # pylint: disable=protected-access
        raise portal.PortalError("bad token")

    backend._open_session = open_session  # pylint: disable=protected-access
    with pytest.raises(portal.PortalError):
        backend._ensure_session()  # pylint: disable=protected-access
    # One attempt only: a second, tokenless one is what would raise the dialog.
    assert attempts == ["stored-token"]
    assert stored_token.read_text() == "stored-token"


def test_a_failed_create_session_is_reported_as_refused(stored_token, monkeypatch):
    pytest.importorskip("gi.repository.GLib")

    class RefusingSession:
        def request(self, _interface, method, *_args, **_kwargs):
            assert method == "CreateSession"
            raise portal.PortalError("CreateSession ended with portal response code 2")

    monkeypatch.setattr(portal, "PortalSession", RefusingSession)
    with pytest.raises(SessionRefused):
        PortalRemoteDesktopBackend()._ensure_session()  # pylint: disable=protected-access
    assert stored_token.read_text() == "stored-token"
