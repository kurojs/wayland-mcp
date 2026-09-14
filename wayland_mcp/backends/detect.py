"""Capability-driven backend selection.

The registries below are ordered by descending priority; selection walks them
and returns the first backend whose ``supports(caps)`` holds. Two rules matter:

* privileged paths always lose. ``evemu`` needs a writable /dev/input, so it
  sits at the bottom and is only reached when nothing else can work.
* an unknown capability is never optimistic. A tool whose version cannot be
  read is trusted only on the protocol it has always spoken.
"""
import logging
import os
from typing import List, Optional, Type

from wayland_mcp.backends.base import (
    BackendUnavailable,
    Capabilities,
    CaptureBackend,
    InputBackend,
)
from wayland_mcp.backends.capture_cosmic import CosmicScreenshotBackend
from wayland_mcp.backends.capture_grim import GrimBackend
from wayland_mcp.backends.capture_legacy import (
    GnomeScreenshotBackend,
    KsnipBackend,
    SpectacleBackend,
)
from wayland_mcp.backends.capture_portal import PortalScreenshotBackend
from wayland_mcp.backends.input_evemu import EvemuBackend
from wayland_mcp.backends.input_portal import PortalRemoteDesktopBackend
from wayland_mcp.backends.input_wtype import WtypeBackend
from wayland_mcp.backends.input_ydotool import YdotoolBackend

CAPTURE_BACKENDS: List[Type[CaptureBackend]] = [
    CosmicScreenshotBackend,   # 80: native, silent, no portal dialog
    GrimBackend,               # 70: wlroots and any compositor grim can reach
    KsnipBackend,              # 60: upstream's first choice, kept
    GnomeScreenshotBackend,    # 55
    SpectacleBackend,          # 50
    PortalScreenshotBackend,   # 20: universal fallback
]

INPUT_BACKENDS: List[Type[InputBackend]] = [
    PortalRemoteDesktopBackend,  # 80: unprivileged, pointer + keyboard, cross-desktop
    WtypeBackend,                # 60: keyboard only, needs virtual-keyboard protocol
    YdotoolBackend,              # 40: needs writable /dev/uinput
    EvemuBackend,                # 10: needs writable /dev/input, last resort
]

ENV_CAPTURE_BACKEND = "WAYLAND_MCP_CAPTURE_BACKEND"
ENV_INPUT_BACKEND = "WAYLAND_MCP_INPUT_BACKEND"


def _select(registry, caps, kind, preferred=None, predicate=None):
    candidates = [cls() for cls in registry]
    candidates.sort(key=lambda backend: backend.priority, reverse=True)
    if predicate is not None:
        candidates = [backend for backend in candidates if predicate(backend)]

    if preferred:
        for backend in candidates:
            if backend.name != preferred:
                continue
            if backend.supports(caps):
                return backend
            raise BackendUnavailable(
                f"{kind} backend {preferred!r} was requested but is not usable here: "
                f"{backend.requirements()}"
            )
        raise BackendUnavailable(
            f"unknown {kind} backend {preferred!r}; known: "
            + ", ".join(backend.name for backend in candidates)
        )

    for backend in candidates:
        if backend.supports(caps):
            logging.info("Selected %s backend: %s", kind, backend.name)
            return backend

    raise BackendUnavailable(
        f"no usable {kind} backend on this system. Tried, and what each needs:\n"
        + "\n".join(f"  - {b.name}: {b.requirements()}" for b in candidates)
    )


def select_capture_backend(
    caps: Optional[Capabilities] = None, preferred: Optional[str] = None
) -> CaptureBackend:
    """Pick the best screen-capture backend for *caps*."""
    caps = caps if caps is not None else Capabilities.detect()
    preferred = preferred or os.environ.get(ENV_CAPTURE_BACKEND) or None
    return _select(CAPTURE_BACKENDS, caps, "capture", preferred)


def select_keyboard_backend(
    caps: Optional[Capabilities] = None, preferred: Optional[str] = None
) -> InputBackend:
    """Pick the best keyboard backend for *caps*."""
    caps = caps if caps is not None else Capabilities.detect()
    preferred = preferred or os.environ.get(ENV_INPUT_BACKEND) or None
    return _select(
        INPUT_BACKENDS, caps, "keyboard", preferred, lambda b: b.can_keyboard
    )


def select_pointer_backend(
    caps: Optional[Capabilities] = None, preferred: Optional[str] = None
) -> InputBackend:
    """Pick the best pointer backend for *caps*."""
    caps = caps if caps is not None else Capabilities.detect()
    preferred = preferred or os.environ.get(ENV_INPUT_BACKEND) or None
    return _select(INPUT_BACKENDS, caps, "pointer", preferred, lambda b: b.can_pointer)
