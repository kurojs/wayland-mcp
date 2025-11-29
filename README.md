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
- Wayland compositor (GNOME, KDE Plasma, Hyprland, Sway, etc.)
- `grim` and `slurp` for screenshots (usually pre-installed)

### Quick Install

```bash
uvx wayland-mcp
```

### From Source

```bash
git clone https://github.com/kurojs/wayland-mcp.git
cd wayland-mcp
pip install -e .
```

### Input Control Setup

For mouse and keyboard automation, run the setup script:

```bash
sudo ./setup.sh
```

**What it does:**
- Installs `evemu-tools` package
- Configures setuid for `evemu-event`
- Adds user to `input` group
- Creates udev rules for device access

After setup, log out and back in for group changes to take effect.

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

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| **VLM Provider Options** | | | |
| `VLM_PROVIDER` | Vision provider: `openrouter` or `gemini` | `openrouter` | No |
| `OPENROUTER_API_KEY` | OpenRouter API key | - | For OpenRouter |
| `GEMINI_API_KEY` | Google Gemini API key | - | For Gemini |
| `VLM_MODEL` | Model identifier | `qwen/qwen2.5-vl-72b-instruct:free` (OpenRouter) or `gemini-2.5-flash` (Gemini) | No |
| **Wayland Environment** | | | |
| `XDG_RUNTIME_DIR` | Wayland runtime directory | `/run/user/1000` | Yes |
| `WAYLAND_DISPLAY` | Display identifier | `wayland-0` | Yes |
| **Optional** | | | |
| `WAYLAND_MCP_PORT` | Server listen port | `4999` | No |

**Getting API Keys:**
- OpenRouter: [openrouter.ai](https://openrouter.ai) → Keys section
- Google Gemini: [Google AI Studio](https://aistudio.google.com/app/apikey)

### Desktop Environment Compatibility

| Desktop | Status | Notes |
|---------|--------|-------|
| GNOME | ✅ Tested | Wayland by default on modern versions |
| KDE Plasma | ✅ Tested | Enable Wayland session at login |
| Hyprland | ✅ Tested | Native Wayland compositor |
| Sway | ✅ Should work | i3-compatible Wayland compositor |
| Others | ⚠️ Untested | Any wlroots-based compositor should work |

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

The setup script requires sudo access to:
- Install system packages (`evemu-tools`)
- Modify file permissions
- Configure udev rules

After setup, the server runs with your user privileges but can control input devices through configured permissions.

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
    │ • VLM    │      │ • evemu  │  │  │ • grim       │ │
    │ • Compare│      │ • Mouse  │  │  │ • slurp      │ │
    │          │      │ • Keyboard│  │  │ • PIL        │ │
    └──────────┘      └──────────┘  │  └──────────────┘ │
                                    │                    │
                                    └────────────────────┘
                                      Wayland Compositor
```

## Troubleshooting

**Input control not working**
- Ensure you ran `sudo ./setup.sh`
- Log out and back in after setup
- Verify you're in the `input` group: `groups | grep input`

**Screenshots failing**
- Check if `grim` is installed: `which grim`
- Verify `WAYLAND_DISPLAY` matches your session: `echo $WAYLAND_DISPLAY`

**VLM analysis not working**
- Confirm `OPENROUTER_API_KEY` is set correctly
- Check API key permissions on OpenRouter dashboard
- Test model availability: some models have usage limits

**Server won't start**
- Check Python version: `python3 --version` (needs 3.8+)
- Verify all dependencies: `pip install -e .`
- Look for port conflicts if using custom `WAYLAND_MCP_PORT`

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
│   └── ...
├── README.md             # This file
├── CONFIG_EXAMPLES.md    # Configuration examples
├── CONTRIBUTING.md       # Contribution guidelines
├── setup.sh              # Permission setup script
└── pyproject.toml        # Package metadata
```

## License

GPL-3.0 License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io)
- Uses [FastMCP](https://github.com/jlowin/fastmcp) for server implementation
- Inspired by the need for reliable Wayland automation tools

---

<div align="center">
Made for the Wayland desktop environment
</div>
