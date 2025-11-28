# 🤖 Gemini API Integration

This fork adds support for Google Gemini API as an alternative to OpenRouter for VLM (Vision-Language Model) analysis.

## ✨ New Features

### Multi-Provider Support
- **Google Gemini API**: Direct integration with Google's Gemini models
- **OpenRouter**: Original OpenRouter support maintained
- **Lazy Initialization**: Proper environment variable loading

### Configuration

The VLM provider can be selected via environment variables:

```json
{
  "mcpServers": {
    "wayland-mcp": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "wayland_mcp.server_mcp"],
      "env": {
        "XDG_RUNTIME_DIR": "/run/user/1000",
        "WAYLAND_MCP_PORT": "4999",
        "DISPLAY": ":0",
        "WAYLAND_DISPLAY": "wayland-0",
        "XDG_SESSION_TYPE": "wayland",
        
        // For Gemini (recommended)
        "GEMINI_API_KEY": "your-gemini-api-key-here",
        "VLM_PROVIDER": "gemini",
        "VLM_MODEL": "gemini-2.5-flash",
        
        // Or for OpenRouter
        // "OPENROUTER_API_KEY": "your-openrouter-key",
        // "VLM_PROVIDER": "openrouter",
        // "VLM_MODEL": "qwen/qwen2.5-vl-72b-instruct:free"
      }
    }
  }
}
```

## 🔑 Getting a Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key and add it to your configuration

## 📊 Recommended Models

### Gemini Models (Free Tier)
- **gemini-2.5-flash** (Recommended): Fast, efficient, excellent for screenshots
- **gemini-1.5-flash**: Alternative if quota exceeded
- **gemini-1.5-pro**: More capable but slower

### Rate Limits
- Free tier: 15 requests per minute
- 1 million tokens per minute

## 🔧 Technical Implementation

### Lazy Initialization
The VLM agent is initialized lazily (on first use) to ensure environment variables are properly loaded by the MCP server:

```python
def get_vlm_agent():
    """Lazy initialization of VLM agent with current environment variables."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
    provider = os.environ.get("VLM_PROVIDER", "openrouter")
    return VLMAgent(api_key, provider=provider)

screen = ScreenController(None)
screen.set_vlm_factory(get_vlm_agent)
```

### Provider Detection
The system automatically selects the appropriate API based on the `VLM_PROVIDER` environment variable:

```python
def analyze_screenshot(self, image_path: str, prompt: str) -> str:
    if self.provider == "gemini":
        return self._analyze_with_gemini(image_path, prompt)
    return self._analyze_with_openrouter(image_path, prompt)
```

## 🐛 Troubleshooting

### "No API key configured"
- Ensure `GEMINI_API_KEY` or `OPENROUTER_API_KEY` is set in your MCP config
- Check logs: `tail -f ~/.config/Claude/logs/mcp-server-wayland-mcp.log`
- Look for "VLM Configuration (lazy init)" in logs

### "Quota exceeded"
- Wait for rate limit reset (usually 1 minute)
- Switch to a different Gemini model
- Consider upgrading to a paid plan

### Still using OpenRouter
- Verify `VLM_PROVIDER` is set to `"gemini"`
- Restart Claude Desktop after config changes
- Check if using venv directly: `/path/to/venv/bin/python` instead of `uvx`

## 📝 Example Usage

```python
# Analyze a screenshot
analyze_screenshot(
    image_path="screenshot.png",
    prompt="Describe what you see in this screenshot in detail"
)

# Compare two images
compare_images(
    img1_path="before.png",
    img2_path="after.png"
)
```

## 🎯 Why Gemini?

1. **Free tier is generous**: 15 RPM with 1M tokens/minute
2. **Fast responses**: Optimized for quick analysis
3. **Good accuracy**: Excellent for screenshot analysis
4. **Easy setup**: No OAuth, just an API key
5. **No cookie issues**: Direct API access

## 📜 License

Same as original: GPL 3
