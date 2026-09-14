# Contributing to Wayland MCP Server

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. Fork and clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/wayland-mcp.git
cd wayland-mcp
```

2. Create a virtual environment

Use `--system-site-packages` so the virtualenv can see a system PyGObject, which
is what the XDG portal backends need:

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
```

3. Install in development mode
```bash
pip install -e ".[dev]"
```

4. Input control setup

There is none, and none is needed: input goes through the
`org.freedesktop.portal.RemoteDesktop` portal, which synthesises events with no
privilege. Your compositor asks for permission the first time.

If you are coming from an older checkout and ran `sudo ./setup.sh`, undo it — see
`scripts/legacy-evemu-setup.sh` for the exact commands. That script made every
`/dev/input/event*` device world-writable via a persistent udev rule, which lets
any local process read your keystrokes.

## Testing

Before submitting a PR:

1. Run the test suite. It is headless by design — no compositor, no D-Bus, no
   `/dev/input` — so it runs anywhere, CI included:

```bash
pytest
```

2. Verify input against a real window. This reads back what the widgets actually
   received rather than inferring success from the absence of an exception:

```bash
python scripts/verify_input.py   # do not touch the machine while it runs
```

3. Manual testing with an MCP client (Claude Code, Claude Desktop, Cline, ...).
4. Say which compositor you verified on, and which you did not.

### Adding a backend

Backends are selected by *capability*, never by compositor name. A new one needs:

- a `supports(caps)` that tests only what it truly requires — a binary and its
  version, a D-Bus interface, a Wayland global — and a `requires` string, which is
  what the user sees when nothing works;
- a priority that puts unprivileged paths above privileged ones;
- a row in `tests/test_backend_selection.py`. Then check the test can fail: mutate
  the guard you just added and confirm it goes red. A test that passes against
  broken code proves nothing, and two of the existing ones had to be rewritten for
  exactly that reason.

Nothing in this project may change `/dev/input` or `/dev/uinput` permissions. It
may only observe them.

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
