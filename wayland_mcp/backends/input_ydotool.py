"""Input via ydotool, when /dev/uinput is already writable.

ydotool needs write access to /dev/uinput, which many distributions grant to a
group the user is already in. We only *check* that access -- we never ask for it,
and nothing here runs ydotoold or changes permissions.
"""
import subprocess

from wayland_mcp.backends.base import Capabilities, InputBackend
from wayland_mcp.backends.keycodes import evdev_keycode, parse_combo

BUTTONS = {"left": 0x00, "right": 0x01, "middle": 0x02}


class YdotoolBackend(InputBackend):
    """`ydotool` for pointer and keyboard."""

    name = "ydotool"
    priority = 40
    can_keyboard = True
    can_pointer = True
    absolute_pointer = True
    requires = "the ydotool binary and write access to /dev/uinput (no root needed)"

    def supports(self, caps: Capabilities) -> bool:
        return caps.has("ydotool") and caps.writable_uinput

    def move_pointer(self, x, y, relative=False) -> bool:
        cmd = ["ydotool", "mousemove"]
        if not relative:
            cmd.append("--absolute")
        return self._run(cmd + ["--", str(x), str(y)])

    def click(self, button="left", press=True, release=True) -> bool:
        code = BUTTONS.get(button)
        if code is None:
            raise ValueError(f"unknown mouse button {button!r}")
        # ydotool packs press/release into the high nibble: 0x40 down, 0x80 up.
        mask = code | (0x40 if press else 0) | (0x80 if release else 0)
        return self._run(["ydotool", "click", f"0x{mask:02X}"])

    def scroll(self, amount, horizontal=False) -> bool:
        # ydotool's wheel axis grows downwards, ours grows upwards.
        delta = -int(amount)
        pair = (str(delta), "0") if horizontal else ("0", str(delta))
        return self._run(["ydotool", "mousemove", "--wheel", "--", *pair])

    def type_text(self, text) -> bool:
        return self._run(["ydotool", "type", "--", text])

    def press_key(self, key) -> bool:
        modifiers, main = parse_combo(key)
        sequence = [f"{code}:1" for code in modifiers]
        sequence += [f"{main}:1", f"{main}:0"]
        sequence += [f"{code}:0" for code in reversed(modifiers)]
        return self._run(["ydotool", "key", "--"] + sequence)

    @staticmethod
    def _run(cmd) -> bool:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"ydotool exited {result.returncode}: {(result.stderr or '').strip()}"
            )
        return True


__all__ = ["YdotoolBackend", "evdev_keycode"]
