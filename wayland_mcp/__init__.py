"""Wayland MCP package initialization.

Nothing heavy is imported at package level on purpose: importing the package
used to pull in server_mcp, which built a MouseController eagerly and raised
RuntimeError on any machine whose /dev/input is not world-writable. Even
``import wayland_mcp.app`` failed. Names below resolve lazily instead.
"""
from typing import Any

__all__ = [
    "VLMAgent",
    "capture_screenshot",
    "add_rulers",
    "MouseController",
    "main",
]

_LAZY = {
    "VLMAgent": ("wayland_mcp.app", "VLMAgent"),
    "capture_screenshot": ("wayland_mcp.app", "capture_screenshot"),
    "add_rulers": ("wayland_mcp.add_rulers", "add_rulers"),
    "MouseController": ("wayland_mcp.mouse_utils", "MouseController"),
    "main": ("wayland_mcp.server_mcp", "main"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr = _LAZY[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    from importlib import import_module

    return getattr(import_module(module_name), attr)


def __dir__():
    return sorted(__all__)
