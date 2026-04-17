# CLIDE

A Clojure IDE written in Python 3.11+ with PyQt6.

**Status:** Pre-alpha — Phase 1 (application shell) only.
**Author:** Chuck Finch / Fragillidae Software
**License:** MIT

## What is CLIDE?

CLIDE is a self-contained integrated development environment for Clojure,
designed around the principle that everything needed for productive
REPL-driven development should live in one unified workspace.

## Requirements

- Python 3.11 or newer
- Linux (primary target: LMDE 7 / Mint 22.3); PyQt6 also runs on macOS and Windows
- A working Qt6 runtime (pulled in automatically by the `PyQt6` wheel)

## Running from source

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On first launch CLIDE writes its configuration directory:

- Linux:   `$XDG_CONFIG_HOME/clide`  (default `~/.config/clide`)
- macOS:   `~/Library/Application Support/clide`
- Windows: `%APPDATA%\clide`

Inside the config directory you will find `settings.json`, a rotating
`clide.log`, and a session cache.

## Current feature scope (Phase 1)

- Four-panel layout (file tree / editor / namespaces / REPL) with
  placeholder widgets
- Amber / blue / dark theme applied via QSS
- Menu bar, toolbar, and three-section status bar (all stubs)
- Persistent window geometry and dock state
- Rotating log file + console logging

All menu actions currently log a `not implemented: <menu path>` message.

## License

See `LICENSE` (MIT).
