# Changelog


## [0.5.0] - 2026-09-13

### Fixed
- `pyproject.toml` was not valid TOML (`urls = {` spanned several lines), so any
  source install failed before reaching the build backend.
- The server raised at import: `MouseController()` and `KeyboardController()` were
  built at module level and scanned `/dev/input`, so a machine with default
  permissions could not start it. `wayland_mcp/__init__.py` imported
  `server_mcp`, so even `import wayland_mcp.app` failed.
- `execute_action` called every handler with no arguments, so all single actions
  except a bare `click` raised an uncaught `TypeError`.
- `grim -g "$(slurp)"` was passed to a shell-less subprocess as a literal string,
  so region capture never worked on any compositor.
- `type_text` lowercased its input, making capital letters impossible.
- Capture no longer rewrites the user's GNOME animation and event-sound settings,
  mutes the audio sink, or writes a sound-theme file at import time. That behaviour
  is opt-in via `WAYLAND_MCP_QUIET_CAPTURE=1` and now restores the values it found.
- The API key is no longer logged, and `~/.roo/mcp.json` is no longer read
  silently (opt-in via `WAYLAND_MCP_CONFIG`).
- An `import time` dropped during the refactor crashed every VLM analysis call
  with an uncaught `NameError`; the import is restored.
- The first 8 characters of the API key were still written to the log on every
  analysis; the log line is removed, so the promise above is now true.
- `## Usage## Usage` heading typo fixed, and the README's absolute-pointer
  limitation now matches the code: a refused ScreenCast stream raises an
  explanatory error instead of moving relatively.

### Added
- `wayland_mcp/backends/`: capture and input backends selected by probed
  capability rather than by compositor name. Capture via `cosmic-screenshot`,
  `grim`, `ksnip`/`gnome-screenshot`/`spectacle`, or the XDG Screenshot portal.
  Input via the XDG RemoteDesktop portal, `wtype`, `ydotool` or `evemu`.
- COSMIC support: `cosmic-comp` implements only `ext-image-copy-capture`, which
  the `grim` 1.4 in current distributions cannot use.
- `describe_environment` tool, reporting what is installed, what the compositor
  advertises, what was selected, and what a missing backend would need.
- `wayland_mcp/session_env.py`: recovers `XDG_RUNTIME_DIR`,
  `DBUS_SESSION_BUS_ADDRESS` and `WAYLAND_DISPLAY`, which MCP stdio clients strip.
- Portal permission is persisted via the `restore_token`, so the consent dialog
  appears once per machine rather than once per server start.
- Headless test suite (selection, keysyms, session recovery) and
  `scripts/verify_input.py`, which verifies input against a real GTK window.

### Changed
- Input needs no privilege. `setup.sh` is removed: it made every
  `/dev/input/event*` world-writable with a persistent udev rule, set setuid on
  `evemu-event` and added a NOPASSWD sudoers entry. `scripts/legacy-evemu-setup.sh`
  documents how to undo it. `evemu` remains as a last resort and activates only if
  a device is already writable.
- The portal backend types by keysym, so text is layout independent. Typing by
  keycode turned `ASAP 42` into `QSQP 'é` on AZERTY.
- `LICENSE` now contains the full GPL-3.0 text, which the licence requires be
  distributed with the work; it previously held only the short notice.

### Removed
- `docs/FORK-REPORT.md` and `docs/REPRO.md`, fork-era documentation written in
  French, so the repository keeps a single language.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2024

### Added
- Model Context Protocol (MCP) integration
- Screenshot capture with ruler overlays
- VLM image analysis via OpenRouter
- Image comparison functionality
- Mouse control (move, click, drag, scroll)
- Keyboard input simulation
- Action chaining with flexible syntax
- FastMCP server implementation

### Changed
- Improved reliability for Wayland environments
- Enhanced error handling and logging

### Documentation
- Comprehensive README with visual diagrams
- Configuration examples for multiple MCP clients
- Contributing guidelines
- Architecture documentation

## [0.3.0] - Previous

### Added
- Basic screenshot functionality
- Initial Wayland support

## [0.2.0] - Previous

### Added
- Core utilities and helpers

## [0.1.0] - Initial Release

### Added
- Project foundation
- Basic structure
