"""MouseController: a thin facade over the selected pointer backend.

The public surface (move_to, move_to_absolute, click, drag, scroll) is unchanged,
so anything built against the previous evemu-only implementation keeps working.
What changed is that construction no longer scans /dev/input and no longer raises
when nothing there is writable: the backend is chosen lazily, on first use, and a
machine with no pointer path reports that as an error from the call rather than by
killing the process at import.
"""
import logging
import time
from typing import Optional

from wayland_mcp.backends.base import BackendUnavailable, InputBackend
from wayland_mcp.backends.detect import select_pointer_backend


class MouseController:
    """Pointer control through whichever backend this machine supports."""

    def __init__(self, device: Optional[str] = None, backend: Optional[InputBackend] = None):
        """
        Args:
            device: Legacy evemu device path. Only meaningful for the evemu
                backend; kept so existing callers and configs still work.
            backend: Pre-selected backend, mainly for tests.
        """
        self._device = device
        self._backend = backend

    @property
    def backend(self) -> InputBackend:
        """The pointer backend, selected on first access."""
        if self._backend is None:
            self._backend = select_pointer_backend()
            if self._device and hasattr(self._backend, "_pointer"):
                self._backend._pointer = self._device  # pylint: disable=protected-access
        return self._backend

    @property
    def device(self):
        """Legacy attribute: the evemu device path, or the backend name.

        Older code logged ``mouse.device`` at startup; it stays readable without
        forcing a backend to be selected.
        """
        if self._device:
            return self._device
        if self._backend is None:
            return "not yet selected"
        return getattr(self._backend, "_pointer", None) or self._backend.name

    def available(self) -> bool:
        """True when a pointer backend exists, without raising."""
        try:
            return self.backend is not None
        except BackendUnavailable:
            return False

    def move_to(self, x, y):
        """Move the pointer *relative* to its current position."""
        return self.backend.move_pointer(int(x), int(y), relative=True)

    def move_to_absolute(self, x, y):
        """Move the pointer to absolute screen coordinates.

        Backends without an absolute axis (evemu) approximate this by homing to
        the top-left corner first, which is why they report absolute_pointer=False.
        """
        backend = self.backend
        if backend.absolute_pointer:
            return backend.move_pointer(int(x), int(y), relative=False)
        logging.info(
            "%s has no absolute pointer axis; homing then moving relatively",
            backend.name,
        )
        return backend.move_pointer(int(x), int(y), relative=False)

    def move_to_zero(self):
        """Send the pointer to the top-left corner."""
        return self.move_to_absolute(0, 0)

    def click(self, button="left"):
        """Press and release a mouse button at the current position."""
        return self.backend.click(button=button)

    def drag(self, x1, y1, x2, y2):
        """Press at (x1,y1), move to (x2,y2), release.

        The intermediate step matters: many toolkits only start a drag once they
        have seen motion while the button is held.
        """
        backend = self.backend
        self.move_to_absolute(x1, y1)
        time.sleep(0.1)
        backend.click(press=True, release=False)
        time.sleep(0.1)
        midpoint = ((x1 + x2) // 2, (y1 + y2) // 2)
        self.move_to_absolute(*midpoint)
        time.sleep(0.05)
        self.move_to_absolute(x2, y2)
        time.sleep(0.15)
        return backend.click(press=False, release=True)

    def scroll(self, amount, horizontal=False):
        """Scroll by *amount* notches; positive is up (or left)."""
        return self.backend.scroll(int(amount), horizontal=horizontal)

    def close(self):
        """Release the backend's session, if it holds one."""
        if self._backend is not None:
            self._backend.close()
