"""The MCP stdio transport strips the session variables this server needs.

The reference SDK passes only HOME, LOGNAME, PATH, SHELL, TERM and USER, so
XDG_RUNTIME_DIR, DBUS_SESSION_BUS_ADDRESS and WAYLAND_DISPLAY arrive empty and a
healthy desktop probes as having no capture and no input. These tests pin the
recovery, filesystem and all, with no real session involved.
"""
import os
import socket

import pytest

from wayland_mcp import session_env


@pytest.fixture(name="runtime")
def runtime_fixture(tmp_path, monkeypatch):
    """A fake XDG_RUNTIME_DIR, with a bus socket, that restore() will find."""
    (tmp_path / "bus").write_text("")
    monkeypatch.setattr(session_env, "_default_runtime_dir", lambda: str(tmp_path))
    return tmp_path


def make_wayland_socket(directory, name, lock=True):
    """Create a real unix socket named *name*, as a compositor would."""
    path = directory / name
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(path))
    if lock:
        (directory / f"{name}.lock").write_text("")
    return sock


def test_all_three_variables_are_recovered(runtime):
    sock = make_wayland_socket(runtime, "wayland-1")
    try:
        environ = {}
        added = session_env.restore(environ)
    finally:
        sock.close()
    assert added["XDG_RUNTIME_DIR"] == str(runtime)
    assert added["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={runtime / 'bus'}"
    assert added["WAYLAND_DISPLAY"] == "wayland-1"
    assert environ["WAYLAND_DISPLAY"] == "wayland-1"


def test_existing_values_are_never_overwritten(runtime):
    sock = make_wayland_socket(runtime, "wayland-1")
    try:
        environ = {
            "XDG_RUNTIME_DIR": "/somewhere/else",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/custom/bus",
            "WAYLAND_DISPLAY": "wayland-7",
        }
        added = session_env.restore(environ)
    finally:
        sock.close()
    assert added == {}
    assert environ["WAYLAND_DISPLAY"] == "wayland-7"
    assert environ["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/custom/bus"


def test_a_third_party_socket_does_not_make_the_session_ambiguous(runtime):
    """A wallpaper daemon's socket matches wayland-* but is not a compositor.

    Observed for real: swww-daemon leaves wayland-1-swww-daemon..sock next to the
    compositor's own socket. Treating it as a candidate hid a perfectly clear
    session behind an "ambiguous" warning.
    """
    sockets = [
        make_wayland_socket(runtime, "wayland-1"),
        make_wayland_socket(runtime, "wayland-1-swww-daemon..sock", lock=False),
    ]
    try:
        added = session_env.restore({})
    finally:
        for sock in sockets:
            sock.close()
    assert added["WAYLAND_DISPLAY"] == "wayland-1"


def test_the_name_filter_alone_excludes_a_non_compositor_socket(runtime):
    """Isolates the wayland-<digits> check from the .lock check.

    Defence in depth rather than an observed case: the sockets seen in the wild
    have no lock file, so the test above passes even without this filter. Asserted
    separately so a change to either guard shows up.
    """
    sockets = [
        make_wayland_socket(runtime, "wayland-1"),
        make_wayland_socket(runtime, "wayland-1-extra", lock=True),
    ]
    try:
        added = session_env.restore({})
    finally:
        for sock in sockets:
            sock.close()
    assert added["WAYLAND_DISPLAY"] == "wayland-1"


def test_a_socket_without_its_lock_is_not_a_compositor(runtime):
    sock = make_wayland_socket(runtime, "wayland-3", lock=False)
    try:
        added = session_env.restore({})
    finally:
        sock.close()
    assert "WAYLAND_DISPLAY" not in added


def test_two_real_compositors_are_left_to_the_user(runtime):
    """Guessing between two sessions is worse than declining to guess."""
    sockets = [
        make_wayland_socket(runtime, "wayland-0"),
        make_wayland_socket(runtime, "wayland-1"),
    ]
    try:
        added = session_env.restore({})
    finally:
        for sock in sockets:
            sock.close()
    assert "WAYLAND_DISPLAY" not in added


def test_a_regular_file_named_like_a_socket_is_ignored(runtime):
    (runtime / "wayland-2").write_text("not a socket")
    (runtime / "wayland-2.lock").write_text("")
    assert "WAYLAND_DISPLAY" not in session_env.restore({})


def test_no_bus_socket_means_no_bus_address(runtime):
    os.remove(runtime / "bus")
    assert "DBUS_SESSION_BUS_ADDRESS" not in session_env.restore({})


def test_a_missing_runtime_directory_is_not_fatal(monkeypatch):
    monkeypatch.setattr(session_env, "_default_runtime_dir", lambda: None)
    assert session_env.restore({}) == {}
