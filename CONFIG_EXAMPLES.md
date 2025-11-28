# Wayland MCP Configuration Examples

## Claude Desktop

Location: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "wayland": {
      "command": "uvx",
      "args": ["wayland-mcp"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-your-key-here",
        "VLM_MODEL": "qwen/qwen2.5-vl-72b-instruct:free",
        "XDG_RUNTIME_DIR": "/run/user/1000",
        "WAYLAND_DISPLAY": "wayland-0",
        "XDG_SESSION_TYPE": "wayland"
      }
    }
  }
}
```

## Cline (VS Code)

Location: `.roo/mcp.json` in your workspace

```json
{
  "mcpServers": {
    "wayland": {
      "command": "uvx",
      "args": ["wayland-mcp"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-your-key-here",
        "VLM_MODEL": "qwen/qwen2.5-vl-72b-instruct:free",
        "XDG_RUNTIME_DIR": "/run/user/1000",
        "WAYLAND_MCP_PORT": "4999",
        "WAYLAND_DISPLAY": "wayland-0"
      }
    }
  }
}
```

## Cursor

Location: `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project)

```json
{
  "mcpServers": {
    "wayland": {
      "command": "uvx",
      "args": ["wayland-mcp"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-your-key-here",
        "XDG_RUNTIME_DIR": "/run/user/1000",
        "WAYLAND_DISPLAY": "wayland-0"
      }
    }
  }
}
```

## Environment Variable Notes

### Finding Your Values

**XDG_RUNTIME_DIR**: Usually `/run/user/$(id -u)`
```bash
echo $XDG_RUNTIME_DIR
```

**WAYLAND_DISPLAY**: Check with
```bash
echo $WAYLAND_DISPLAY
# Common values: wayland-0, wayland-1
```

### OpenRouter API Key

Get your key from [openrouter.ai](https://openrouter.ai):
1. Sign up/login
2. Go to Keys section
3. Create new key
4. Copy key starting with `sk-or-v1-`

### Alternative VLM Models

You can use any vision model from OpenRouter:

```json
"VLM_MODEL": "anthropic/claude-3.5-sonnet"
"VLM_MODEL": "google/gemini-pro-vision"
"VLM_MODEL": "openai/gpt-4-vision-preview"
```

Check [openrouter.ai/models](https://openrouter.ai/models) for options.
