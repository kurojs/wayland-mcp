"""Capture via org.freedesktop.portal.Screenshot.

The universal fallback: implemented by GNOME, KDE, COSMIC and
xdg-desktop-portal-wlr alike, and needs no privilege. The cost is a permission
prompt the first time, and on some desktops an interactive picker -- which is why
this sits below the native tools rather than above them.
"""
import logging
import os
import shutil

from wayland_mcp.backends.base import (
    IFACE_SCREENSHOT,
    Capabilities,
    CaptureBackend,
)
from wayland_mcp.backends import portal


class PortalScreenshotBackend(CaptureBackend):
    """`org.freedesktop.portal.Screenshot.Screenshot`, interactive=false."""

    name = "portal"
    priority = 20
    requires = (
        "a running XDG desktop portal exposing org.freedesktop.portal.Screenshot, "
        "plus PyGObject (install the 'portal' extra, or python3-gi)"
    )

    def supports(self, caps: Capabilities) -> bool:
        return IFACE_SCREENSHOT in caps.dbus_interfaces and caps.has_gi

    def capture(self, output_path, mode="auto", geometry=None, include_mouse=True) -> dict:
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
        return {"success": True, "filename": output_path}
