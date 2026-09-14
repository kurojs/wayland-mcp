"""Capture via grim, for compositors grim can actually reach.

grim speaks zwlr_screencopy_manager_v1 up to 1.4, and gained
ext-image-copy-capture in 1.5. Upstream called grim whenever it was on PATH,
which fails on any compositor that only implements the newer protocol -- COSMIC
being the case that motivated this fork. Availability is therefore gated on the
version *and* on what the compositor advertises.
"""
import logging
import subprocess

from wayland_mcp.backends.base import (
    PROTO_EXT_IMAGE_COPY,
    PROTO_WLR_SCREENCOPY,
    Capabilities,
    CaptureBackend,
)


class GrimBackend(CaptureBackend):
    """`grim [-g GEOMETRY] OUTPUT`, with slurp for interactive regions."""

    name = "grim"
    priority = 70
    requires = (
        "grim, plus either zwlr_screencopy_manager_v1 (any grim) or "
        "ext_image_copy_capture_manager_v1 with grim >= 1.5"
    )

    def supports(self, caps: Capabilities) -> bool:
        if not caps.has("grim") or not caps.is_wayland:
            return False
        if PROTO_WLR_SCREENCOPY in caps.wayland_protocols:
            return True
        if PROTO_EXT_IMAGE_COPY in caps.wayland_protocols:
            # Only 1.5+ learned this protocol. An unreadable version is treated as
            # old, so we degrade to the portal rather than fail at capture time.
            return caps.version("grim") >= (1, 5)
        # No protocol information at all (no wayland-info installed): trust grim
        # only if nothing suggests it cannot work. Being wrong here is cheap --
        # capture returns an error and the caller can force another backend.
        return not caps.wayland_protocols

    def capture(self, output_path, mode="auto", geometry=None, include_mouse=True) -> dict:
        if include_mouse:
            logging.debug("grim cannot draw the cursor; capturing without it")
        cmd = ["grim"]
        if mode == "region":
            geometry = geometry or _pick_region()
            if not geometry:
                return {
                    "success": False,
                    "error": "region capture needs a geometry, or slurp to select one",
                }
            # Upstream passed the literal string "$(slurp)" here because the list
            # form of subprocess does not run a shell. slurp is run separately.
            cmd += ["-g", geometry]
        cmd.append(output_path)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=20, check=False
            )
        except (OSError, subprocess.SubprocessError) as err:
            return {"success": False, "error": f"grim failed: {err}"}
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"grim exited {result.returncode}: {result.stderr.strip()}",
            }
        return {"success": True, "filename": output_path}


def _pick_region():
    """Ask slurp for a geometry. Returns None when slurp is absent or cancelled."""
    try:
        result = subprocess.run(
            ["slurp"], capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None
