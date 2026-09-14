"""Wayland MCP server with action chaining support.
Provides tools for:
- Mouse control (move, click, drag, scroll)
- Keyboard input (typing, key presses)
- Screenshot capture and analysis
- Action chaining (combining multiple actions)
Tool Usage:
All tools are accessible via the MCP protocol using the @mcp.tool() decorator.
Tools can be called individually or chained together.
Action Chaining Syntax:
  chain:action1;action2;action3
Where actions are in format:
  type:text
  press:key
  click:x,y
  drag:x1,y1:x2,y2
Example Chains:
  chain:click:100,200;type:hello;press:Enter
  chain:drag:50,50:100,100;click:200,200
"""
import logging
import os
import json
from typing import Optional, Tuple
from fastmcp import FastMCP
from wayland_mcp.chain_processor import ChainProcessor, register_handler
from wayland_mcp.mouse_utils import MouseController
from wayland_mcp.keyboard_utils import KeyboardController
from wayland_mcp.screen_utils import ScreenController
from wayland_mcp import session_env
from wayland_mcp.backends.base import BackendUnavailable
# Recover XDG_RUNTIME_DIR / DBUS_SESSION_BUS_ADDRESS / WAYLAND_DISPLAY before any
# capability probing: MCP stdio clients strip them, and without them every backend
# looks unavailable. Must run before the first Capabilities.detect().
session_env.restore()

# --- Logging ------------------------------------------------------------------
LOG_FILE = os.environ.get("WAYLAND_MCP_LOG", "/tmp/wayland-mcp.log")
log_handler = logging.FileHandler(LOG_FILE)
log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(log_handler)
logging.getLogger().setLevel(logging.INFO)

# --- VLM configuration, entirely optional -------------------------------------
# The VLM is a feature, not a dependency: the server must start and capture
# without any API key. Upstream also read ~/.roo/mcp.json looking for a key, and
# logged the first 15 characters of whatever it found. Both are gone -- the config
# file read is opt-in via WAYLAND_MCP_CONFIG, and keys are never logged.
VLM_ENV_KEYS = ("AZURE_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY")


def _api_key_from_env():
    for name in VLM_ENV_KEYS:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def _api_key_from_config():
    """Read a key from an explicitly configured JSON file, or return ""."""
    path = os.environ.get("WAYLAND_MCP_CONFIG")
    if not path:
        return ""
    provider = os.environ.get("VLM_PROVIDER", "openrouter")
    wanted = {
        "gemini": "GEMINI_API_KEY",
        "azure": "AZURE_API_KEY",
    }.get(provider, "OPENROUTER_API_KEY")
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, json.JSONDecodeError) as err:
        logging.warning("WAYLAND_MCP_CONFIG %s could not be read: %s", path, err)
        return ""
    for server in (config.get("mcpServers") or {}).values():
        key = (server.get("env") or {}).get(wanted)
        if key:
            return key
    return ""


def vlm_configured() -> bool:
    """True when a VLM provider has a key available."""
    return bool(_api_key_from_env() or _api_key_from_config())


def get_vlm_agent():
    """Build a VLMAgent from the current environment, on demand."""
    from wayland_mcp.app import VLMAgent  # pylint: disable=import-outside-toplevel

    provider = os.environ.get("VLM_PROVIDER", "openrouter")
    logging.info("Initializing VLM agent for provider %s (key present: %s)",
                 provider, "yes" if vlm_configured() else "no")
    return VLMAgent(_api_key_from_env() or _api_key_from_config(), provider=provider)


NO_VLM_ERROR = (
    "No VLM provider is configured. Set OPENROUTER_API_KEY, GEMINI_API_KEY or "
    "AZURE_API_KEY (with VLM_PROVIDER) to enable image analysis. Screen capture "
    "and input control work without it."
)

# --- Controllers, built on first use ------------------------------------------
# Upstream instantiated MouseController() and KeyboardController() here, at module
# level. Both scanned /dev/input and raised RuntimeError when nothing was
# writable, so the server died at import on any machine with sane permissions.
# They are lazy now, and a missing input path is reported per tool call: capture
# stays usable when input control is not.
_mouse = None
_keyboard = None
_screen = None


def get_mouse():
    """The MouseController, constructed once."""
    global _mouse  # pylint: disable=global-statement
    if _mouse is None:
        _mouse = MouseController()
    return _mouse


def get_keyboard():
    """The KeyboardController, constructed once."""
    global _keyboard  # pylint: disable=global-statement
    if _keyboard is None:
        _keyboard = KeyboardController()
    return _keyboard


