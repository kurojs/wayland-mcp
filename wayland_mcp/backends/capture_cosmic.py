"""Capture via cosmic-screenshot, COSMIC's own front-end to its portal.

Chosen first under COSMIC: it is silent, needs no permission dialog, and avoids
the portal round-trip. It writes into a directory of its own choosing and prints
the resulting path, so the file is moved to where the caller asked.
"""
import logging
import os
import shutil
import subprocess
import tempfile

from wayland_mcp.backends.base import Capabilities, CaptureBackend


class CosmicScreenshotBackend(CaptureBackend):
    """`cosmic-screenshot --interactive=false --notify=false --save-dir DIR`."""

    name = "cosmic-screenshot"
    priority = 80
    requires = "the cosmic-screenshot binary (shipped with COSMIC)"

    def supports(self, caps: Capabilities) -> bool:
        return caps.has("cosmic-screenshot") and caps.is_wayland

    def capture(self, output_path, mode="auto", geometry=None, include_mouse=True) -> dict:
        if mode == "region":
            # cosmic-screenshot only does regions through its interactive UI, which
            # would block an MCP call waiting for a human. Say so instead of hanging.
            return {
                "success": False,
                "error": "cosmic-screenshot cannot capture a region non-interactively; "
                         "use the portal backend or install grim+slurp",
            }
        with tempfile.TemporaryDirectory(prefix="wayland-mcp-") as tmpdir:
            cmd = [
                "cosmic-screenshot",
                "--interactive=false",
                "--notify=false",
                "--modal=false",
                "--save-dir",
                tmpdir,
            ]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30, check=False
                )
            except (OSError, subprocess.SubprocessError) as err:
                return {"success": False, "error": f"cosmic-screenshot failed: {err}"}
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"cosmic-screenshot exited {result.returncode}: "
                             f"{result.stderr.strip()}",
                }
            produced = _only_file(tmpdir, result.stdout.strip())
            if not produced:
                return {
                    "success": False,
                    "error": "cosmic-screenshot reported success but wrote no file",
                }
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
            shutil.move(produced, output_path)
            logging.info("cosmic-screenshot captured to %s", output_path)
            return {"success": True, "filename": output_path}


def _only_file(tmpdir: str, reported: str):
    """Path of the captured file: what the tool printed, else the one file present."""
    if reported and os.path.isfile(reported):
        return reported
    entries = [os.path.join(tmpdir, e) for e in os.listdir(tmpdir)]
    files = [e for e in entries if os.path.isfile(e)]
    return files[0] if len(files) == 1 else None
