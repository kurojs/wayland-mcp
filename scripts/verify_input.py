#!/usr/bin/env python3
"""End-to-end check of the input backend against a real window.

Opens a GTK window, calibrates where it sits on screen, then drives it through
whichever input backend this machine selects: click a button at its true
on-screen position, type a known string into an entry, and scroll a list. Every
result is read back from the widgets, so nothing is inferred from the mere absence
of an exception.

Wayland does not let a client know its own position, so the origin is *measured*:
the pointer is warped to a known absolute point and the motion event GTK reports
gives the offset. Guessing from the monitor geometry does not survive a tiling
compositor or a panel.

Run from a graphical session:

    python scripts/verify_input.py

The compositor asks for permission once; afterwards the stored restore token makes
it silent. Set WAYLAND_MCP_NO_PERSIST=1 to be asked every time.
"""
import sys
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402  pylint: disable=wrong-import-position

from wayland_mcp.keyboard_utils import KeyboardController  # noqa: E402
from wayland_mcp.mouse_utils import MouseController  # noqa: E402

EXPECTED_TEXT = "Bonjour ASAP 42"
#: Absolute point used to work out where the window is. Chosen well inside a
#: 1080p screen and inside a centred window.
CALIBRATION_POINT = (760, 420)

#: Seconds to wait before driving anything, so the window is mapped and focused.
SETTLE_SECONDS = 3.0

RESULTS = {
    "pointer_backend": None,
    "keyboard_backend": None,
    "absolute_pointer": None,
    "origin": None,
    "clicked": False,
    "typed": None,
    "keycodes": [],
    "scrolled": 0.0,
    "errors": [],
}


class Harness(Gtk.Application):
    """A window that records what the input backend actually does to it."""

    def __init__(self):
        super().__init__(application_id="cool.asap.waylandmcp.verify")
        self.window = None
        self.entry = None
        self.button = None
        self.scroller = None
        self._last_motion = None
        self._motion_seen = threading.Event()

    def do_activate(self):  # pylint: disable=arguments-differ
        self.window = Gtk.ApplicationWindow(application=self, title="wayland-mcp verify")
        self.window.set_default_size(700, 460)
        # Fullscreen on purpose: the calibration warp must land inside the window,
        # and a windowed harness silently fails if anything else has the pointer or
        # the keyboard focus. Do not use the machine while this runs.
        self.window.fullscreen()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        for side in ("top", "start", "end"):
            getattr(box, f"set_margin_{side}")(30)

        self.button = Gtk.Button(label="click me")
        self.button.connect("clicked", self._on_clicked)
        box.append(self.button)

        self.entry = Gtk.Entry(placeholder_text="typing lands here")
        box.append(self.entry)

        self.scroller = Gtk.ScrolledWindow(vexpand=True)
        self.scroller.set_child(Gtk.Label(label="\n".join(f"line {n}" for n in range(120))))
        box.append(self.scroller)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        self.window.add_controller(motion)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.window.add_controller(keys)

        self.window.set_child(box)
        self.window.present()
        threading.Thread(target=self._drive, daemon=True).start()

    # -- observers ---------------------------------------------------------

    def _on_clicked(self, _button):
        RESULTS["clicked"] = True

    def _on_motion(self, _controller, x, y):
        self._last_motion = (x, y)
        self._motion_seen.set()

    def _on_key(self, _controller, _keyval, keycode, _state):
        # GTK reports hardware keycodes, which are evdev codes plus 8.
        RESULTS["keycodes"].append(keycode - 8)
        return False

    # -- the test ----------------------------------------------------------

    def _drive(self):
        try:
            time.sleep(SETTLE_SECONDS)  # let the compositor map and focus the window
            mouse = MouseController()
            keyboard = KeyboardController()
            RESULTS["pointer_backend"] = mouse.backend.name
            RESULTS["keyboard_backend"] = keyboard.backend.name
            RESULTS["absolute_pointer"] = mouse.backend.absolute_pointer

            origin = self._calibrate(mouse)
            RESULTS["origin"] = origin

            self._click_button(mouse, origin)
            self._type_into_entry(keyboard)
            self._scroll_list(mouse, origin)

            mouse.close()
            keyboard.close()
        except Exception as err:  # pylint: disable=broad-except
            RESULTS["errors"].append(f"{type(err).__name__}: {err}")
        finally:
            time.sleep(0.4)
            GLib.idle_add(self.quit)

    def _calibrate(self, mouse):
        """Measure the window origin by warping the pointer to a known point."""
        self._motion_seen.clear()
        mouse.move_to_absolute(*CALIBRATION_POINT)
        if not self._motion_seen.wait(timeout=3.0):
            raise RuntimeError(
                "the window received no pointer motion at all; the backend accepted "
                "the request but the compositor delivered nothing"
            )
        time.sleep(0.2)
        local_x, local_y = self._last_motion
        origin = (
            CALIBRATION_POINT[0] - local_x,
            CALIBRATION_POINT[1] - local_y,
        )
        print(f"window origin measured at {origin[0]:.0f},{origin[1]:.0f}")
        return origin

    def _widget_center(self, widget, origin):
        ok, bounds = widget.compute_bounds(self.window)
        if not ok:
            raise RuntimeError(f"could not compute bounds for {widget}")
        return (
            int(origin[0] + bounds.origin.x + bounds.size.width / 2),
            int(origin[1] + bounds.origin.y + bounds.size.height / 2),
        )

    def _click_button(self, mouse, origin):
        target = self._widget_center(self.button, origin)
        print(f"clicking the button at {target}")
        mouse.move_to_absolute(*target)
        time.sleep(0.4)
        mouse.click()
        time.sleep(0.6)

    def _type_into_entry(self, keyboard):
        print("focusing the entry and typing")
        done = threading.Event()
        GLib.idle_add(lambda: (self.entry.grab_focus(), done.set(), False)[2])
        done.wait(timeout=2.0)
        time.sleep(0.4)
        keyboard.type_text(EXPECTED_TEXT)
        time.sleep(1.0)
        read = threading.Event()

        def read_entry():
            RESULTS["typed"] = self.entry.get_text()
            read.set()
            return False

        GLib.idle_add(read_entry)
        read.wait(timeout=2.0)

    def _scroll_list(self, mouse, origin):
        print("scrolling the list")
        adjustment = self.scroller.get_vadjustment()
        before = adjustment.get_value()
        mouse.move_to_absolute(*self._widget_center(self.scroller, origin))
        time.sleep(0.3)
        mouse.scroll(-5)  # negative is down
        time.sleep(1.0)
        RESULTS["scrolled"] = adjustment.get_value() - before


def main():
    Harness().run([])

    print("\n--- results ---")
    print(f"pointer backend         : {RESULTS['pointer_backend']}")
    print(f"keyboard backend        : {RESULTS['keyboard_backend']}")
    print(f"absolute pointer        : {RESULTS['absolute_pointer']}")
    print(f"button received a click : {RESULTS['clicked']}")
    print(f"entry received          : {RESULTS['typed']!r}")
    print(f"evdev codes seen        : {RESULTS['keycodes']}")
    print(f"scroll moved the view by: {RESULTS['scrolled']:.0f}px")
    for error in RESULTS["errors"]:
        print(f"error                   : {error}")

    checks = {
        "click delivered": RESULTS["clicked"],
        "text typed exactly": RESULTS["typed"] == EXPECTED_TEXT,
        "scroll moved the view": RESULTS["scrolled"] > 0,
        "no errors": not RESULTS["errors"],
    }
    for label, ok in checks.items():
        print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    passed = all(checks.values())
    print("\nPASS" if passed else "\nFAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
