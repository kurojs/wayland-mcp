"""Input via evemu-event -- last resort, and never a requirement.

This is upstream's only input path. It writes raw events to a /dev/input device,
so it needs that device to be writable. Upstream shipped a setup.sh that made
*every* input device world-writable (mode 0666, via a persistent udev rule) and
setuid on evemu-event, which turns any local process into a keylogger.

This fork never changes those permissions. The backend activates only if a device
happens to be writable already, and it always loses to an unprivileged backend.
"""
import logging
import os
import subprocess
import time
from typing import Optional

from wayland_mcp.backends.base import Capabilities, InputBackend
from wayland_mcp.keymap import KEY_MAP


class EvemuBackend(InputBackend):
    """`evemu-event DEVICE --type ... --code ... --value ...`."""

    name = "evemu"
    priority = 10
    can_keyboard = True
    can_pointer = True
    #: evemu emits REL_X/REL_Y, so absolute moves are only ever approximated.
    absolute_pointer = False
    requires = (
        "evemu-event plus an already-writable /dev/input/event* device; this fork "
        "will not widen those permissions for you"
    )

    def __init__(self, device: Optional[str] = None):
        self._pointer = device
        self._keyboard = device

    def supports(self, caps: Capabilities) -> bool:
        return caps.has("evemu-event") and caps.writable_input_device

    # -- device discovery --------------------------------------------------

    def _find(self, *required) -> Optional[str]:
        """First writable device whose evemu description has all *required* caps."""
        if not os.path.isdir("/dev/input"):
            return None
        for entry in sorted(os.listdir("/dev/input")):
            if not entry.startswith("event"):
                continue
            path = f"/dev/input/{entry}"
            if not os.access(path, os.W_OK):
                continue
            try:
                desc = subprocess.check_output(
                    ["evemu-describe", path], text=True, timeout=2
                )
            except (OSError, subprocess.SubprocessError):
                continue
            if all(capability in desc for capability in required):
                return path
        return None

    def _pointer_device(self) -> str:
        if not self._pointer:
            self._pointer = self._find("BTN_LEFT", "REL_X")
        if not self._pointer:
            raise RuntimeError("no writable pointer device in /dev/input")
        return self._pointer

    def _keyboard_device(self) -> str:
        if not self._keyboard:
            self._keyboard = self._find("KEY_A", "KEY_ENTER")
        if not self._keyboard:
            raise RuntimeError("no writable keyboard device in /dev/input")
        return self._keyboard

    # -- events ------------------------------------------------------------

    def _event(self, device, ev_type, code, value) -> bool:
        cmd = [
            "evemu-event", device, "--type", ev_type, "--code", code,
            "--value", str(value), "--sync",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"evemu-event exited {result.returncode}: {(result.stderr or '').strip()}"
            )
        return True

    def move_pointer(self, x, y, relative=False) -> bool:
        device = self._pointer_device()
        if not relative:
            # No absolute axis on a relative device: slam the pointer into the
            # top-left corner first, then walk out. Approximate by nature.
            logging.debug("evemu has no absolute axis; homing to (0,0) first")
            self._event(device, "EV_REL", "REL_X", -50000)
            self._event(device, "EV_REL", "REL_Y", -50000)
        self._event(device, "EV_REL", "REL_X", int(x))
        self._event(device, "EV_REL", "REL_Y", int(y))
        time.sleep(0.05)
        return True

    def click(self, button="left", press=True, release=True) -> bool:
        device = self._pointer_device()
        code = {"left": "BTN_LEFT", "right": "BTN_RIGHT", "middle": "BTN_MIDDLE"}.get(button)
        if code is None:
            raise ValueError(f"unknown mouse button {button!r}")
        if press:
            self._event(device, "EV_KEY", code, 1)
            time.sleep(0.05)
        if release:
            self._event(device, "EV_KEY", code, 0)
        return True

    def scroll(self, amount, horizontal=False) -> bool:
        device = self._pointer_device()
        axis = "REL_HWHEEL" if horizontal else "REL_WHEEL"
        self._event(device, "EV_REL", axis, int(amount))
        self._event(device, "EV_REL", f"{axis}_HI_RES", int(amount) * 120)
        return True

    def type_text(self, text) -> bool:
        device = self._keyboard_device()
        for char in text:
            name = KEY_MAP.get(char.lower())
            if not name:
                logging.warning("No evemu key for %r; skipped", char)
                continue
            shift = char.isupper()
            if shift:
                self._event(device, "EV_KEY", "KEY_LEFTSHIFT", 1)
            self._event(device, "EV_KEY", name, 1)
            time.sleep(0.02)
            self._event(device, "EV_KEY", name, 0)
            if shift:
                self._event(device, "EV_KEY", "KEY_LEFTSHIFT", 0)
        return True

    def press_key(self, key) -> bool:
        device = self._keyboard_device()
        parts = [part for part in key.split("+") if part] or [key]
        names = []
        for part in parts:
            name = KEY_MAP.get(part.lower())
            if not name:
                raise ValueError(f"unknown key {part!r} in {key!r}")
            names.append(name)
        for name in names[:-1]:
            self._event(device, "EV_KEY", name, 1)
        try:
            self._event(device, "EV_KEY", names[-1], 1)
            self._event(device, "EV_KEY", names[-1], 0)
        finally:
            for name in reversed(names[:-1]):
                self._event(device, "EV_KEY", name, 0)
        return True
