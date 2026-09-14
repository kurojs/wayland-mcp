"""Backend selection must be decided by capability, and must run headless.

Every scenario below is a plain Capabilities value, so these tests pass with no
compositor, no D-Bus and no /dev/input access -- i.e. in CI.
"""
import pytest

from wayland_mcp.backends.base import (
    Capabilities,
    BackendUnavailable,
    IFACE_REMOTE_DESKTOP,
    IFACE_SCREENCAST,
    IFACE_SCREENSHOT,
    PROTO_EXT_IMAGE_COPY,
    PROTO_VIRTUAL_KEYBOARD,
    PROTO_VIRTUAL_POINTER,
    PROTO_WLR_SCREENCOPY,
)
from wayland_mcp.backends.input_wtype import WtypeBackend
from wayland_mcp.backends.detect import (
    select_capture_backend,
    select_keyboard_backend,
    select_pointer_backend,
)

PORTAL_FULL = {IFACE_SCREENSHOT, IFACE_REMOTE_DESKTOP, IFACE_SCREENCAST}


def cosmic() -> Capabilities:
    """Pop!_OS 24.04 / cosmic-comp, as probed on the reference machine."""
    return Capabilities(
        binaries={"cosmic-screenshot": "cosmic-screenshot 0.1.0", "wayland-info": ""},
        dbus_interfaces=set(PORTAL_FULL),
        wayland_protocols={PROTO_EXT_IMAGE_COPY, PROTO_VIRTUAL_KEYBOARD},
        wayland_display="wayland-1",
        has_gi=True,
        writable_uinput=True,
    )


def sway_grim14() -> Capabilities:
    """wlroots compositor with the grim 1.4 shipped by most distros."""
    return Capabilities(
        binaries={"grim": "grim 1.4.0", "slurp": "slurp 1.4.0", "wtype": "wtype 0.4"},
        # xdg-desktop-portal-wlr provides ScreenCast, and -gtk provides Screenshot;
        # neither provides RemoteDesktop, which is why pointer control has no
        # portal path on wlroots.
        dbus_interfaces={IFACE_SCREENCAST, IFACE_SCREENSHOT},
        wayland_protocols={
            PROTO_WLR_SCREENCOPY,
            PROTO_VIRTUAL_KEYBOARD,
            PROTO_VIRTUAL_POINTER,
        },
        wayland_display="wayland-1",
        has_gi=True,
    )


def sway_grim15() -> Capabilities:
    """wlroots compositor that dropped wlr-screencopy for ext-image-copy."""
    caps = sway_grim14()
    caps.binaries["grim"] = "grim 1.5.0"
    caps.wayland_protocols = {
        PROTO_EXT_IMAGE_COPY,
        PROTO_VIRTUAL_KEYBOARD,
        PROTO_VIRTUAL_POINTER,
    }
    return caps


def gnome() -> Capabilities:
    """GNOME exposes no virtual-keyboard protocol, so wtype cannot work there."""
    return Capabilities(
        binaries={"gnome-screenshot": "gnome-screenshot 41.0"},
        dbus_interfaces=set(PORTAL_FULL),
        wayland_protocols={PROTO_EXT_IMAGE_COPY},
        wayland_display="wayland-0",
        has_gi=True,
    )


def kde() -> Capabilities:
    return Capabilities(
        binaries={"spectacle": "spectacle 24.02.0"},
        dbus_interfaces=set(PORTAL_FULL),
        wayland_protocols={PROTO_EXT_IMAGE_COPY, PROTO_VIRTUAL_KEYBOARD},
        wayland_display="wayland-0",
        has_gi=True,
    )


def barren() -> Capabilities:
    """A TTY or a CI runner: nothing at all."""
    return Capabilities()


# --------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "caps, expected",
    [
        (cosmic(), "cosmic-screenshot"),
        (sway_grim14(), "grim"),
        (sway_grim15(), "grim"),
        (gnome(), "gnome-screenshot"),
        (kde(), "spectacle"),
    ],
)
def test_capture_backend_choice(caps, expected):
    assert select_capture_backend(caps).name == expected


def test_capture_falls_back_to_portal_when_no_tool_is_installed():
    caps = cosmic()
    caps.binaries.pop("cosmic-screenshot")
    assert select_capture_backend(caps).name == "portal"


def test_grim_14_is_rejected_without_wlr_screencopy():
    """The exact COSMIC trap: grim is installed but cannot talk to the compositor."""
    caps = cosmic()
    caps.binaries["grim"] = "grim 1.4.0"
    chosen = select_capture_backend(caps)
    assert chosen.name != "grim"


