"""Desktop-specific screenshot tools, kept for upstream compatibility.

These are the backends the original cascade used. Behaviour is preserved; the
only change is that each is now gated on its own binary being present instead of
being tried blindly, and none of them touches the user's settings.
"""
import subprocess
from typing import List

from wayland_mcp.backends.base import Capabilities, CaptureBackend


class _ToolBackend(CaptureBackend):
    binary = ""
    timeout = 30

    def supports(self, caps: Capabilities) -> bool:
        return caps.has(self.binary)

    def requirements(self) -> str:
        return f"the {self.binary} binary"

    def build_command(self, output_path: str, include_mouse: bool) -> List[str]:
        raise NotImplementedError

    def capture(self, output_path, mode="auto", geometry=None, include_mouse=True) -> dict:
        cmd = self.build_command(output_path, include_mouse)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout, check=False
            )
        except (OSError, subprocess.SubprocessError) as err:
            return {"success": False, "error": f"{self.binary} failed: {err}"}
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"{self.binary} exited {result.returncode}: "
                         f"{(result.stderr or '').strip()}",
            }
        return {"success": True, "filename": output_path}


class KsnipBackend(_ToolBackend):
    name = "ksnip"
    binary = "ksnip"
    priority = 60

    def build_command(self, output_path, include_mouse):
        cmd = ["ksnip", "-f", output_path, "-m"]
        if include_mouse:
            cmd.append("-c")
        return cmd


class GnomeScreenshotBackend(_ToolBackend):
    name = "gnome-screenshot"
    binary = "gnome-screenshot"
    priority = 55

    def build_command(self, output_path, include_mouse):
        cmd = ["gnome-screenshot", "-f", output_path]
        if include_mouse:
            cmd.append("--include-pointer")
        return cmd


class SpectacleBackend(_ToolBackend):
    name = "spectacle"
    binary = "spectacle"
    priority = 50

    def build_command(self, output_path, include_mouse):
        cmd = [
            "spectacle", "--fullscreen", "--background", "--nonotify",
            "--output", output_path,
        ]
        if include_mouse:
            cmd.append("--pointer")
        return cmd
