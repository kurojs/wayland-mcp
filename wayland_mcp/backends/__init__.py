"""Capture and input backends, selected by capability at runtime.

Import the selectors from :mod:`wayland_mcp.backends.detect`; nothing here opens
a session or touches the system at import time.
"""
from wayland_mcp.backends.base import (
    BackendUnavailable,
    Capabilities,
    CaptureBackend,
    InputBackend,
)

__all__ = [
    "BackendUnavailable",
    "Capabilities",
    "CaptureBackend",
    "InputBackend",
]
