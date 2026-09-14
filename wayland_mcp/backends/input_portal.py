"""Input via org.freedesktop.portal.RemoteDesktop.

This is the answer to upstream's root requirement. RemoteDesktop synthesises
pointer and keyboard events with no privilege at all, and GNOME, KDE and COSMIC
all implement it -- unlike zwp_virtual_keyboard (absent on GNOME) or ydotool
(needs /dev/uinput).

One wrinkle shapes the code below: NotifyPointerMotionAbsolute takes a *stream*,
which only exists if a ScreenCast session is attached to the same handle. So the
session is opened as RemoteDesktop + ScreenCast when absolute positioning is
wanted, and degrades to relative-only motion when ScreenCast is unavailable or
refused.
"""
import logging
import os
import time

from wayland_mcp.backends.base import (
    IFACE_REMOTE_DESKTOP,
    IFACE_SCREENCAST,
    Capabilities,
    InputBackend,
)
from wayland_mcp.backends import portal
from wayland_mcp.backends.keycodes import keysym_for_char, parse_keysym_combo

#: Linux input button codes, what NotifyPointerButton expects.
BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112
BUTTONS = {"left": BTN_LEFT, "right": BTN_RIGHT, "middle": BTN_MIDDLE}

#: RemoteDesktop device bitmask: 1 = keyboard, 2 = pointer, 4 = touchscreen.
DEVICE_KEYBOARD = 1
DEVICE_POINTER = 2

#: Session persistence: 0 none, 1 while the app runs, 2 until revoked.
PERSIST_UNTIL_REVOKED = 2

#: One wheel notch, in the units NotifyPointerAxis uses.
AXIS_STEP = 120.0

#: Axis indices for NotifyPointerAxisDiscrete.
AXIS_VERTICAL = 0
AXIS_HORIZONTAL = 1

#: Settling time after the warm-up event; see _warm_up.
WARM_UP_SECONDS = 0.15

#: Where the restore token lives between runs.
#
# The portal hands back a restore_token after the user allows a session. Replaying
# it with persist_mode=2 lets the compositor grant the next session silently, so
# the consent dialog appears once per machine rather than once per server start.
# It is a capability: keep it 0600, in the user's state directory.
ENV_TOKEN_PATH = "WAYLAND_MCP_RESTORE_TOKEN_PATH"
ENV_NO_PERSIST = "WAYLAND_MCP_NO_PERSIST"


def token_path() -> str:
    """Path of the stored restore token."""
    override = os.environ.get(ENV_TOKEN_PATH)
    if override:
        return os.path.expanduser(override)
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "wayland-mcp", "remote-desktop-token")


def persistence_enabled() -> bool:
    """False when the user asked to be prompted every time."""
    return os.environ.get(ENV_NO_PERSIST, "").lower() not in ("1", "true", "yes")


def load_restore_token():
    """The stored token, or None."""
    if not persistence_enabled():
        return None
    try:
        with open(token_path(), encoding="utf-8") as handle:
            return handle.read().strip() or None
    except OSError:
        return None


def save_restore_token(value) -> None:
    """Store *value* for the next run, readable only by this user."""
    if not value or not persistence_enabled():
        return
    path = token_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Create with 0600 from the start rather than widening then narrowing.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
    except OSError as err:
        logging.warning("Could not store the portal restore token in %s: %s", path, err)


def forget_restore_token() -> None:
    """Drop the stored token, so the next session asks again."""
    try:
        os.remove(token_path())
    except OSError:
        pass


