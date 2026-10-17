"""The portal capture backend gets the cursor from the ScreenCast stream when it can.

Headless like the rest of the suite: the stream grab and the Screenshot portal call
are replaced by recorders, so what is under test is the choice between them and the
fallback, not GStreamer or D-Bus.
"""
import pytest

from wayland_mcp import screen_utils
from wayland_mcp.backends import capture_portal, input_portal, portal
from wayland_mcp.backends.base import (
    Capabilities,
    IFACE_REMOTE_DESKTOP,
    IFACE_SCREENCAST,
    IFACE_SCREENSHOT,
)
from wayland_mcp.backends.capture_portal import PortalScreenshotBackend
from wayland_mcp.backends.input_portal import PortalRemoteDesktopBackend, SessionRefused


def gnome() -> Capabilities:
    """GNOME with no capture tool installed, so the portal backend is the one in use."""
    return Capabilities(
        dbus_interfaces={IFACE_SCREENSHOT, IFACE_REMOTE_DESKTOP, IFACE_SCREENCAST},
        wayland_display="wayland-0",
        has_gi=True,
    )


class Recorder:
    """Stands in for both capture paths and records which one ran."""

    def __init__(self, stream_error=None):
        self.calls = []
        self.stream_error = stream_error

    def stream(self, _output_path):
        self.calls.append("stream")
        if self.stream_error:
            raise self.stream_error

    def screenshot(self, output_path):
        self.calls.append("screenshot")
        return {"success": True, "filename": output_path, "cursor": False}


class FakeRemote:
    """A RemoteDesktop session that only records being closed."""

    closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def gst_present(monkeypatch):
    monkeypatch.setattr(capture_portal, "_gst", object)


@pytest.fixture(autouse=True)
def cursor_stream_unset(monkeypatch):
    """Start every test here from the unset default, whatever the shell says."""
    monkeypatch.delenv(capture_portal.ENV_CURSOR_STREAM, raising=False)


@pytest.fixture
def stored_permission(monkeypatch, tmp_path):
    """A stored portal permission, so the stream path is the one in use."""
    path = tmp_path / "remote-desktop-token"
    path.write_text("stored-token")
    monkeypatch.setenv(input_portal.ENV_TOKEN_PATH, str(path))
    monkeypatch.delenv(input_portal.ENV_NO_PERSIST, raising=False)
    return path


def backend_for(caps, recorder):
    backend = PortalScreenshotBackend()
    assert backend.supports(caps)
    backend._capture_stream_frame = recorder.stream  # pylint: disable=protected-access
    backend._screenshot = recorder.screenshot  # pylint: disable=protected-access
    return backend


def test_the_cursor_comes_from_the_stream(stored_permission, gst_present):
    recorder = Recorder()
    result = backend_for(gnome(), recorder).capture("shot.png")
    assert recorder.calls == ["stream"]
    assert result == {"success": True, "filename": "shot.png", "cursor": True}


def test_without_the_cursor_the_screenshot_portal_is_used(gst_present):
    recorder = Recorder()
    result = backend_for(gnome(), recorder).capture("shot.png", include_mouse=False)
    assert recorder.calls == ["screenshot"]
    assert result["cursor"] is False


def test_no_stream_without_a_remote_desktop_portal(stored_permission, gst_present):
    """xdg-desktop-portal-wlr offers ScreenCast but no RemoteDesktop session to use."""
    caps = gnome()
    caps.dbus_interfaces.discard(IFACE_REMOTE_DESKTOP)
    recorder = Recorder()
    backend_for(caps, recorder).capture("shot.png")
    assert recorder.calls == ["screenshot"]


def test_no_stream_without_a_screencast_portal(stored_permission, gst_present):
    caps = gnome()
    caps.dbus_interfaces.discard(IFACE_SCREENCAST)
    recorder = Recorder()
    backend_for(caps, recorder).capture("shot.png")
    assert recorder.calls == ["screenshot"]


def test_no_stream_without_pipewiresrc(monkeypatch, stored_permission):
    monkeypatch.setattr(capture_portal, "_gst", lambda: None)
    recorder = Recorder()
    backend_for(gnome(), recorder).capture("shot.png")
    assert recorder.calls == ["screenshot"]


def test_no_stream_without_a_stored_permission(monkeypatch, gst_present):
    """No permission means no session is built, not merely that its write is skipped.

    Opening one is what raises the remote-control dialog, and a screenshot is not
    worth a dialog or the permission behind it.
    """
    monkeypatch.setenv(input_portal.ENV_NO_PERSIST, "1")  # do not read the real token
    recorder = Recorder()
    backend = backend_for(gnome(), recorder)
    result = backend.capture("shot.png")
    assert recorder.calls == ["screenshot"]
    assert backend._remote is None  # pylint: disable=protected-access
    assert result["cursor"] is False


def test_the_stream_can_be_forced_without_a_permission(monkeypatch, gst_present):
    """WAYLAND_MCP_CURSOR_STREAM=1 asks for the stream anyway, dialog and all."""
    monkeypatch.setenv(input_portal.ENV_NO_PERSIST, "1")
    monkeypatch.setenv(capture_portal.ENV_CURSOR_STREAM, "1")
    recorder = Recorder()
    result = backend_for(gnome(), recorder).capture("shot.png")
    assert recorder.calls == ["stream"]
    assert result["cursor"] is True


