# Contributing to Wayland MCP Server

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. Fork and clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/wayland-mcp.git
cd wayland-mcp
```

2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
```

3. Install in development mode
```bash
pip install -e .
```

4. Run setup script (for input control features)
```bash
sudo ./setup.sh
```

## Testing

Before submitting a PR, please test your changes:

1. Manual testing with an MCP client (Claude Desktop, Cline, etc.)
2. Test all affected tools/functions
3. Verify on your Wayland compositor

## Code Style

- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Add docstrings to new functions
- Keep functions focused and modular

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Update README.md if needed
4. Test thoroughly
5. Submit PR with description of changes

## Reporting Issues

When reporting bugs, please include:
- Your desktop environment (GNOME, KDE, Hyprland, etc.)
- Wayland compositor version
- Python version
- Error messages or logs
- Steps to reproduce

## Feature Requests

Feature requests are welcome! Please:
- Check existing issues first
- Clearly describe the use case
- Explain why it would be useful

## Questions?

Feel free to open an issue for any questions about contributing.
