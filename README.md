![CLJDE](images/cljde-banner.svg)

# CLJDE

A Clojure IDE written in Python 3.11+ with PyQt6.

**Status:** Pre-alpha — Phases 1–7 complete; Phase 8 (polish & packaging) pending.
**Author:** Chuck Finch / Fragillidae Software
**License:** MIT

## What is CLJDE?

CLJDE (pronounced "CLYDE") is a self-contained integrated development environment for Clojure,
designed around the principle that everything needed for productive
REPL-driven development should live in one unified workspace.

## Requirements

- Python 3.11 or newer
- Linux (primary target: LMDE 7 / Mint 22.3); PyQt6 also runs on macOS and Windows
- A working Qt6 runtime (pulled in automatically by the `PyQt6` wheel)
- To drive a REPL: a JVM with Clojure available via `clj`/`clojure` or
  Leiningen (`lein`) on your `PATH`

## Running from source

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On first launch CLJDE writes its configuration directory:

- Linux:   `$XDG_CONFIG_HOME/cljde`  (default `~/.config/cljde`)
- macOS:   `~/Library/Application Support/cljde`
- Windows: `%APPDATA%\cljde`

Inside the config directory you will find `settings.json`, a rotating
`cljde.log`, and a session cache.

## Current feature scope (Phases 1–7)

- Four-panel layout: file tree / tabbed editors / namespace browser / REPL,
  with movable, dockable panes and persistent window geometry
- Amber / blue / dark theme applied via QSS
- Clojure editor: syntax highlighting, paren matching, rainbow parens,
  line-number gutter, and paredit-style structural editing (slurp, barf,
  wrap, unwrap)
- File & project management: Leiningen / deps.edn / git project detection,
  multi-tab editing, recent files, `.gitignore`-aware tree, and session
  restore on relaunch
- Embedded nREPL client (custom bencode, threaded socket worker, sessions)
  with code evaluation, stdout/stderr/value/exception streaming
- REPL lifecycle: start a project REPL with automatic port detection and
  auto-connect, or connect to an external nREPL; stop / restart / disconnect
- Namespace tools: browser with filter and current-ns highlight, in-ns /
  reload / remove, fuzzy "Go to Namespace", and `tools.namespace` refresh
- Help → Quick Reference (`F1`) with shortcuts and a Clojure cheat sheet
- Rotating log file + console logging

See `docs/cljde_operators_guide.md` for a full usage guide and
`docs/cljde_implementation_plan.md` for the phase roadmap. Phase 8
(preferences dialog, splash screen, packaging) is still outstanding.

## License

See `LICENSE` (MIT).