def get_screen():
    """The ScreenController, constructed once, with lazy VLM initialization."""
    global _screen  # pylint: disable=global-statement
    if _screen is None:
        _screen = ScreenController(None)
        _screen.set_vlm_factory(get_vlm_agent)
    return _screen


def _input_error(err) -> dict:
    """Turn a backend failure into an MCP result the caller can act on."""
    logging.error("Input unavailable: %s", err)
    return {"success": False, "error": str(err)}


# Server configuration
try:
    PORT = int(os.environ.get("WAYLAND_MCP_PORT", "4999"))
except ValueError:
    PORT = 4999
mcp = FastMCP("Wayland MCP")
logging.info("Initialized FastMCP server on port %d", PORT)
# Mouse control tools
@mcp.tool()
def move_mouse(x: int, y: int, relative: bool = False) -> dict:
    """Move mouse to specified screen coordinates.
    Args:
        x: Horizontal position (0 = left)
        y: Vertical position (0 = top)
        relative: If True, moves relative to current position (default: False)
    Returns:
        dict: {
            'success': bool,
            'error': str (if failed)
        }
    Examples:
        move_mouse(100, 200)  # Moves to absolute x=100, y=200
        move_mouse(10, 10, relative=True)  # Moves 10px right and down
    """
    try:
        if relative:
            get_mouse().move_to(x, y)
        else:
            print("Moving to absolute coordinates")
            print(f"Moving to x={x}, y={y}")
            get_mouse().move_to_absolute(x, y)
        return {"success": True}
    except (BackendUnavailable, RuntimeError, IOError, ValueError) as e:
        return _input_error(e)
@mcp.tool()
def click_mouse() -> dict:
    """Simulate left mouse click at current position.
    Returns:
        dict: {
            'success': bool,
            'error': str (if failed)
        }
    Example:
        click_mouse()  # Clicks at current cursor position
    """
    try:
        get_mouse().click()
        return {"success": True}
    except (BackendUnavailable, RuntimeError, IOError, ValueError) as e:
        return _input_error(e)
@mcp.tool()
def drag_mouse(x1: int, y1: int, x2: int, y2: int) -> dict:
    """Perform drag operation between coordinates.
    Args:
        x1, y1: Start position
        x2, y2: End position
    Returns:
        dict: {
            'success': bool,
            'error': str (if failed)
        }
    Example:
        drag_mouse(100, 100, 200, 200)  # Drags from (100,100) to (200,200)
    """
    try:
        get_mouse().drag(x1, y1, x2, y2)
        return {"success": True}
    except (BackendUnavailable, RuntimeError, IOError, ValueError) as e:
        return _input_error(e)
@mcp.tool()
def scroll_mouse(amount: int) -> dict:
    """Scroll vertically (positive=up, negative=down).
    Note: Each unit represents one notch on the scroll wheel (120 units = high-definition scroll).
    Typical values range from 2-3 to 5-10 for normal scrolling.
    """
    try:
        get_mouse().scroll(amount)
        return {"success": True}
    except (BackendUnavailable, RuntimeError, IOError, ValueError) as e:
        return _input_error(e)
# Media capture tools
@mcp.tool()
def capture_screenshot(filename: str = "screenshot.png", include_mouse: bool = True) -> dict:
    """Capture the screen, with measurement rulers drawn on the result.

    Args:
        filename: Where to write the PNG.
        include_mouse: Draw the cursor, when the selected backend can.

    Returns:
        dict: {'success': bool, 'filename': str, 'backend': str, 'error': str}
    """
    return get_screen().capture(filename, include_mouse=include_mouse)
@mcp.tool()
def compare_images(img1_path: str, img2_path: str) -> dict:
    """Compare two images using a VLM. Requires a configured VLM provider."""
    if not vlm_configured():
        return {"success": False, "error": NO_VLM_ERROR}
    return get_screen().compare(img1_path, img2_path)
@mcp.tool()
def analyze_screenshot(image_path: str, prompt: str) -> str:
    """Analyze a screenshot with a VLM. Requires a configured VLM provider."""
    if not vlm_configured():
        return NO_VLM_ERROR
    result = get_screen().analyze(image_path, prompt)
    return result.get("analysis", "") if result.get("success") else ""
