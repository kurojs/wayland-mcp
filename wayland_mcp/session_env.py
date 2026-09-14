"""Recover the session variables an MCP client strips before launching us.

The MCP stdio transport does not hand a server the caller's whole environment: the
reference SDK passes a deliberately small allow-list (PATH, HOME, USER, ...) and
drops everything else. For most servers that is harmless. For this one it removes
exactly what it needs -- XDG_RUNTIME_DIR, DBUS_SESSION_BUS_ADDRESS and
WAYLAND_DISPLAY -- so every backend probe comes back empty and the server reports
a perfectly healthy desktop as having no capture and no input at all.

Each of the three is recoverable from the filesystem, so we reconstruct what is
missing instead of asking every user to restate it in their client config. Values
already present are never overwritten: an explicit setting always wins.
"""
import glob
import logging
import os
import re
import stat


def restore(environ=None) -> dict:
    """Fill in missing session variables. Returns what was added."""
    environ = environ if environ is not None else os.environ
    added = {}

    runtime_dir = environ.get("XDG_RUNTIME_DIR") or _default_runtime_dir()
    if runtime_dir and not environ.get("XDG_RUNTIME_DIR"):
        environ["XDG_RUNTIME_DIR"] = runtime_dir
        added["XDG_RUNTIME_DIR"] = runtime_dir

    if not environ.get("DBUS_SESSION_BUS_ADDRESS"):
        bus = _default_bus_address(runtime_dir)
        if bus:
            environ["DBUS_SESSION_BUS_ADDRESS"] = bus
            added["DBUS_SESSION_BUS_ADDRESS"] = bus

    if not environ.get("WAYLAND_DISPLAY"):
        display = _find_wayland_socket(runtime_dir)
        if display:
            environ["WAYLAND_DISPLAY"] = display
            added["WAYLAND_DISPLAY"] = display

    if added:
        logging.info(
            "Recovered session variables the MCP client did not pass: %s",
            ", ".join(sorted(added)),
        )
    return added


def _default_runtime_dir():
    """``/run/user/<uid>``, when it exists and belongs to us."""
    path = f"/run/user/{os.getuid()}"
    return path if os.path.isdir(path) else None


def _default_bus_address(runtime_dir):
    """The well-known session bus socket under the runtime directory."""
    if not runtime_dir:
        return None
    socket_path = os.path.join(runtime_dir, "bus")
    if not os.path.exists(socket_path):
        return None
    return f"unix:path={socket_path}"


def _find_wayland_socket(runtime_dir):
    """Name of the compositor's Wayland socket in *runtime_dir*, if unambiguous.

    Only ``wayland-<digits>`` counts, and only with the sibling ``.lock`` file a
    compositor creates. Other programs put sockets of their own in the runtime
    directory -- a wallpaper daemon's ``wayland-1-swww-daemon..sock`` is a real
    example -- and matching them would make a perfectly clear session look
    ambiguous. With several genuine candidates we still refuse to guess: talking to
    the wrong compositor is worse than reporting none, and WAYLAND_DISPLAY can
    always be set explicitly in the client config.
    """
    if not runtime_dir:
        return None
    candidates = []
    for path in glob.glob(os.path.join(runtime_dir, "wayland-*")):
        name = os.path.basename(path)
        if not re.fullmatch(r"wayland-\d+", name):
            continue
        if not os.path.exists(path + ".lock"):
            continue
        try:
            if stat.S_ISSOCK(os.stat(path).st_mode):
                candidates.append(name)
        except OSError:
            continue
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        logging.warning(
            "Several Wayland sockets in %s (%s); set WAYLAND_DISPLAY explicitly",
            runtime_dir, ", ".join(sorted(candidates)),
        )
    return None
