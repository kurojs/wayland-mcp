"""Capability model and backend interfaces for capture and input.

Backends are chosen by *capability*, never by compositor name: a probed
snapshot of the machine (binaries and their versions, D-Bus interfaces on the
session bus, Wayland globals advertised by the compositor) is matched against
what each backend actually requires. That keeps selection testable without a
graphical session -- see tests/test_backend_selection.py -- and avoids the
usual trap of special-casing XDG_CURRENT_DESKTOP.
"""
import os
import shutil
import subprocess
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple

# Wayland globals we care about, and the tools that speak them.
PROTO_WLR_SCREENCOPY = "zwlr_screencopy_manager_v1"
PROTO_EXT_IMAGE_COPY = "ext_image_copy_capture_manager_v1"
PROTO_VIRTUAL_KEYBOARD = "zwp_virtual_keyboard_manager_v1"
PROTO_VIRTUAL_POINTER = "zwlr_virtual_pointer_manager_v1"

# Portal interfaces, as seen on org.freedesktop.portal.Desktop.
IFACE_SCREENSHOT = "org.freedesktop.portal.Screenshot"
IFACE_REMOTE_DESKTOP = "org.freedesktop.portal.RemoteDesktop"
IFACE_SCREENCAST = "org.freedesktop.portal.ScreenCast"

_BINARIES_OF_INTEREST = (
    "grim",
    "slurp",
    "cosmic-screenshot",
    "gnome-screenshot",
    "ksnip",
    "spectacle",
    "wtype",
    "ydotool",
    "evemu-event",
    "evemu-describe",
    "wayland-info",
)


@dataclass
class Capabilities:
    """What this machine can actually do.

    Build one with :meth:`detect` at runtime, or by hand in tests. Every field
    is data, so a scenario is one constructor call.
    """

    binaries: Dict[str, str] = field(default_factory=dict)
    """Available binary name -> version string ("" when version is unknown)."""

    dbus_interfaces: Set[str] = field(default_factory=set)
    wayland_protocols: Set[str] = field(default_factory=set)
    wayland_display: Optional[str] = None
    has_gi: bool = False
    writable_input_device: bool = False
    writable_uinput: bool = False

    def has(self, binary: str) -> bool:
        """True when *binary* is on PATH."""
        return binary in self.binaries

    def version(self, binary: str) -> Tuple[int, ...]:
        """Parsed version of *binary* as a tuple, ``()`` when unknown."""
        raw = self.binaries.get(binary, "")
        match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", raw)
        if not match:
            return ()
        return tuple(int(g) for g in match.groups() if g is not None)

    @property
    def is_wayland(self) -> bool:
        return bool(self.wayland_display)

    @classmethod
    def detect(cls) -> "Capabilities":
        """Probe the running system. Never raises; unknowns stay empty."""
        return cls(
            binaries=_probe_binaries(),
            dbus_interfaces=_probe_portal_interfaces(),
            wayland_protocols=_probe_wayland_protocols(),
            wayland_display=os.environ.get("WAYLAND_DISPLAY"),
            has_gi=_probe_gi(),
            writable_input_device=_probe_writable_input(),
            writable_uinput=os.access("/dev/uinput", os.W_OK),
        )


def _probe_binaries() -> Dict[str, str]:
    found = {}
    for name in _BINARIES_OF_INTEREST:
        if not shutil.which(name):
            continue
        found[name] = _probe_version(name)
    return found


def _probe_version(name: str) -> str:
    for flag in ("--version", "-V"):
        try:
            out = subprocess.run(
                [name, flag], capture_output=True, text=True, timeout=5, check=False
            )
        except (OSError, subprocess.SubprocessError):
            continue
        text = (out.stdout or "") + (out.stderr or "")
        if re.search(r"\d+\.\d+", text):
            return text.strip().splitlines()[0]
    return ""


def _probe_portal_interfaces() -> Set[str]:
    """Interfaces exposed by the XDG desktop portal, if one is running."""
    try:
        from gi.repository import Gio, GLib  # pylint: disable=import-outside-toplevel
    except (ImportError, ValueError):
        return set()
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.DBus.Introspectable",
            "Introspect",
            None,
            GLib.VariantType("(s)"),
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
    except GLib.Error as err:
        logging.debug("Portal introspection failed: %s", err)
        return set()
    xml = reply.unpack()[0]
    return set(re.findall(r'<interface name="(org\.freedesktop\.portal\.[^"]+)"', xml))


def _probe_wayland_protocols() -> Set[str]:
    """Globals advertised by the compositor, via wayland-info when present.

    Absent that tool we return an empty set rather than guessing. Backends must
    treat "unknown" as "do not rely on this protocol", so an empty set degrades
    to the portal rather than to a wrong choice.
    """
    if not os.environ.get("WAYLAND_DISPLAY") or not shutil.which("wayland-info"):
        return set()
    try:
        out = subprocess.run(
            ["wayland-info"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError) as err:
        logging.debug("wayland-info failed: %s", err)
        return set()
    return set(re.findall(r"interface: '([a-z_0-9]+)'", out.stdout))


def _probe_gi() -> bool:
    try:
        from gi.repository import Gio  # noqa: F401  pylint: disable=unused-import,import-outside-toplevel
    except (ImportError, ValueError):
        return False
    return True


def _probe_writable_input() -> bool:
    """True when at least one /dev/input event device is writable as-is.

    This only *observes* permissions. Nothing in this project ever changes them:
    the upstream setup.sh made every input device world-writable, which turns any
    local process into a keylogger.
    """
    try:
        entries = os.listdir("/dev/input")
    except OSError:
        return False
    return any(
        entry.startswith("event") and os.access(f"/dev/input/{entry}", os.W_OK)
        for entry in entries
    )


class BackendUnavailable(RuntimeError):
    """Raised when no backend can serve a request, with an actionable message."""


class Backend:
    """Common shape: a name, a priority, and an availability predicate."""

    name = "abstract"
    priority = 0

    #: Human-readable statement of what this backend needs, used in error messages.
    requires = "unspecified"

    def supports(self, caps: Capabilities) -> bool:
        """True when this backend can work given *caps*."""
        raise NotImplementedError

    def requirements(self) -> str:
        """What this backend needs, for the 'nothing works' error message."""
        return self.requires

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} priority={self.priority}>"


class CaptureBackend(Backend):
    """Grabs the screen to a PNG file."""

    def capture(self, output_path: str, mode: str = "auto", geometry=None,
                include_mouse: bool = True) -> dict:
        """Return ``{"success": bool, "filename": str, "error": str}``."""
        raise NotImplementedError


class InputBackend(Backend):
    """Synthesises pointer and/or keyboard events."""

    can_pointer = False
    can_keyboard = False
    #: True when absolute pointer coordinates are honoured directly.
    absolute_pointer = False

    def move_pointer(self, x: int, y: int, relative: bool = False) -> bool:
        raise NotImplementedError

    def click(self, button: str = "left", press: bool = True, release: bool = True) -> bool:
        raise NotImplementedError

    def scroll(self, amount: int, horizontal: bool = False) -> bool:
        raise NotImplementedError

    def type_text(self, text: str) -> bool:
        raise NotImplementedError

    def press_key(self, key: str) -> bool:
        raise NotImplementedError

    def close(self) -> None:
        """Release any session held by this backend."""
