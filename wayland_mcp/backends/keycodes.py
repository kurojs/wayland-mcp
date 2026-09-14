"""Key names and characters to Linux evdev keycodes.

The portal's NotifyKeyboardKeycode and evemu both ultimately want the numeric
codes from include/uapi/linux/input-event-codes.h. Upstream's keymap.py maps to
``KEY_*`` *names* for evemu; this module keeps those names working and adds the
numbers, so both backends share one source of truth.

Layout caveat: keycodes are positions on the keyboard, not characters. The
mapping below is the US/QWERTY interpretation, which is what every keycode-level
tool assumes. On another layout, ``type_text`` produces whatever those positions
mean there -- the portal's keysym path would be needed to do better, and it is
not implemented by every desktop.
"""
from typing import List, Optional, Tuple

from wayland_mcp.keymap import KEY_MAP

#: Name -> evdev code, for everything KEY_MAP can name.
KEY_CODES = {
    "KEY_ESC": 1, "KEY_1": 2, "KEY_2": 3, "KEY_3": 4, "KEY_4": 5, "KEY_5": 6,
    "KEY_6": 7, "KEY_7": 8, "KEY_8": 9, "KEY_9": 10, "KEY_0": 11,
    "KEY_MINUS": 12, "KEY_EQUAL": 13, "KEY_BACKSPACE": 14, "KEY_TAB": 15,
    "KEY_Q": 16, "KEY_W": 17, "KEY_E": 18, "KEY_R": 19, "KEY_T": 20,
    "KEY_Y": 21, "KEY_U": 22, "KEY_I": 23, "KEY_O": 24, "KEY_P": 25,
    "KEY_LEFTBRACE": 26, "KEY_RIGHTBRACE": 27, "KEY_ENTER": 28,
    "KEY_LEFTCTRL": 29, "KEY_A": 30, "KEY_S": 31, "KEY_D": 32, "KEY_F": 33,
    "KEY_G": 34, "KEY_H": 35, "KEY_J": 36, "KEY_K": 37, "KEY_L": 38,
    "KEY_SEMICOLON": 39, "KEY_APOSTROPHE": 40, "KEY_GRAVE": 41,
    "KEY_LEFTSHIFT": 42, "KEY_BACKSLASH": 43, "KEY_Z": 44, "KEY_X": 45,
    "KEY_C": 46, "KEY_V": 47, "KEY_B": 48, "KEY_N": 49, "KEY_M": 50,
    "KEY_COMMA": 51, "KEY_DOT": 52, "KEY_SLASH": 53, "KEY_RIGHTSHIFT": 54,
    "KEY_KPASTERISK": 55, "KEY_LEFTALT": 56, "KEY_SPACE": 57,
    "KEY_CAPSLOCK": 58, "KEY_F1": 59, "KEY_F2": 60, "KEY_F3": 61,
    "KEY_F4": 62, "KEY_F5": 63, "KEY_F6": 64, "KEY_F7": 65, "KEY_F8": 66,
    "KEY_F9": 67, "KEY_F10": 68, "KEY_NUMLOCK": 69, "KEY_SCROLLLOCK": 70,
    "KEY_F11": 87, "KEY_F12": 88, "KEY_RIGHTCTRL": 97, "KEY_SYSRQ": 99,
    "KEY_RIGHTALT": 100, "KEY_HOME": 102, "KEY_UP": 103, "KEY_PAGEUP": 104,
    "KEY_LEFT": 105, "KEY_RIGHT": 106, "KEY_END": 107, "KEY_DOWN": 108,
    "KEY_PAGEDOWN": 109, "KEY_INSERT": 110, "KEY_DELETE": 111,
    "KEY_LEFTMETA": 125, "KEY_RIGHTMETA": 126, "KEY_COMPOSE": 127,
    "KEY_PRINT": 99, "KEY_PAUSE": 119, "KEY_MENU": 139,
}

#: Characters reachable only with shift held, and the unshifted key they sit on.
SHIFTED_CHARS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
    "*": "8", "(": "9", ")": "0", "_": "-", "+": "=", "{": "[", "}": "]",
    "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".", "?": "/", "~": "`",
}

#: Punctuation that types directly.
PUNCTUATION = {
    "-": "KEY_MINUS", "=": "KEY_EQUAL", "[": "KEY_LEFTBRACE",
    "]": "KEY_RIGHTBRACE", ";": "KEY_SEMICOLON", "'": "KEY_APOSTROPHE",
    "`": "KEY_GRAVE", "\\": "KEY_BACKSLASH", ",": "KEY_COMMA",
    ".": "KEY_DOT", "/": "KEY_SLASH", " ": "KEY_SPACE", "\n": "KEY_ENTER",
    "\t": "KEY_TAB",
}


