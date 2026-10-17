"""Capture via org.freedesktop.portal.Screenshot.

The universal fallback: implemented by GNOME, KDE, COSMIC and
xdg-desktop-portal-wlr alike, and needs no privilege. The cost is a permission
prompt the first time, and on some desktops an interactive picker -- which is why
this sits below the native tools rather than above them.

The Screenshot portal has no cursor option, and GNOME leaves the pointer out. So
when the cursor is wanted, the frame comes instead from a RemoteDesktop session's
ScreenCast stream, which is requested with an embedded cursor. That session reuses
the input backend's restore token, so where the desktop honours it there is no
extra prompt. It needs GStreamer's pipewiresrc; without it, or if the stream
fails, capture falls back to the Screenshot portal and reports ``cursor: False``.
"""
import logging
import os
import shutil

from wayland_mcp.backends.base import (
    IFACE_REMOTE_DESKTOP,
    IFACE_SCREENCAST,
    IFACE_SCREENSHOT,
    Capabilities,
    CaptureBackend,
)
from wayland_mcp.backends import portal
from wayland_mcp.backends.input_portal import PortalRemoteDesktopBackend, SessionRefused

#: How long to wait for the stream's first frame, in seconds.
STREAM_FRAME_TIMEOUT = 5


def _gst():
    """GStreamer, initialised, when it has a PipeWire source; otherwise None."""
    try:
        import gi  # pylint: disable=import-outside-toplevel

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst  # pylint: disable=import-outside-toplevel
    except (ImportError, ValueError):
        return None
    if not Gst.is_initialized():
        Gst.init(None)
    if Gst.ElementFactory.find("pipewiresrc") is None:
        return None
    return Gst


class PortalScreenshotBackend(CaptureBackend):
    """`org.freedesktop.portal.Screenshot.Screenshot`, interactive=false."""

    name = "portal"
    priority = 20
    requires = (
        "a running XDG desktop portal exposing org.freedesktop.portal.Screenshot, "
        "plus PyGObject (install the 'portal' extra, or python3-gi)"
    )

    def __init__(self):
        self._caps = None
        self._remote = None
        self._stream_failed = False

    def supports(self, caps: Capabilities) -> bool:
        self._caps = caps
        return IFACE_SCREENSHOT in caps.dbus_interfaces and caps.has_gi

    def capture(self, output_path, mode="auto", geometry=None, include_mouse=True) -> dict:
        if include_mouse and self._can_stream():
            try:
                self._capture_stream_frame(output_path)
                logging.info("portal stream captured to %s", output_path)
                return {"success": True, "filename": output_path, "cursor": True}
            except SessionRefused as err:
                # Typically a locked screen, which passes: try the stream again next
                # time rather than giving up on the cursor for good.
                logging.info("No stream session (%s); capturing without the cursor", err)
                self._drop_remote()
            except RuntimeError as err:  # PortalError and GLib.Error are both RuntimeErrors
                # Do not reopen the session on the next capture: the likeliest cause
                # is the user stopping the share, and a silent restart would undo
                # that. A server restart tries again.
                logging.warning(
                    "Stream capture failed (%s); using the Screenshot portal, "
                    "without the cursor, from now on", err,
                )
                self._stream_failed = True
                self._drop_remote()
        return self._screenshot(output_path)

    def _screenshot(self, output_path) -> dict:
        """One `Screenshot` portal call. GNOME leaves the cursor out of these."""
        from gi.repository import GLib  # pylint: disable=import-outside-toplevel

        handle_token = portal.token()
        options = {
            "handle_token": GLib.Variant("s", handle_token),
            # Non-interactive: no picker, no modal. A desktop that insists on
            # interaction will still show one; that is its prerogative.
            "interactive": GLib.Variant("b", False),
            "modal": GLib.Variant("b", False),
        }
        portal.log_permission_hint("Screen capture")
        try:
            session = portal.PortalSession()
            results = session.request(
                IFACE_SCREENSHOT,
                "Screenshot",
                GLib.Variant("(sa{sv})", ("", options)),
                handle_token,
                timeout_ms=120000,  # a permission dialog may be waiting on a human
            )
        except portal.PortalError as err:
            return {"success": False, "error": str(err)}

        uri = results.get("uri")
        if not uri:
            return {"success": False, "error": "portal returned no screenshot URI"}
        source = portal.uri_to_path(uri)
        if not os.path.isfile(source):
            return {"success": False, "error": f"portal reported {source}, which is missing"}
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
        # The portal writes into its own cache; move so repeated captures do not
        # pile up there.
        shutil.move(source, output_path)
        logging.info("portal captured to %s", output_path)
        return {"success": True, "filename": output_path, "cursor": False}

    # -- stream capture ----------------------------------------------------

    def _can_stream(self) -> bool:
        if self._stream_failed or self._caps is None:
            return False
        interfaces = self._caps.dbus_interfaces
        if IFACE_REMOTE_DESKTOP not in interfaces or IFACE_SCREENCAST not in interfaces:
            return False
        return _gst() is not None

    def _capture_stream_frame(self, output_path):
        """Write one frame of the session's screen stream to *output_path* as PNG."""
        Gst = _gst()  # pylint: disable=invalid-name
        if self._remote is None:
            # Created on first use, so it loads the newest restore token: the input
            # sessions rotate it each time they start.
            self._remote = PortalRemoteDesktopBackend()
            self._remote.supports(self._caps)
        fd, node = self._remote.open_stream()
        pipeline = None
        try:
            # pipewiresrc dups the descriptor, so ours is closed below either way.
            pipeline = Gst.parse_launch(
                f"pipewiresrc fd={fd} path={node} always-copy=true "
                "! videoconvert ! pngenc ! appsink name=sink sync=false"
            )
            pipeline.set_state(Gst.State.PLAYING)
            sample = pipeline.get_by_name("sink").emit(
                "try-pull-sample", STREAM_FRAME_TIMEOUT * Gst.SECOND
            )
            if sample is None:
                raise RuntimeError(
                    f"no frame from the screen stream within {STREAM_FRAME_TIMEOUT}s"
                )
            buffer = sample.get_buffer()
            data = buffer.extract_dup(0, buffer.get_size())
        finally:
            if pipeline is not None:
                pipeline.set_state(Gst.State.NULL)
            os.close(fd)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
        with open(output_path, "wb") as handle:
            handle.write(data)

    def _drop_remote(self):
        if self._remote is not None:
            self._remote.close()
            self._remote = None
