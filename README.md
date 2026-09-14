# Wayland MCP Server

<div align="center">

[![License: GPL3](https://img.shields.io/badge/license-GPL3-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Wayland-lightgrey.svg)

**Model Context Protocol server for Wayland desktop automation**

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [API](#available-tools) • [Security](#security)

---

</div>

## Overview

Wayland MCP Server enables AI assistants to interact with your Wayland desktop through the Model Context Protocol. It provides screenshot capture with VLM analysis, mouse control, keyboard input, and action chaining capabilities.

### Why This Project?

Existing Wayland screenshot and automation tools often have reliability issues. This project provides a robust, MCP-native solution specifically designed for AI-driven desktop automation on modern Linux systems.

### Quick Example

```bash
# AI Assistant: "Take a screenshot and tell me what's on screen"
→ Captures screen, analyzes with VLM, responds with description

# AI Assistant: "Click the OK button"  
→ Identifies button location from screenshot, moves mouse, clicks

# AI Assistant: "Fill out this form with test data"
→ Chains clicks and keyboard input to complete form automatically
```

## Features

**Visual Analysis**
- Screenshot capture with precision ruler overlays
- VLM-powered image analysis via **OpenRouter** or **Google Gemini**
- Multiple vision model support (Claude, GPT-4V, Gemini, Qwen)
- Side-by-side image comparison and diff detection

**Mouse Automation**
- Absolute and relative cursor positioning
- Click operations (left, right, middle button)
- Drag and drop with coordinate precision
- Bidirectional scrolling (vertical/horizontal)

**Keyboard Control**
- Text input simulation
- Individual key press events
- Complex key combinations

**Action Sequences**
- Chain multiple operations together
- Flexible syntax: `chain:action1;action2;action3`
- Example: `chain:click:100,200;type:hello;press:Enter`

## Installation

### Prerequisites

- Python 3.8 or higher
- A Wayland session (GNOME, KDE Plasma, COSMIC, Hyprland, Sway, ...)
- **No privileged setup, and no root.** See [Backends](#backends) for what each
  path needs; the server tells you itself with the `describe_environment` tool.

Recommended, though optional: PyGObject, which unlocks the XDG portal backends and
is the only path that works on every desktop.

```bash
sudo apt install python3-gi        # Debian, Ubuntu, Pop!_OS
sudo dnf install python3-gobject   # Fedora
sudo pacman -S python-gobject      # Arch
```

### Quick Install

```bash
uvx wayland-mcp
```

To let `uvx` see a system PyGObject, add `--system-site-packages`:

```bash
uv venv --system-site-packages && uv pip install wayland-mcp
```

### From Source

```bash
git clone https://github.com/Sycatle/wayland-mcp.git
cd wayland-mcp
uv venv --system-site-packages
uv pip install -e ".[dev]"
```

### Input Control Setup

There is none. Input goes through the `org.freedesktop.portal.RemoteDesktop`
portal, which synthesises pointer and keyboard events with no privilege at all.
Your compositor asks for permission the first time; the returned restore token is
kept in `$XDG_STATE_HOME/wayland-mcp/remote-desktop-token` (mode 0600) and
replayed afterwards, so you are not asked again. Set `WAYLAND_MCP_NO_PERSIST=1`
to be prompted every time instead.

> **If you ran the upstream `sudo ./setup.sh`, undo it.** That script made every
> `/dev/input/event*` device world-writable and installed a udev rule
> (`KERNEL=="event*", MODE="0666"`) to keep them that way across reboots, plus a
> setuid bit and a NOPASSWD sudoers entry for `evemu-event`. While that rule is in
> place, *any* local process can read your keystrokes, passwords included.
> `scripts/legacy-evemu-setup.sh` documents the exact rollback commands. This fork
> removed the script from the install path and needs none of it.

## Usage

### MCP Configuration

The server supports two VLM providers:

**Option 1: OpenRouter** (multiple models via proxy)
```json
{
  "mcpServers": {
    "wayland": {
      "command": "uvx",
      "args": ["wayland-mcp"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-...",
        "VLM_PROVIDER": "openrouter",
        "VLM_MODEL": "qwen/qwen2.5-vl-72b-instruct:free",
        "XDG_RUNTIME_DIR": "/run/user/1000",
        "WAYLAND_DISPLAY": "wayland-0"
      }
    }
  }
}
```

**Option 2: Google Gemini Direct** (native API, faster)
```json
{
  "mcpServers": {
    "wayland": {
      "command": "uvx",
      "args": ["wayland-mcp"],
      "env": {
        "GEMINI_API_KEY": "AIza...",
        "VLM_PROVIDER": "gemini",
        "VLM_MODEL": "gemini-2.5-flash",
        "XDG_RUNTIME_DIR": "/run/user/1000",
        "WAYLAND_DISPLAY": "wayland-0"
      }
    }
  }
}
```

**Example for Claude Desktop** (`~/.config/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "wayland": {
      "command": "uvx",
      "args": ["wayland-mcp"],
      "env": {
        "GEMINI_API_KEY": "AIza...",
        "VLM_PROVIDER": "gemini",
        "VLM_MODEL": "gemini-2.5-flash",
        "XDG_RUNTIME_DIR": "/run/user/1000",
        "WAYLAND_DISPLAY": "wayland-0"
      }
    }
  }
}
```

> **Note:** See [CONFIG_EXAMPLES.md](CONFIG_EXAMPLES.md) for more configuration examples including Cursor, OpenRouter models, and VLM provider options.

### Environment Variables

Everything below is optional. The server starts, captures the screen and controls
input with none of it set.

| Variable | Description | Default |
|----------|-------------|---------|
| **Vision analysis (optional feature)** | | |
| `VLM_PROVIDER` | `openrouter`, `gemini` or `azure` | `openrouter` |
| `OPENROUTER_API_KEY` | OpenRouter key | - |
| `GEMINI_API_KEY` | Google Gemini key | - |
| `AZURE_API_KEY`, `AZURE_ENDPOINT`, `AZURE_DEPLOYMENT` | Azure AI Foundry | - |
| `VLM_MODEL` | Model identifier | provider default |
| `WAYLAND_MCP_CONFIG` | JSON file to read a key from, if you keep it out of the environment | - |
| **Backend selection** | | |
| `WAYLAND_MCP_CAPTURE_BACKEND` | Force a capture backend by name | auto |
| `WAYLAND_MCP_INPUT_BACKEND` | Force an input backend by name | auto |
| `WAYLAND_MCP_NO_PERSIST` | `1` to be asked for portal permission every time | unset |
| `WAYLAND_MCP_RESTORE_TOKEN_PATH` | Where to keep the portal restore token | `$XDG_STATE_HOME/wayland-mcp/remote-desktop-token` |
| **Behaviour** | | |
| `WAYLAND_MCP_QUIET_CAPTURE` | `1` to silence animations and sound around a capture, restoring your settings afterwards | unset |
| `WAYLAND_MCP_LOG` | Log file path | `/tmp/wayland-mcp.log` |
| **Session** | | |
| `XDG_RUNTIME_DIR`, `WAYLAND_DISPLAY`, `DBUS_SESSION_BUS_ADDRESS` | Recovered automatically when your MCP client strips them; set them explicitly if you run several compositors | auto |

**Getting API keys:**
- OpenRouter: [openrouter.ai](https://openrouter.ai) → Keys section
- Google Gemini: [Google AI Studio](https://aistudio.google.com/app/apikey)

> **MCP clients strip the environment.** The reference stdio transport passes only
> `HOME`, `LOGNAME`, `PATH`, `SHELL`, `TERM` and `USER` to the server it launches,
> which removes exactly what a Wayland tool needs. The server reconstructs
> `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS` and `WAYLAND_DISPLAY` from the
> filesystem when they are missing, so no client-side configuration is required. It
> declines to guess only when several compositor sockets are present; set
> `WAYLAND_DISPLAY` in your client config then.

### Backends

Backends are chosen by *capability*, never by compositor name: the server probes
which binaries exist and at what version, which portal interfaces are on the
session bus, and which globals the compositor advertises, then picks the highest
priority backend whose requirements are actually met. Call `describe_environment`
to see what it decided and why.

**Capture**, highest priority first:

| Backend | Needs | Notes |
|---------|-------|-------|
| `cosmic-screenshot` | the binary, shipped with COSMIC | silent, no dialog; full screen only |
| `grim` | `grim`, plus `zwlr_screencopy_manager_v1`, **or** `ext_image_copy_capture_manager_v1` with grim >= 1.5 | region capture via `slurp` |
| `ksnip`, `gnome-screenshot`, `spectacle` | the respective binary | the upstream cascade, preserved |
| `portal` | `org.freedesktop.portal.Screenshot` + PyGObject | works everywhere; may prompt |

**Input**, highest priority first:

| Backend | Needs | Pointer | Keyboard |
|---------|-------|---------|----------|
| `portal` | `org.freedesktop.portal.RemoteDesktop` + PyGObject | yes, absolute | yes, layout-independent |
| `wtype` | `wtype` + `zwp_virtual_keyboard_manager_v1` | no | yes |
| `ydotool` | `ydotool` + writable `/dev/uinput` | yes | yes, US layout only |
| `evemu` | `evemu-event` + an **already** writable `/dev/input/event*` | approximate | yes, US layout only |

`evemu` is last on purpose and is never a requirement. Nothing in this project
changes `/dev/input` permissions.

### Desktop Environment Compatibility

| Desktop | Capture | Input | Notes |
|---------|---------|-------|-------|
| COSMIC (Pop!_OS 24.04) | ✅ `cosmic-screenshot` | ✅ `portal` | Verified end to end on `cosmic-comp 0.1`. Only implements `ext-image-copy-capture`, so a `grim` older than 1.5 cannot capture here — which is what motivated this fork. |
| GNOME | ✅ `gnome-screenshot` or `portal` | ✅ `portal` | No `zwp_virtual_keyboard`, so `wtype` is unavailable; the portal covers it. |
| KDE Plasma | ✅ `spectacle` or `portal` | ✅ `portal` | |
| Hyprland, Sway, wlroots | ✅ `grim` | ⚠️ `wtype` keyboard; pointer needs `ydotool` | `xdg-desktop-portal-wlr` provides ScreenCast and Screenshot but not RemoteDesktop, so there is no portal pointer path. |
| Others | ⚠️ falls back to `portal` | ⚠️ depends | `describe_environment` will tell you. |

Only the COSMIC row was verified on hardware for this fork; the others follow from
each backend's stated requirements and the unit tests that pin the selection, not
from a live run.

### Known limitations

- **Region capture** needs `grim` + `slurp`, or a portal that offers an interactive
  picker. `cosmic-screenshot` cannot select a region without a human, so it reports
  that instead of blocking an MCP call.
- **Keyboard layout**: the portal backend types by keysym and is layout
  independent. `ydotool` and `evemu` type by *position*, so on a non-US layout they
  produce whatever those positions mean there — asking for `ASAP 42` on AZERTY
  gives `QSQP 'é`.
- **cosmic-comp discards the first synthesized event** after a session starts. The
  portal backend absorbs that with a zero-distance warm-up motion; without it, the
  first click or keystroke of every session is silently lost.
- **Absolute pointer positioning through the portal** needs a ScreenCast stream
  attached to the session. Where the portal refuses one, absolute moves raise an
  explanatory error instead of silently misplacing the cursor; use a relative
  move, or another input backend.

### Example Commands

Through an MCP client, you can request actions like:

- *"Take a screenshot and analyze what's on the screen"*
- *"Move the mouse to coordinates (100, 200) and click"*
- *"Type 'hello world' and press Enter"*
- *"Click at (50, 50), then drag to (200, 200)"*

## Available Tools

The server exposes the following MCP tools:

### Screen Capture
- `capture_screenshot` - Take a screenshot with optional ruler overlays
- `capture_and_analyze` - Capture and analyze using VLM in one step

### Vision Analysis  
- `analyze_screenshot` - Analyze an existing screenshot with custom prompt
- `compare_images` - Compare two screenshots to detect differences

### Mouse Control
- `move_mouse` - Move cursor to coordinates (absolute or relative)
- `click_mouse` - Perform left click at current position
- `drag_mouse` - Drag between two coordinate points
- `scroll_mouse` - Vertical scroll (positive=up, negative=down)

### Action Execution
- `execute_action` - Execute single action or chain multiple actions

#### Action Chain Syntax

Combine multiple actions with semicolons:

```
chain:action1;action2;action3
```

**Supported Actions:**
- `type:text` - Type a text string
- `press:key` - Press a specific key
- `click:` or `click:x,y` - Click at position or current location
- `move_to:x,y` - Move to absolute coordinates
- `move_to:rel:x,y` - Move relative to current position
- `drag:x1,y1:x2,y2` - Drag from point to point
- `scroll:amount` - Scroll vertically (typical values: 15-120)
- `scroll:horizontal:amount` - Scroll horizontally

**Example Chains:**
```
chain:move_to:100,200;click:;type:hello;press:Enter
chain:click:50,50;drag:50,50:200,200
chain:scroll:120;move_to:rel:0,-50;click:
```

## Security

**⚠️ IMPORTANT SECURITY CONSIDERATIONS**

This server grants extensive control over your desktop environment:

- Full mouse and keyboard control
- Screen capture capabilities
- Ability to execute arbitrary input sequences

### Best Practices

- Only use with trusted AI models and MCP clients
- Review action chains before execution in sensitive contexts
- Consider running in a sandboxed or test environment
- Be aware that the AI can perform any action you could perform manually

### Permission Model

No setuid binaries, no sudoers entries, no udev rules, no `input` group
membership. The nominal path is the XDG portal: your compositor asks you once,
mediates every event, and can revoke the grant at any time. The stored restore
token is a capability — treat it like a credential; delete
`$XDG_STATE_HOME/wayland-mcp/remote-desktop-token` to revoke it locally, and
revoke the permission in your desktop settings to invalidate it entirely.

The fallback backends need more, and get chosen only when nothing better exists:
`ydotool` wants a writable `/dev/uinput`, `evemu` a writable `/dev/input/event*`.
The server checks whether that access already exists. It never asks for it, and it
never widens it.

## Architecture

```
                    ┌─────────────────────────────────┐
                    │      MCP Client Layer           │
                    │   (Claude, Cursor, VS Code)     │
                    └───────────────┬─────────────────┘
                                    │
                            MCP Protocol (stdio/HTTP)
                                    │
                    ┌───────────────▼─────────────────┐
                    │    Wayland MCP Server           │
                    │    ┌─────────────────────┐      │
                    │    │  Core Components    │      │
                    │    ├─────────────────────┤      │
                    │    │ • FastMCP Handler   │      │
                    │    │ • Action Processor  │      │
                    │    │ • Chain Parser      │      │
                    │    └─────────────────────┘      │
                    └────┬────────────────┬────────────┘
                         │                │
         ┌───────────────┴────┐      ┌────┴──────────────┐
         │                    │      │                   │
    ┌────▼─────┐      ┌──────▼───┐  │  ┌──────────────┐ │
    │  Vision  │      │  Input   │  │  │   Screen     │ │
    │          │      │ Control  │  │  │   Capture    │ │
    ├──────────┤      ├──────────┤  │  ├──────────────┤ │
    │ • VLM    │      │ • portal │  │  │ • cosmic     │ │
    │ • Compare│      │ • wtype  │  │  │ • grim/slurp │ │
    │          │      │ • ydotool│  │  │ • portal     │ │
    └──────────┘      └──────────┘  │  └──────────────┘ │
                                    │                    │
                                    └────────────────────┘
                                      Wayland Compositor
```

## Troubleshooting

**Start here, whatever the symptom.** Call the `describe_environment` tool: it
reports which binaries were found, which portal interfaces are on the bus, which
backend was selected for capture, keyboard and pointer, and — when one is
unavailable — exactly what each candidate would have needed.

**Everything reports as unavailable when launched from an MCP client**
- Almost always the stripped environment. The server recovers
  `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS` and `WAYLAND_DISPLAY` on its own,
  but it refuses to guess between several compositor sockets — set
  `WAYLAND_DISPLAY` in the `env` block of your client config.
- Check the log (`/tmp/wayland-mcp.log`) for the line listing what it recovered.

**Input control not working**
- No `sudo` step exists any more; if you are looking for `setup.sh`, read the
  warning under [Input Control Setup](#input-control-setup).
- If a permission dialog never appears and nothing happens, your desktop may have
  no `RemoteDesktop` portal (wlroots compositors do not ship one). Install `wtype`
  for keyboard, `ydotool` for pointer.
- If the permission was denied once, the stored token is stale: delete
  `$XDG_STATE_HOME/wayland-mcp/remote-desktop-token` and try again.
- Verify against a real window rather than guessing:
  `python scripts/verify_input.py` clicks, types and scrolls, then reads back what
  the widgets actually received. Do not touch the machine while it runs.

**Screenshots failing**
- On COSMIC, a `grim` older than 1.5 cannot work: the compositor implements only
  `ext-image-copy-capture`. Selection already accounts for this; if you forced
  `WAYLAND_MCP_CAPTURE_BACKEND=grim`, unset it.
- Install a portal (`xdg-desktop-portal` plus the backend for your desktop) and
  PyGObject for the universal fallback.

**Typing produces the wrong characters**
- You are on a non-US layout with a keycode-based backend (`ydotool`, `evemu`),
  which types positions rather than characters. The `portal` backend types by
  keysym and is layout independent.

**VLM analysis not working**
- Vision is optional: capture and input do not need it. The analysis tools say
  precisely which variable to set when no provider is configured.
- Confirm the key for the provider you selected with `VLM_PROVIDER`.

**Server won't start**
- Check Python: `python3 --version` (needs 3.8+).
- Reinstall: `uv pip install -e ".[dev]"`, then `pytest` — the test suite runs
  headless and does not need a graphical session.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Project Structure

```
wayland-mcp/
├── wayland_mcp/          # Main package
│   ├── server_mcp.py     # MCP server implementation
│   ├── screen_utils.py   # Screenshot & VLM analysis
│   ├── mouse_utils.py    # Mouse control functions
│   ├── keyboard_utils.py # Keyboard input handling
│   ├── chain_processor.py# Action chain parser
│   ├── session_env.py    # Recovers the session vars MCP clients strip
│   └── backends/         # Capability-selected capture and input backends
│       ├── base.py       # Capabilities probe + backend interfaces
│       ├── detect.py     # Selection by priority and requirements
│       ├── portal.py     # Shared GDBus plumbing for XDG portals
│       ├── capture_*.py  # cosmic-screenshot, grim, legacy tools, portal
│       └── input_*.py    # portal RemoteDesktop, wtype, ydotool, evemu
├── tests/                # Headless tests: selection, keycodes, session env
├── scripts/
│   ├── verify_input.py   # End-to-end input check against a real window
│   └── legacy-evemu-setup.sh  # Documents how to undo the upstream setup.sh
├── docs/REPRO.md         # The upstream failure this fork started from
├── README.md             # This file
├── CONFIG_EXAMPLES.md    # Configuration examples
├── CONTRIBUTING.md       # Contribution guidelines
└── pyproject.toml        # Package metadata
```

## License

GPL-3.0. See [LICENSE](LICENSE) for the full text.

Copyright (C) 2024 wayland-mcp contributors, and contributors to this fork. This
is a fork of [kurojs/wayland-mcp](https://github.com/kurojs/wayland-mcp), adding
capability-based backend selection so it works on compositors the original could
not reach — COSMIC in particular — and removing the privileged input setup.

## Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io)
- Uses [FastMCP](https://github.com/jlowin/fastmcp) for server implementation
- Inspired by the need for reliable Wayland automation tools

---

<div align="center">
Made for the Wayland desktop environment
</div>
