# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **Everything is in English now**: user interface, messages, scripts, tests and documentation
- README with a screenshot

## [0.1.3] – 2026-11-23

### Changed
- **New name: Node-Router** (previously "DIY Audio Router"). This applies to:
  - the window, tray and app menu entry
  - the AppImage file (`Node-Router-<version>-x86_64.AppImage`)
  - the AppImage folders (`~/.config/node-router`, `~/.local/share/node-router`)
- Old app menu and autostart entries and AppImage folders are taken over automatically
- Unchanged: the internal PipeWire names (`diy_…`) of virtual mics and effects, so
  existing settings keep working

## [0.1.2] – 2026-11-23

### Added
- **Bundled effect plugins** (in `plugins/` and in the AppImage), so nothing extra has to be
  installed:
  - RNNoise (noise suppression)
  - LSP (compressor, ducking)
  - `libatomic` as a fallback for systems without that library

  Licenses and origin: `plugins/README.md`
- **`install-deps.sh`**: installs missing system packages (PipeWire, pipewire-pulse,
  WirePlumber, pactl) for Ubuntu/Debian/Mint, Fedora, Arch/Manjaro and openSUSE
- **Startup check**: if something is missing, the app shows the matching command at startup
  (with "Copy command")

### Changed
- `install.sh --with-rnnoise` is no longer needed (the option is ignored)

## [0.1.1] – 2026-11-23

### Added
- **AppImage**: a single runnable file (`DIY-Audio-Router-0.1.1-x86_64.AppImage`) with Python,
  PySide6 and Qt. Download it, make it executable and start it.
- `build_appimage.sh` for building it yourself, and `tests/test_appimage.py`

### Changed
- As an AppImage, config and effect files live in `~/.config/diy-audio-router/` and
  `~/.local/share/diy-audio-router/`. When started from source they stay next to the program.
- From the AppImage, system programs (pw-link, pactl, pipewire …) are started with the system
  environment, not with the bundle's libraries
- With the AppImage, autostart and app menu entries point to the AppImage file

## [0.1.0] – 2026-11-22

First version.

### Routing
- Two fixed lists:
  - sources (input devices, app streams) on the left
  - targets (output devices, virtual microphones) on the right

  Connections are made by drag & drop as direct `pw-link` links.
- Routes, order and settings are kept in `config.json`. Routes are restored when an app
  restarts, or pauses and plays again.
- Paused apps stay as a greyed-out card, with saved routes shown dashed
- Removed WirePlumber connections stay removed (blocked routes)
- Ignore list for apps and devices that should never be shown (system sounds, for example)
- Virtual microphones (`Audio/Source/Virtual`) for Discord and similar apps
- Volume and mute per device or app (0–150 %)

### Effect blocks (PipeWire filter-chain)
- High-pass, equalizer (3 bands), delay, reverb
- Noise suppression (RNNoise), compressor, ducking with a music and a priority input
  (LSP plugins)
- Blocks can be moved freely in the mesh, sliders work live, and blocks keep running when the
  router is closed

### Usage and operation
- On/off switch: removes all of the router's own connections and stops effects, while the program
  stays open
- Theme: dark, light or follow system
- Tray icon, background operation, autostart (minimized), single instance
- Detects PipeWire restarts and restores virtual mics, effects and routes
- `install.sh` (venv, app menu entry, optional autostart and RNNoise download)
- Automated tests (`tests/run_all.py`) and a manual PipeWire restart test

### Known limitations
- Only tested on Ubuntu 24.04, PipeWire 1.0.5 and WirePlumber 0.4.17
- Not yet tested with Discord and real speech (see `TESTING.md`)

[Unreleased]: https://github.com/benborofn-lgtm/Node-Router/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/benborofn-lgtm/Node-Router/releases/tag/v0.1.3
[0.1.2]: https://github.com/benborofn-lgtm/Node-Router/releases/tag/v0.1.2
[0.1.1]: https://github.com/benborofn-lgtm/Node-Router/releases/tag/v0.1.1
[0.1.0]: https://github.com/benborofn-lgtm/Node-Router/releases/tag/v0.1.0