def _handle_type_action(text: str) -> dict:
    """Handle typing text using KeyboardController."""
    try:
        success = get_keyboard().type_text(text)
        return {"success": success, "error": "" if success else "Type action failed"}
    except (BackendUnavailable, RuntimeError, ValueError) as e:
        logging.error("Type action failed: %s", e)
        return _input_error(e)
def _handle_press_action(key: str) -> dict:
    """Handle key press using KeyboardController."""
    try:
        success = get_keyboard().press_key(key)
        return {"success": success, "error": "" if success else "Press action failed"}
    except (BackendUnavailable, RuntimeError, ValueError) as e:
        logging.error("Press action failed: %s", e)
        return _input_error(e)
def _handle_scroll_action(action: str) -> dict:
    """Handle scroll action.
    Args:
        action: Should be "scroll:amount" where amount is an integer
        Note:
          - Each unit = 1 scroll notch (120 = high-def scroll)
          - Typical values: 15-120 for normal scrolling
    """
    if len(action) <= 7 or not action.startswith("scroll:"):
        return {"success": False, "error": "Bad scroll format"}
    try:
        amount_str = action[7:]
        if not amount_str:
            return {"success": False, "error": "Missing scroll amount"}
        amount = int(amount_str)
        get_mouse().scroll(amount)
        return {"success": True}
    except ValueError:
        return {"success": False, "error": "Scroll amount must be a number"}
    except (BackendUnavailable, RuntimeError) as e:
        logging.error("Scroll action failed: %s", e)
        return _input_error(e)
def _handle_click_action() -> dict:
    """Handle click action at current mouse position."""
    try:
        get_mouse().click()
        return {"success": True}
    except (BackendUnavailable, RuntimeError, ValueError) as e:
        logging.error("Click action failed: %s", e)
        return _input_error(e)
def _handle_move_to_action(coords_str) -> dict:
    """Handle move to coordinates (absolute or relative).
    Args:
        coords_str: The coordinates string in format:
          - "x,y" for absolute movement (e.g. "500,500")
          - "rel:x,y" for relative movement (e.g. "rel:10,-5")
    """
    try:
        relative = coords_str.startswith("rel:")
        if relative:
            coords_str = coords_str[4:]
        coords = _parse_coordinates(coords_str)
        if not coords:
            return {"success": False, "error": "Invalid coordinates"}
        if relative:
            get_mouse().move_to(*coords)
        else:
            get_mouse().move_to_absolute(*coords)
        return {"success": True}
    except (BackendUnavailable, RuntimeError, ValueError) as e:
        logging.error("Move to action failed: %s", e)
        return _input_error(e)
def _handle_drag_action(action: str) -> dict:
    """Handle drag action between coordinates."""
    parts = action[5:].split(":")
    if len(parts) != 2:
        return {"success": False, "error": "Invalid drag format"}
    start = _parse_coordinates(parts[0])
    end = _parse_coordinates(parts[1])
    if not start or not end:
        return {"success": False, "error": "Invalid coordinates"}
    try:
        get_mouse().drag(*start, *end)
        return {"success": True}
    except (BackendUnavailable, RuntimeError, ValueError) as e:
        logging.error("Drag action failed: %s", e)
        return _input_error(e)
def _parse_coordinates(coords_str: str) -> Optional[Tuple[int, int]]:
    """Parse x,y coordinates from string."""
    try:
        x, y = map(int, coords_str.split(","))
        if x < 0 or y < 0:
            raise ValueError("Coordinates must be positive")
        return (x, y)
    except ValueError as e:
        logging.error("Invalid coordinates: %s", e)
        return None
# Register action handlers with proper parameter passing
def make_handler(prefix: str, handler: callable) -> callable:
    """Create an action handler that strips the prefix.
    Args:
        prefix: The action prefix to strip
        handler: The handler function to call
    Returns:
        A function that processes the action after the prefix
    """
    return lambda action: handler(action[len(prefix):])