def test_grim_15_is_accepted_on_ext_image_copy():
    caps = cosmic()
    caps.binaries["grim"] = "grim 1.5.0"
    caps.binaries.pop("cosmic-screenshot")
    assert select_capture_backend(caps).name == "grim"


def test_grim_of_unknown_version_is_trusted_only_on_wlr_screencopy():
    caps = sway_grim14()
    caps.binaries["grim"] = ""
    assert select_capture_backend(caps).name == "grim"
    caps.wayland_protocols = {PROTO_EXT_IMAGE_COPY}
    assert select_capture_backend(caps).name == "portal"


def test_capture_raises_with_an_actionable_message_when_barren():
    with pytest.raises(BackendUnavailable) as excinfo:
        select_capture_backend(barren())
    assert "capture" in str(excinfo.value).lower()


def test_capture_backend_can_be_forced_by_name():
    caps = cosmic()
    assert select_capture_backend(caps, preferred="portal").name == "portal"


def test_forcing_an_unavailable_capture_backend_is_refused():
    with pytest.raises(BackendUnavailable):
        select_capture_backend(cosmic(), preferred="spectacle")


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "caps, expected",
    [
        (cosmic(), "portal"),
        (sway_grim14(), "wtype"),
        (sway_grim15(), "wtype"),
        (gnome(), "portal"),
        (kde(), "portal"),
    ],
)
def test_keyboard_backend_choice(caps, expected):
    assert select_keyboard_backend(caps).name == expected


@pytest.mark.parametrize(
    "caps, expected",
    [
        (cosmic(), "portal"),
        (sway_grim14(), "portal-less wlroots"),
        (gnome(), "portal"),
        (kde(), "portal"),
    ],
)
def test_pointer_backend_choice(caps, expected):
    """wlroots without a RemoteDesktop portal has no pointer path here."""
    if expected == "portal-less wlroots":
        with pytest.raises(BackendUnavailable):
            select_pointer_backend(caps)
    else:
        assert select_pointer_backend(caps).name == expected


def test_wtype_is_rejected_without_the_virtual_keyboard_protocol():
    """wtype is installed on GNOME but the protocol is missing: it cannot work.

    Asserted on the backend directly, not through selection: the portal outranks
    wtype on GNOME anyway, so a selection-level assertion would pass even with the
    protocol check removed.
    """
    caps = gnome()
    caps.binaries["wtype"] = "wtype 0.4"
    assert WtypeBackend().supports(caps) is False
    assert select_keyboard_backend(caps).name == "portal"


def test_wtype_is_the_keyboard_of_last_resort_only_where_the_protocol_exists():
    """With no portal at all, the protocol check is what decides."""
    caps = gnome()
    caps.binaries["wtype"] = "wtype 0.4"
    caps.dbus_interfaces = set()
    with pytest.raises(BackendUnavailable):
        select_keyboard_backend(caps)
    caps.wayland_protocols = {PROTO_VIRTUAL_KEYBOARD}
    assert select_keyboard_backend(caps).name == "wtype"


def test_ydotool_is_used_for_the_pointer_when_no_portal_exists():
    caps = sway_grim14()
    caps.binaries["ydotool"] = "ydotool 1.0.4"
    caps.writable_uinput = True
    assert select_pointer_backend(caps).name == "ydotool"


def test_evemu_is_never_preferred_over_an_unprivileged_backend():
    """evemu needs writable /dev/input, which is exactly what we refuse to require."""
    caps = cosmic()
    caps.binaries["evemu-event"] = "evemu-event 2.7.0"
    caps.writable_input_device = True
    assert select_keyboard_backend(caps).name == "portal"
    assert select_pointer_backend(caps).name == "portal"


def test_evemu_is_still_available_as_a_last_resort():
    caps = barren()
    caps.binaries["evemu-event"] = "evemu-event 2.7.0"
    caps.writable_input_device = True
    assert select_keyboard_backend(caps).name == "evemu"
    assert select_pointer_backend(caps).name == "evemu"


def test_evemu_is_rejected_when_devices_are_not_already_writable():
    """We observe permissions; we never widen them, so a read-only /dev/input is final."""
    caps = barren()
    caps.binaries["evemu-event"] = "evemu-event 2.7.0"
    caps.writable_input_device = False
    with pytest.raises(BackendUnavailable):
        select_keyboard_backend(caps)


def test_input_raises_with_an_actionable_message_when_barren():
    with pytest.raises(BackendUnavailable) as excinfo:
        select_keyboard_backend(barren())
    assert "keyboard" in str(excinfo.value).lower()