def code_for_name(name: str) -> Optional[int]:
    """evdev code for a ``KEY_*`` name, or None when unknown."""
    return KEY_CODES.get(name)


def evdev_keycode(char: str) -> Tuple[Optional[int], bool]:
    """``(keycode, needs_shift)`` for a single character or a key name.

    Returns ``(None, False)`` when the character has no keycode on a US layout,
    which is how callers know to skip it rather than type something wrong.
    """
    if len(char) == 1:
        if char.isupper():
            return code_for_name(f"KEY_{char}"), True
        if char in SHIFTED_CHARS:
            base = SHIFTED_CHARS[char]
            name = PUNCTUATION.get(base) or f"KEY_{base.upper()}"
            return code_for_name(name), True
        if char in PUNCTUATION:
            return code_for_name(PUNCTUATION[char]), False
        if char.isalnum():
            return code_for_name(f"KEY_{char.upper()}"), False
        return None, False
    # A key name such as "enter" or "f5", via upstream's KEY_MAP.
    name = KEY_MAP.get(char.lower())
    return (code_for_name(name) if name else None), False


#: X11 keysyms for the named keys, used by the portal's keysym path.
#
# Keysyms describe *characters and functions*, not positions, so they are immune to
# the keyboard layout. A keycode-based type_text on an AZERTY layout writes
# "QSQP 'é" when asked for "ASAP 42"; the keysym path writes what was asked.
KEYSYMS = {
    "enter": 0xFF0D, "return": 0xFF0D, "esc": 0xFF1B, "escape": 0xFF1B,
    "backspace": 0xFF08, "tab": 0xFF09, "space": 0x0020, "delete": 0xFFFF,
    "insert": 0xFF63, "home": 0xFF50, "end": 0xFF57, "pageup": 0xFF55,
    "pagedown": 0xFF56, "up": 0xFF52, "down": 0xFF54, "left": 0xFF51,
    "right": 0xFF53, "capslock": 0xFFE5, "menu": 0xFF67, "print": 0xFF61,
    "pause": 0xFF13,
    "shift": 0xFFE1, "ctrl": 0xFFE3, "control": 0xFFE3, "alt": 0xFFE9,
    "super": 0xFFEB, "meta": 0xFFEB,
}
KEYSYMS.update({f"f{n}": 0xFFBE + n - 1 for n in range(1, 13)})


def keysym_for_char(char: str):
    """X11 keysym for a single character, or None.

    Latin-1 characters are their own codepoint; everything else uses the Unicode
    range X11 reserves for exactly this (0x01000000 + codepoint).
    """
    if len(char) != 1:
        return None
    codepoint = ord(char)
    if codepoint in (0x0A, 0x0D):
        return KEYSYMS["enter"]
    if codepoint == 0x09:
        return KEYSYMS["tab"]
    if 0x20 <= codepoint <= 0xFF:
        return codepoint
    return 0x01000000 + codepoint


def keysym_for(name: str):
    """Keysym for a character or a key name such as ``"enter"`` or ``"f5"``."""
    if len(name) == 1:
        return keysym_for_char(name)
    return KEYSYMS.get(name.lower())


def parse_keysym_combo(key: str) -> Tuple[List[int], int]:
    """Split ``"ctrl+shift+a"`` into modifier keysyms and the final keysym."""
    parts = [part for part in key.split("+") if part] or [key]
    symbols = []
    for part in parts:
        symbol = keysym_for(part if len(part) == 1 else part.lower())
        if symbol is None:
            raise ValueError(f"unknown key {part!r} in {key!r}")
        symbols.append(symbol)
    return symbols[:-1], symbols[-1]


def parse_combo(key: str) -> Tuple[List[int], int]:
    """Split ``"ctrl+shift+a"`` into modifier keycodes and the final keycode.

    Raises ValueError naming the offending part, so the MCP caller learns which
    key was wrong instead of getting a bare False.
    """
    parts = [part for part in key.split("+") if part] or [key]
    codes = []
    for part in parts:
        code, shift = evdev_keycode(part if len(part) == 1 else part.lower())
        if code is None:
            raise ValueError(f"unknown key {part!r} in {key!r}")
        if shift:
            codes.append((code_for_name("KEY_LEFTSHIFT"), code))
        else:
            codes.append((None, code))
    modifiers = [code for implicit_shift, code in codes[:-1] for code in [code]]
    implicit_shift, main = codes[-1]
    if implicit_shift is not None:
        modifiers.append(implicit_shift)
    return modifiers, main