class PortalRemoteDesktopBackend(InputBackend):
    """A persistent RemoteDesktop session, started on first use."""

    name = "portal"
    priority = 80
    can_pointer = True
    can_keyboard = True
    absolute_pointer = True
    requires = (
        "a running XDG desktop portal exposing org.freedesktop.portal.RemoteDesktop, "
        "plus PyGObject (install the 'portal' extra, or python3-gi)"
    )

    def __init__(self):
        self._session = None
        self._handle = None
        self._stream = None
        self._screen = None
        self._restore_token = load_restore_token()
        self._can_screencast = True

    def supports(self, caps: Capabilities) -> bool:
        self._can_screencast = IFACE_SCREENCAST in caps.dbus_interfaces
        return IFACE_REMOTE_DESKTOP in caps.dbus_interfaces and caps.has_gi

    # -- session lifecycle -------------------------------------------------

    def _ensure_session(self):
        """Open the session once; every later call reuses it.

        A stored restore token can go stale -- the user revoked the permission, the
        compositor restarted, the token rotated out. That must not be fatal, so a
        failure with a token in hand is retried once without it, which falls back
        to asking the user.
        """
        if self._handle is not None:
            return
        try:
            self._open_session()
        except portal.PortalError:
            if not self._restore_token:
                raise
            logging.warning(
                "The stored portal token was refused; asking for permission again"
            )
            forget_restore_token()
            self._restore_token = None
            self._handle = None
            self._open_session()

    def _open_session(self):
        """Create, configure and start a RemoteDesktop session."""
        from gi.repository import GLib  # pylint: disable=import-outside-toplevel

        if self._restore_token:
            logging.info("Reusing the stored portal permission for input control")
        else:
            portal.log_permission_hint("Pointer and keyboard control")
        self._session = portal.PortalSession()

        create_token = portal.token()
        results = self._session.request(
            IFACE_REMOTE_DESKTOP,
            "CreateSession",
            GLib.Variant("(a{sv})", ({
                "handle_token": GLib.Variant("s", create_token),
                "session_handle_token": GLib.Variant("s", portal.token()),
            },)),
            create_token,
        )
        self._handle = results["session_handle"]

        select_token = portal.token()
        select_options = {
            "handle_token": GLib.Variant("s", select_token),
            "types": GLib.Variant("u", DEVICE_KEYBOARD | DEVICE_POINTER),
            "persist_mode": GLib.Variant("u", PERSIST_UNTIL_REVOKED),
        }
        if self._restore_token:
            select_options["restore_token"] = GLib.Variant("s", self._restore_token)
        self._session.request(
            IFACE_REMOTE_DESKTOP,
            "SelectDevices",
            GLib.Variant("(oa{sv})", (self._handle, select_options)),
            select_token,
        )

        if self._can_screencast:
            self._select_screencast_sources()

        start_token = portal.token()
        started = self._session.request(
            IFACE_REMOTE_DESKTOP,
            "Start",
            GLib.Variant("(osa{sv})", (
                self._handle, "", {"handle_token": GLib.Variant("s", start_token)},
            )),
            start_token,
            # The consent dialog is a human in the loop -- unless a stored token
            # lets the portal answer on its own, which is the usual case.
            timeout_ms=180000,
        )
        new_token = started.get("restore_token")
        if new_token:
            # The portal may rotate the token on every use, so always store what
            # the latest Start returned rather than keeping the first one.
            self._restore_token = new_token
            save_restore_token(new_token)
        self._adopt_streams(started.get("streams") or [])
        self._warm_up()
        logging.info(
            "RemoteDesktop session started (absolute pointer: %s, silent next time: %s)",
            "yes" if self._stream is not None else "no, relative only",
            "yes" if self._restore_token else "no",
        )

    def _warm_up(self):
        """Absorb the first synthesized event, which cosmic-comp discards.

        Measured on cosmic-comp 0.1: the first event sent after Start never reaches
        any client -- the first pointer warp and the first key tap are both lost,
        while everything after them arrives. A zero-distance relative motion is a
        harmless sacrifice, and it makes the first real call behave like the rest.
        """
        from gi.repository import GLib  # pylint: disable=import-outside-toplevel

        try:
            self._notify(
                "NotifyPointerMotion",
                GLib.Variant("(oa{sv}dd)", (self._handle, {}, 0.0, 0.0)),
            )
            time.sleep(WARM_UP_SECONDS)
        except portal.PortalError as err:
            logging.debug("Warm-up event failed, continuing: %s", err)

    def _select_screencast_sources(self):
        """Attach a ScreenCast source, needed for absolute pointer coordinates."""
        from gi.repository import GLib  # pylint: disable=import-outside-toplevel

        sources_token = portal.token()
        try:
            self._session.request(
                IFACE_SCREENCAST,
                "SelectSources",
                GLib.Variant("(oa{sv})", (self._handle, {
                    "handle_token": GLib.Variant("s", sources_token),
                    "types": GLib.Variant("u", 1),  # monitors
                    "multiple": GLib.Variant("b", False),
                    "cursor_mode": GLib.Variant("u", 2),  # embedded, so captures show it
                    # No persist_mode here: a ScreenCast attached to a RemoteDesktop
                    # session cannot persist, and COSMIC rejects the whole call with
                    # "Remote desktop sessions cannot persist" if it is passed.
                })),
                sources_token,
            )
        except portal.PortalError as err:
            # Not fatal: we lose absolute positioning, not the whole session.
            logging.warning("ScreenCast source selection failed (%s); pointer will be "
                            "relative only", err)
            self._can_screencast = False

    def _adopt_streams(self, streams):
        """Remember the first stream's node id and size for absolute motion."""
        for node_id, props in streams:
            self._stream = node_id
            size = props.get("size")
            if size:
                self._screen = (int(size[0]), int(size[1]))
            return

    def close(self):
        if self._handle and self._session:
            try:
                self._session.call_on(
                    self._handle, "org.freedesktop.portal.Session", "Close", None, None
                )
            except portal.PortalError as err:
                logging.debug("Closing RemoteDesktop session failed: %s", err)
        self._handle = None
        self._stream = None

    # -- pointer -----------------------------------------------------------

    @property
    def screen_size(self):
        """Size of the captured stream, or None when unknown."""
        return self._screen

    def move_pointer(self, x, y, relative=False) -> bool:
        from gi.repository import GLib  # pylint: disable=import-outside-toplevel

        self._ensure_session()
        if relative or self._stream is None:
            if not relative:
                raise portal.PortalError(
                    "absolute pointer positioning needs a ScreenCast stream, which this "
                    "portal did not grant; move relatively or use another input backend"
                )
            self._notify(
                "NotifyPointerMotion",
                GLib.Variant("(oa{sv}dd)", (self._handle, {}, float(x), float(y))),
            )
            return True
        self._notify(
            "NotifyPointerMotionAbsolute",
            GLib.Variant("(oa{sv}udd)", (
                self._handle, {}, self._stream, float(x), float(y),
            )),
        )
        return True

    def click(self, button="left", press=True, release=True) -> bool:
        from gi.repository import GLib  # pylint: disable=import-outside-toplevel

        self._ensure_session()
        code = BUTTONS.get(button)
        if code is None:
            raise ValueError(f"unknown mouse button {button!r}")
        for state in ([1] if press else []) + ([0] if release else []):
            self._notify(
                "NotifyPointerButton",
                GLib.Variant("(oa{sv}iu)", (self._handle, {}, code, state)),
            )
        return True

    def scroll(self, amount, horizontal=False) -> bool:
        """Scroll by *amount* wheel notches; positive is up (or left).

        NotifyPointerAxis carries continuous deltas, which GTK treats as a smooth
        two-finger gesture and a plain list view ignores. A wheel is discrete, so
        NotifyPointerAxisDiscrete is what actually moves the view.
        """
        from gi.repository import GLib  # pylint: disable=import-outside-toplevel

        self._ensure_session()
        axis = AXIS_HORIZONTAL if horizontal else AXIS_VERTICAL
        # Our sign convention is upstream's: positive scrolls up. The portal axis
        # grows downwards.
        steps = -int(amount)
        self._notify(
            "NotifyPointerAxisDiscrete",
            GLib.Variant("(oa{sv}ui)", (self._handle, {}, axis, steps)),
        )
        return True

    # -- keyboard ----------------------------------------------------------

    def type_text(self, text) -> bool:
        """Type *text* by keysym, so the result does not depend on the layout."""
        self._ensure_session()
        for char in text:
            symbol = keysym_for_char(char)
            if symbol is None:
                logging.warning("No keysym for %r; skipped", char)
                continue
            self._tap_keysym([], symbol)
        return True

    def press_key(self, key) -> bool:
        """Press a key or a combination such as ``"ctrl+shift+t"``."""
        self._ensure_session()
        modifiers, main = parse_keysym_combo(key)
        self._tap_keysym(modifiers, main)
        return True

    def _tap_keysym(self, modifiers, symbol):
        """Hold modifiers, tap *symbol*, release modifiers in reverse order."""
        for modifier in modifiers:
            self._keysym(modifier, 1)
        try:
            self._keysym(symbol, 1)
            self._keysym(symbol, 0)
        finally:
            for modifier in reversed(modifiers):
                self._keysym(modifier, 0)

    def _keysym(self, symbol, state):
        from gi.repository import GLib  # pylint: disable=import-outside-toplevel

        self._notify(
            "NotifyKeyboardKeysym",
            GLib.Variant("(oa{sv}iu)", (self._handle, {}, int(symbol), state)),
        )

    def _notify(self, method, args):
        self._session.call(IFACE_REMOTE_DESKTOP, method, args, None)
