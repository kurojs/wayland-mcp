"""Shared plumbing for org.freedesktop.portal.* calls over GDBus.

Portal methods do not answer inline: they return an object path and the real
answer arrives later as a ``Response`` signal on that path. Everything here
exists to make that one pattern usable synchronously, which is what an MCP tool
call needs.
"""
import logging
import os
import random
import string

PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
REQUEST_IFACE = "org.freedesktop.portal.Request"

#: Portal responses: 0 success, 1 cancelled by the user, 2 ended some other way.
RESPONSE_SUCCESS = 0
RESPONSE_CANCELLED = 1


class PortalError(RuntimeError):
    """A portal call failed, was cancelled, or timed out."""


def gi_available() -> bool:
    """True when PyGObject is importable (the ``portal`` extra is installed)."""
    try:
        from gi.repository import Gio, GLib  # noqa: F401  pylint: disable=unused-import,import-outside-toplevel
    except (ImportError, ValueError):
        return False
    return True


def token() -> str:
    """A handle token: portals require [A-Za-z0-9_] and uniqueness per caller."""
    return "wayland_mcp_" + "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(16)
    )


class PortalSession:
    """A session bus connection with synchronous portal request handling."""

    def __init__(self, timeout_ms: int = 30000):
        from gi.repository import Gio  # pylint: disable=import-outside-toplevel

        self.timeout_ms = timeout_ms
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self._sender = self.bus.get_unique_name().lstrip(":").replace(".", "_")

    def request_path(self, handle_token: str) -> str:
        """The object path a request with *handle_token* will use.

        Subscribing to it *before* issuing the call closes the race where the
        portal answers faster than we can listen.
        """
        return f"{PORTAL_PATH}/request/{self._sender}/{handle_token}"

    def call(self, interface, method, args, reply_type):
        """A plain synchronous D-Bus call on the portal object."""
        from gi.repository import Gio, GLib  # pylint: disable=import-outside-toplevel

        try:
            return self.bus.call_sync(
                PORTAL_BUS, PORTAL_PATH, interface, method, args,
                GLib.VariantType(reply_type) if reply_type else None,
                Gio.DBusCallFlags.NONE, self.timeout_ms, None,
            )
        except GLib.Error as err:
            raise PortalError(f"{interface}.{method} failed: {err.message}") from err

    def call_on(self, path, interface, method, args, reply_type):
        """Same, but on an arbitrary object path (a session handle, typically)."""
        from gi.repository import Gio, GLib  # pylint: disable=import-outside-toplevel

        try:
            return self.bus.call_sync(
                PORTAL_BUS, path, interface, method, args,
                GLib.VariantType(reply_type) if reply_type else None,
                Gio.DBusCallFlags.NONE, self.timeout_ms, None,
            )
        except GLib.Error as err:
            raise PortalError(f"{interface}.{method} failed: {err.message}") from err

    def request(self, interface, method, args, handle_token, timeout_ms=None):
        """Issue a portal request and block until its Response signal arrives.

        Returns the response's ``a{sv}`` payload as a dict.
        """
        from gi.repository import GLib  # pylint: disable=import-outside-toplevel

        loop = GLib.MainLoop()
        outcome = {}
        path = self.request_path(handle_token)

        def on_response(_bus, _sender, _path, _iface, _signal, params):
            code, results = params.unpack()
            outcome["code"] = code
            outcome["results"] = results
            loop.quit()

        subscription = self.bus.signal_subscribe(
            PORTAL_BUS, REQUEST_IFACE, "Response", path, None, 0, on_response
        )
        try:
            self.call(interface, method, args, "(o)")
            timeout = timeout_ms or self.timeout_ms
            expiry = GLib.timeout_add(timeout, lambda: (loop.quit(), False)[1])
            loop.run()
            GLib.source_remove(expiry)
        finally:
            self.bus.signal_unsubscribe(subscription)

        if "code" not in outcome:
            raise PortalError(
                f"{interface}.{method} timed out after {timeout_ms or self.timeout_ms}ms "
                "with no portal response (is a permission dialog waiting for input?)"
            )
        if outcome["code"] == RESPONSE_CANCELLED:
            raise PortalError(f"{interface}.{method} was cancelled by the user")
        if outcome["code"] != RESPONSE_SUCCESS:
            raise PortalError(
                f"{interface}.{method} ended with portal response code {outcome['code']}"
            )
        return outcome["results"]


def uri_to_path(uri: str) -> str:
    """Turn the ``file://`` URI a portal returns into a local path."""
    from gi.repository import GLib  # pylint: disable=import-outside-toplevel

    if not uri.startswith("file://"):
        return uri
    path, _ = GLib.filename_from_uri(uri)
    return path


def cache_dir() -> str:
    """Where to stage portal output before moving it where the caller asked."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    path = os.path.join(base, "wayland-mcp")
    os.makedirs(path, exist_ok=True)
    return path


def log_permission_hint(what: str) -> None:
    logging.info(
        "%s goes through the XDG portal: the compositor may ask you to allow it once.",
        what,
    )
