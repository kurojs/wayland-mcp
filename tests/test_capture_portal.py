"""The portal capture backend gets the cursor from the ScreenCast stream when it can.

Headless like the rest of the suite: the stream grab and the Screenshot portal call
are replaced by recorders, so what is under test is the choice between them and the
fallback, not GStreamer or D-Bus.
"""
import pytest

from wayland_mcp import screen_utils
from wayland_mcp.backends import capture_portal, portal
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


def backend_for(caps, recorder):
    backend = PortalScreenshotBackend()
    assert backend.supports(caps)
    backend._capture_stream_frame = recorder.stream  # pylint: disable=protected-access
    backend._screenshot = recorder.screenshot  # pylint: disable=protected-access
    return backend


def test_the_cursor_comes_from_the_stream(gst_present):
    recorder = Recorder()
    result = backend_for(gnome(), recorder).capture("shot.png")
    assert recorder.calls == ["stream"]
    assert result == {"success": True, "filename": "shot.png", "cursor": True}


def test_without_the_cursor_the_screenshot_portal_is_used(gst_present):
    recorder = Recorder()
    result = backend_for(gnome(), recorder).capture("shot.png", include_mouse=False)
    assert recorder.calls == ["screenshot"]
    assert result["cursor"] is False


def test_no_stream_without_a_remote_desktop_portal(gst_present):
    """xdg-desktop-portal-wlr offers ScreenCast but no RemoteDesktop session to use."""
    caps = gnome()
    caps.dbus_interfaces.discard(IFACE_REMOTE_DESKTOP)
    recorder = Recorder()
    backend_for(caps, recorder).capture("shot.png")
    assert recorder.calls == ["screenshot"]


def test_no_stream_without_a_screencast_portal(gst_present):
    caps = gnome()
    caps.dbus_interfaces.discard(IFACE_SCREENCAST)
    recorder = Recorder()
    backend_for(caps, recorder).capture("shot.png")
    assert recorder.calls == ["screenshot"]


def test_no_stream_without_pipewiresrc(monkeypatch):
    monkeypatch.setattr(capture_portal, "_gst", lambda: None)
    recorder = Recorder()
    backend_for(gnome(), recorder).capture("shot.png")
    assert recorder.calls == ["screenshot"]


def test_a_failed_stream_falls_back_and_is_not_reopened(gst_present):
    """The likeliest failure is the user stopping the share; reopening would undo it."""
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


def test_a_refused_session_only_costs_the_cursor_of_that_capture(gst_present):
    """GNOME refuses sessions while the screen is locked; that passes, so retry."""
    recorder = Recorder(stream_error=SessionRefused("locked"))
    backend = backend_for(gnome(), recorder)
    backend.capture("a.png")
    backend.capture("b.png")
    assert recorder.calls == ["stream", "screenshot", "stream", "screenshot"]


def test_a_pipeline_error_falls_back_too(gst_present):
    """GLib.Error derives from RuntimeError; a bare one stands in for it here."""
    recorder = Recorder(stream_error=RuntimeError("could not link pipewiresrc"))
    result = backend_for(gnome(), recorder).capture("shot.png")
    assert recorder.calls == ["stream", "screenshot"]
    assert result["cursor"] is False


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