def test_the_stream_can_be_turned_off(monkeypatch, stored_permission, gst_present):
    """=0 keeps the Screenshot portal even where the stream would work."""
    monkeypatch.setenv(capture_portal.ENV_CURSOR_STREAM, "0")
    recorder = Recorder()
    backend_for(gnome(), recorder).capture("shot.png")
    assert recorder.calls == ["screenshot"]


def test_a_capture_may_not_prompt_for_permission(monkeypatch, stored_permission, gst_present):
    """A capture reuses a permission already granted; it may not ask for one."""
    built = []

    class RecordingRemote:
        """Records how the capture backend built its RemoteDesktop session."""

        def __init__(self, **kwargs):
            built.append(kwargs)

        def supports(self, _caps):
            return True

        def open_stream(self):
            raise RuntimeError("stop before GStreamer")

        def close(self):
            pass

    monkeypatch.setattr(capture_portal, "PortalRemoteDesktopBackend", RecordingRemote)
    recorder = Recorder()
    backend = PortalScreenshotBackend()
    assert backend.supports(gnome())
    backend._screenshot = recorder.screenshot  # pylint: disable=protected-access

    backend.capture("shot.png")

    assert built == [{"allow_prompt": False}]
    assert recorder.calls == ["screenshot"]


def test_a_failed_stream_falls_back_and_is_not_reopened(stored_permission, gst_present):
    """The stream stays off for the cooldown, so the stopped share is not reopened."""
    recorder = Recorder(stream_error=portal.PortalError("session closed"))
    backend = backend_for(gnome(), recorder)
    remote = FakeRemote()
    backend._remote = remote  # pylint: disable=protected-access

    first = backend.capture("a.png")
    second = backend.capture("b.png")

    assert recorder.calls == ["stream", "screenshot", "screenshot"]
    assert first == {"success": True, "filename": "a.png", "cursor": False}
    assert second["cursor"] is False
    assert remote.closed
    assert backend._remote is None  # pylint: disable=protected-access


def test_a_refused_session_only_costs_the_cursor_of_that_capture(stored_permission,
                                                                 gst_present):
    """GNOME refuses sessions while the screen is locked; that passes, so retry."""
    recorder = Recorder(stream_error=SessionRefused("locked"))
    backend = backend_for(gnome(), recorder)
    backend.capture("a.png")
    backend.capture("b.png")
    assert recorder.calls == ["stream", "screenshot", "stream", "screenshot"]


def test_a_pipeline_error_falls_back_too(stored_permission, gst_present):
    """GLib.Error derives from RuntimeError; a bare one stands in for it here."""
    recorder = Recorder(stream_error=RuntimeError("could not link pipewiresrc"))
    result = backend_for(gnome(), recorder).capture("shot.png")
    assert recorder.calls == ["stream", "screenshot"]
    assert result["cursor"] is False


def test_the_stream_is_tried_again_after_the_cooldown(monkeypatch, stored_permission,
                                                      gst_present):
    """The cooldown ends: a later capture does try the stream again."""
    now = [1000.0]
    monkeypatch.setattr(capture_portal.time, "monotonic", lambda: now[0])
    recorder = Recorder(stream_error=portal.PortalError("session closed"))
    backend = backend_for(gnome(), recorder)

    backend.capture("a.png")
    backend.capture("b.png")
    assert recorder.calls == ["stream", "screenshot", "screenshot"]

    # A few minutes on, from a literal rather than the constant: what matters is
    # that the pause is short on a human's clock, so a cooldown long enough to read
    # as "no cursor until restart" has to fail here.
    now[0] += 300
    backend.capture("c.png")
    assert recorder.calls == ["stream", "screenshot", "screenshot", "stream", "screenshot"]


def test_close_drops_the_stream_session(stored_permission, gst_present):
    """The session does not outlive the backend that opened it."""
    recorder = Recorder()
    backend = backend_for(gnome(), recorder)
    remote = FakeRemote()
    backend._remote = remote  # pylint: disable=protected-access

    assert backend.capture("shot.png")["cursor"] is True
    backend.close()

    assert remote.closed
    assert backend._remote is None  # pylint: disable=protected-access


def test_open_stream_refuses_a_session_without_a_stream(monkeypatch):
    monkeypatch.setenv("WAYLAND_MCP_NO_PERSIST", "1")  # do not read the real token
    remote = PortalRemoteDesktopBackend()
    remote._handle = "/org/freedesktop/portal/desktop/session/1/x"  # pylint: disable=protected-access
    with pytest.raises(portal.PortalError):
        remote.open_stream()


def test_screen_controller_reports_whether_the_cursor_is_drawn(monkeypatch):
    def fake_capture(filename, include_mouse=True):
        return {"success": True, "filename": filename, "backend": "portal",
                "cursor": include_mouse}

    monkeypatch.setattr(screen_utils, "capture_func", fake_capture)
    monkeypatch.setattr(screen_utils, "add_rulers", lambda filename: filename)
    controller = screen_utils.ScreenController()
    assert controller.capture("shot.png")["cursor"] is True
    assert controller.capture("shot.png", include_mouse=False)["cursor"] is False
