"""Keyboard input via wtype (zwp_virtual_keyboard_manager_v1).

Keyboard only, and only where the compositor advertises the protocol: wlroots
compositors and COSMIC do, GNOME does not. Its advantage over the portal is that
it types immediately with no consent dialog, and it handles characters outside a
US layout because it works in keysyms rather than keycodes.
"""
import subprocess

from wayland_mcp.backends.base import (
    PROTO_VIRTUAL_KEYBOARD,
    Capabilities,
    InputBackend,
)

#: wtype's names for the keys we accept, where they differ from ours.
KEY_NAMES = {
    "enter": "Return", "esc": "Escape", "backspace": "BackSpace",
    "delete": "Delete", "tab": "Tab", "space": "space", "up": "Up",
    "down": "Down", "left": "Left", "right": "Right", "home": "Home",
    "end": "End", "pageup": "Prior", "pagedown": "Next", "insert": "Insert",
    "ctrl": "ctrl", "alt": "alt", "shift": "shift", "super": "logo",
    "meta": "logo",
}
MODIFIERS = {"ctrl", "alt", "shift", "super", "meta", "logo"}


class WtypeBackend(InputBackend):
    """`wtype` for text and key combinations."""

    name = "wtype"
    priority = 60
    can_keyboard = True
    can_pointer = False
    requires = "the wtype binary and a compositor exposing zwp_virtual_keyboard_manager_v1"

    def supports(self, caps: Capabilities) -> bool:
        if not caps.has("wtype") or not caps.is_wayland:
            return False
        if PROTO_VIRTUAL_KEYBOARD in caps.wayland_protocols:
            return True
        # No protocol listing available: wtype itself is the evidence, since it
        # refuses to start without the protocol.
        return not caps.wayland_protocols

    def type_text(self, text) -> bool:
        return self._run(["wtype", "--", text])

    def press_key(self, key) -> bool:
        parts = [part for part in key.split("+") if part] or [key]
        modifiers = [KEY_NAMES.get(p.lower(), p) for p in parts[:-1]]
        main = parts[-1]
        main = KEY_NAMES.get(main.lower(), main) if len(main) > 1 else main
        cmd = ["wtype"]
        for modifier in modifiers:
            cmd += ["-M", modifier]
        cmd += ["-k", main]
        for modifier in reversed(modifiers):
            cmd += ["-m", modifier]
        return self._run(cmd)

    def move_pointer(self, x, y, relative=False) -> bool:
        raise NotImplementedError("wtype has no pointer support")

    def click(self, button="left", press=True, release=True) -> bool:
        raise NotImplementedError("wtype has no pointer support")

    def scroll(self, amount, horizontal=False) -> bool:
        raise NotImplementedError("wtype has no pointer support")

    @staticmethod
    def _run(cmd) -> bool:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"wtype exited {result.returncode}: {(result.stderr or '').strip()}"
            )
        return True
