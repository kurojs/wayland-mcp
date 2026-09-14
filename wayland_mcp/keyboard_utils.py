"""KeyboardController: a thin facade over the selected keyboard backend.

Same story as MouseController: the public surface (type_text, press_key,
send_key_combo) is preserved, the /dev/input scan and the constructor-time
RuntimeError are gone, and text is no longer lowercased on the way out -- upstream
called ``text.lower()``, which made typing a capital letter impossible.
"""
from typing import List, Optional

from wayland_mcp.backends.base import BackendUnavailable, InputBackend
from wayland_mcp.backends.detect import select_keyboard_backend


class KeyboardController:
    """Keyboard input through whichever backend this machine supports."""

    def __init__(self, device: Optional[str] = None, backend: Optional[InputBackend] = None):
        """
        Args:
            device: Legacy evemu device path, honoured only by the evemu backend.
            backend: Pre-selected backend, mainly for tests.
        """
        self._device = device
        self._backend = backend

    @property
    def backend(self) -> InputBackend:
        """The keyboard backend, selected on first access."""
        if self._backend is None:
            self._backend = select_keyboard_backend()
            if self._device and hasattr(self._backend, "_keyboard"):
                self._backend._keyboard = self._device  # pylint: disable=protected-access
        return self._backend

    @property
    def device(self):
        """Legacy attribute; see MouseController.device."""
        if self._device:
            return self._device
        if self._backend is None:
            return "not yet selected"
        return getattr(self._backend, "_keyboard", None) or self._backend.name

    def available(self) -> bool:
        """True when a keyboard backend exists, without raising."""
        try:
            return self.backend is not None
        except BackendUnavailable:
            return False

    def type_text(self, text: str) -> bool:
        """Type *text* as-is, case included."""
        return self.backend.type_text(text)

    def press_key(self, key: str) -> bool:
        """Press a key or a combination such as ``"ctrl+shift+t"``."""
        return self.backend.press_key(key)

    def send_key_combo(self, keys: List[str]) -> bool:
        """Press a combination given as a list.

        Accepts both plain names (``["ctrl", "a"]``) and the ``KEY_*`` spellings
        the evemu-era API used (``["KEY_LEFTCTRL", "KEY_A"]``).
        """
        return self.press_key("+".join(_plain(key) for key in keys))

    def close(self):
        """Release the backend's session, if it holds one."""
        if self._backend is not None:
            self._backend.close()


_KEY_PREFIX_ALIASES = {
    "leftctrl": "ctrl", "rightctrl": "ctrl",
    "leftshift": "shift", "rightshift": "shift",
    "leftalt": "alt", "rightalt": "alt",
    "leftmeta": "super", "rightmeta": "super",
}


def _plain(key: str) -> str:
    """Turn ``KEY_LEFTCTRL`` into ``ctrl``; leave anything else alone."""
    if not key.startswith("KEY_"):
        return key
    name = key[4:].lower()
    return _KEY_PREFIX_ALIASES.get(name, name)