register_handler("type:", lambda action: _handle_type_action(action[5:]))
register_handler("press:", make_handler("press:", _handle_press_action))
register_handler("click", lambda _: _handle_click_action())
register_handler("click:", lambda _: _handle_click_action())
register_handler("move_to:", lambda action: _handle_move_to_action(coords_str=action[8:]))
register_handler("drag:", make_handler("drag:", _handle_drag_action))
register_handler("scroll:", _handle_scroll_action)
@mcp.tool()
def execute_action(action: str) -> dict:
    """Execute system actions with chaining support.
    Handles both single actions and chained sequences.
    Args:
        action: Action string in format:
          Single: "prefix:params" (e.g. "click:100,200")
          Chain: "chain:action1;action2" (e.g. "chain:click:100,200;type:hello")
    Supported Actions:
      type:text - Type text
      press:key - Press key
      click/click: - Click at current position (both formats supported)
      move_to:x,y - Move to absolute coordinates (default)
      move_to:rel:x,y - Move relative to current position
      drag:x1,y1:x2,y2 - Drag between points
      scroll:amount - Vertical scroll (positive=up, negative=down)
        Note: Each unit = 1 scroll notch (120 = high-def scroll). Typical: 15-120.
      scroll:horizontal:amount - Horizontal scroll
        Note: Each unit = 1 scroll notch (120 = high-def scroll). Typical: 15-120.
    Returns:
        dict: {'success': bool, 'error': str}

        Declared as a dict because that is what every code path returns. It was
        annotated -> bool while returning dicts, and a strict MCP client rejects the
        structured content against the declared schema, so the tool was unusable
        from a conforming client.
    Example:
        execute_action("click:100,200")
        execute_action("chain:click:100,200;type:hello;press:Enter")
    """
    if not action or not isinstance(action, str):
        logging.error("Invalid action")
        return {"success": False, "error": "Invalid action"}

    # Each entry receives the part of the action after its prefix. Upstream called
    # every handler with no argument at all -- handler() against
    # _handle_type_action(text) -- so every single action except a bare "click"
    # raised TypeError, which none of the except clauses caught. Only chained
    # actions worked, because ChainProcessor dispatches separately.
    handlers = (
        ("chain:", lambda payload: ChainProcessor(payload).execute()),
        ("type:", _handle_type_action),
        ("press:", _handle_press_action),
        ("move_to:", _handle_move_to_action),
        ("drag:", lambda payload: _handle_drag_action("drag:" + payload)),
        ("scroll:", lambda payload: _handle_scroll_action("scroll:" + payload)),
        ("click", lambda _payload: _handle_click_action()),
    )
    for prefix, handler in handlers:
        if not action.startswith(prefix):
            continue
        try:
            result = handler(action[len(prefix):])
            if isinstance(result, bool):  # Backward compatibility
                return {"success": result, "error": "" if result else "Action failed"}
            return result
        except (BackendUnavailable, RuntimeError, ValueError, IOError) as e:
            logging.error("Action failed: %s", e)
            return {"success": False, "error": str(e)}
    logging.error("Unknown action format: %s", action)
    return {"success": False, "error": "Unknown action format"}
@mcp.tool()
def capture_and_analyze(prompt: str) -> dict:
    """Capture then analyze the screen. Requires a configured VLM provider."""
    if not vlm_configured():
        return {"success": False, "error": NO_VLM_ERROR}
    return get_screen().capture_and_analyze(prompt)
@mcp.tool()
def describe_environment() -> dict:
    """Report which backends this machine offers, and which were selected.

    Call this first when a capture or an input action fails: it says what is
    installed, what the compositor advertises, and what that adds up to.
    """
    from wayland_mcp.backends.base import Capabilities  # pylint: disable=import-outside-toplevel
    from wayland_mcp.backends.detect import (  # pylint: disable=import-outside-toplevel
        select_capture_backend,
        select_keyboard_backend,
        select_pointer_backend,
    )

    caps = Capabilities.detect()
    selected = {}
    for label, selector in (
        ("capture", select_capture_backend),
        ("keyboard", select_keyboard_backend),
        ("pointer", select_pointer_backend),
    ):
        try:
            selected[label] = selector(caps).name
        except BackendUnavailable as err:
            selected[label] = f"unavailable: {err}"
    return {
        "success": True,
        "selected": selected,
        "binaries": sorted(caps.binaries),
        "portal_interfaces": sorted(
            iface for iface in caps.dbus_interfaces
            if iface.rsplit(".", 1)[-1] in ("Screenshot", "RemoteDesktop", "ScreenCast")
        ),
        "wayland_display": caps.wayland_display,
        "vlm_configured": vlm_configured(),
        "unprivileged": not caps.writable_input_device,
    }


# Server entry points
if __name__ == "__main__":
    try:
        mcp.run()
        logging.info("MCP server running on port %d", PORT)
    except (RuntimeError, IOError) as e:
        logging.error("Server failed: %s", e)
def main():
    """Script entry point."""
    try:
        mcp.run()
        logging.info("MCP server running on port %d", PORT)
    except RuntimeError as e:
        logging.error("Server failed: %s", e)
