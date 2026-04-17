# CLIDE — Clojure IDE Implementation Plan

**Project codename:** CLIDE (placeholder — final name TBD)
**Target platform:** Linux (primary: LMDE 7 / Mint 22.3), cross-platform capable
**Implementation language:** Python 3.11+
**GUI framework:** PyQt6
**License:** MIT (tentative)
**Author:** Chuck Finch / Fragillidae Software

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technical Architecture](#2-technical-architecture)
3. [Coding Standards](#3-coding-standards)
4. [Module & File Structure](#4-module--file-structure)
5. [Phase 1 — Foundation & Application Shell](#phase-1--foundation--application-shell)
6. [Phase 2 — Editor Component](#phase-2--editor-component)
7. [Phase 3 — File & Project Management](#phase-3--file--project-management)
8. [Phase 4 — nREPL Protocol Client](#phase-4--nrepl-protocol-client)
9. [Phase 5 — REPL Pane & Evaluation](#phase-5--repl-pane--evaluation)
10. [Phase 6 — REPL Process Management](#phase-6--repl-process-management)
11. [Phase 7 — Structural Awareness & Namespace Tools](#phase-7--structural-awareness--namespace-tools)
12. [Phase 8 — Polish, Preferences & Packaging](#phase-8--polish-preferences--packaging)
13. [AI Agent Prompts (Cold-Session Ready)](#ai-agent-prompts)
14. [Appendix A — nREPL Protocol Reference](#appendix-a--nrepl-protocol-reference)
15. [Appendix B — Keyboard Shortcut Map](#appendix-b--keyboard-shortcut-map)

---

## 1. Project Overview

### 1.1 Purpose

CLIDE is a self-contained integrated development environment for the Clojure programming language, designed around the principle that everything needed for productive Clojure development should live in one unified workspace. Unlike the prevailing Clojure tooling culture (Emacs + CIDER, Vim + Conjure, or multi-plugin VS Code configurations), CLIDE treats the REPL-driven development model as a first-class part of the IDE rather than as an add-on.

### 1.2 Design Principles

- **Unified workspace.** No external panels, no separate terminal windows, no context-switching to other applications for core development tasks.
- **Procedural clarity.** Code is organized around what it does rather than deep class hierarchies. OOP is used where Qt demands it (widget subclassing), not as a universal structure.
- **REPL-first.** The running REPL is the development target. Evaluating forms into a live REPL is as easy as typing.
- **Minimal viable scope.** This plan delivers a usable IDE, not a feature-complete competitor to Cursive. Later releases can expand scope.
- **Consistent visual language.** Amber/blue/dark theme consistent with other Fragillidae tooling.

### 1.3 Non-Goals (v1)

The following are explicitly out of scope for the initial release:

- Step debugger
- Test runner UI
- Refactoring tools beyond basic rename
- ClojureScript browser-connected REPL
- Built-in Git integration
- Remote pair-programming features
- Plugin system

These may be added in post-1.0 releases; the architecture should not preclude them, but the first version should ship without them.

### 1.4 Success Criteria for v1.0

CLIDE v1.0 is complete when a developer can:

1. Open an existing Leiningen or deps.edn Clojure project
2. Browse the project tree and open files in tabs
3. Launch an embedded nREPL session tied to that project
4. Evaluate the form at the cursor, the selection, or the whole file
5. See results and stdout/stderr inline in the REPL pane
6. Switch namespaces in the REPL
7. Reload a namespace after editing
8. Save their work and restart the session with state restored

---

## 2. Technical Architecture

### 2.1 Stack Summary

| Layer | Technology | Rationale |
|-------|------------|-----------|
| GUI | PyQt6 | Mature, familiar, good widget set |
| Editor | QPlainTextEdit subclass with custom highlighter | Full control over behavior |
| Syntax highlighting | QSyntaxHighlighter | Native Qt integration |
| REPL wire protocol | nREPL over TCP, bencode | Standard Clojure tooling protocol |
| Bencode | Custom minimal implementation | Avoid external dependency for 200 LOC |
| Async I/O | Qt signals/slots + QThread for socket | Integrates cleanly with event loop |
| Subprocess management | QProcess | Integrates with Qt, no asyncio conflict |
| Configuration | JSON files in platform config dir | Simple, portable, human-readable |
| Packaging | PyInstaller (single executable) | Standard for PyQt6 apps |

### 2.2 High-Level Component Diagram

```
┌────────────────────────────────────────────────────────────┐
│                      MainWindow                            │
│  ┌──────────┐ ┌────────────────────┐ ┌─────────────────┐   │
│  │          │ │                    │ │                 │   │
│  │  File    │ │   Editor Tabs      │ │    Namespace    │   │
│  │  Tree    │ │   (QTabWidget)     │ │    Browser      │   │
│  │          │ │                    │ │                 │   │
│  │          │ │                    │ │                 │   │
│  └──────────┘ └────────────────────┘ └─────────────────┘   │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │               REPL Pane                              │  │
│  │  ┌──────────────────────────────────┐ ┌───────────┐  │  │
│  │  │  Output history                  │ │ Status:   │  │  │
│  │  │                                  │ │ Connected │  │  │
│  │  ├──────────────────────────────────┤ │ NS: user  │  │  │
│  │  │  Input line                      │ │           │  │  │
│  │  └──────────────────────────────────┘ └───────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  Status bar: file info | cursor position | REPL status     │
└────────────────────────────────────────────────────────────┘
       ▲
       │
       │ Qt signals
       │
┌──────┴──────────┐          ┌────────────────────┐
│  nREPL Client   │◄────────►│  REPL Process      │
│  (TCP + bencode)│   TCP    │  (QProcess:        │
│                 │          │   lein/clj)        │
└─────────────────┘          └────────────────────┘
```

### 2.3 Key Architectural Decisions

**Decision 1: nREPL over TCP, not subprocess stdio.**
We connect to an nREPL server via TCP rather than driving a REPL through a subprocess's stdin/stdout. This gives us message IDs, async responses, clean out/err separation, and compatibility with any existing Clojure project that spins up its own nREPL.

**Decision 2: QThread for the nREPL socket loop.**
Socket reads are blocking. Running them in a QThread with signals back to the main thread keeps the UI responsive without needing asyncio, which conflicts awkwardly with Qt's event loop.

**Decision 3: QProcess for launching REPLs.**
When CLIDE spawns `lein repl :headless` or `clj -M:nrepl`, it does so via QProcess. We parse the port from the output and connect our nREPL client to it. This separation means CLIDE can also connect to REPLs launched externally.

**Decision 4: No editor framework dependency.**
We use QPlainTextEdit directly rather than QScintilla or a third-party editor widget. QScintilla adds a dependency and its own API learning curve; for a Clojure-focused editor, QPlainTextEdit gives us enough control with less weight.

**Decision 5: Bencode implemented in-tree.**
The bencode wire format is tiny (four data types). Implementing encoder/decoder ourselves (~150 lines) avoids a dependency and makes the code more transparent for debugging wire issues.

---

## 3. Coding Standards

### 3.1 File Size Limits

These are soft limits. A module reaching its limit should be considered for splitting, not mandatorily split.

| Module Type | Target | Hard Ceiling |
|-------------|--------|--------------|
| UI widget modules | ~250 lines | 400 lines |
| Protocol/wire modules | ~200 lines | 350 lines |
| Orchestration/controller modules | ~200 lines | 350 lines |
| Utility/helper modules | ~150 lines | 250 lines |
| Entry point (`main.py`) | ~80 lines | 150 lines |

Rationale: files under 300 lines fit in a single screen scroll context and are easier for both human review and AI agent sessions to reason about. Over 400 lines is a strong signal that a module has grown two responsibilities.

### 3.2 Style Rules

- **Python version:** 3.11 minimum (for pattern matching, exception groups, and improved typing).
- **Type hints:** required on public function signatures, optional on internal helpers.
- **Docstrings:** required on modules, classes, and public functions. Triple-quoted, first line a single summary sentence.
- **Naming:** `snake_case` for functions and variables, `PascalCase` for classes, `SCREAMING_SNAKE_CASE` for module-level constants.
- **Imports:** grouped (stdlib / third-party / local) with a blank line between groups.
- **Qt signals:** suffixed `_signal` in attribute names for clarity (e.g., `eval_complete_signal`).
- **No wildcard imports.**
- **No circular imports.** If two modules need each other, a third module owns the shared code or an interface.
- **Procedural preference:** if a class has no state beyond `__init__` arguments and only one method, it should be a function.

### 3.3 Error Handling

- Network/IO errors surface as status bar messages and REPL pane warnings, not exceptions that crash the UI.
- All QThread workers catch exceptions at the top of their run loop and emit an error signal.
- File I/O uses context managers; never leave file handles dangling.
- `assert` is for developer invariants only, never for validating user input or network data.

### 3.4 Testing

- Unit tests with `pytest` for all non-UI modules (bencode, nREPL message builders, config, parser helpers).
- UI tests deferred to v1.1 — manual smoke testing is acceptable for v1.0 given the personal-use priority.
- A test is added with any bug fix to prevent regression.

---

## 4. Module & File Structure

```
clide/
├── main.py                          # Entry point, ~80 lines
├── pyproject.toml                   # Project metadata, dependencies
├── requirements.txt                 # Pinned dependency versions
├── README.md
├── LICENSE
├── clide/
│   ├── __init__.py
│   ├── app.py                       # QApplication setup, ~100 lines
│   ├── main_window.py               # MainWindow class, ~300 lines
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py              # Load/save settings JSON, ~150 lines
│   │   ├── theme.py                 # Color palette, fonts, ~120 lines
│   │   └── paths.py                 # Platform-specific config paths, ~80 lines
│   ├── editor/
│   │   ├── __init__.py
│   │   ├── editor_widget.py         # QPlainTextEdit subclass, ~250 lines
│   │   ├── clojure_highlighter.py   # QSyntaxHighlighter for Clojure, ~200 lines
│   │   ├── paren_matcher.py         # Bracket matching logic, ~150 lines
│   │   ├── line_numbers.py          # Line number area widget, ~120 lines
│   │   └── form_detector.py         # Find form boundaries at cursor, ~180 lines
│   ├── files/
│   │   ├── __init__.py
│   │   ├── file_tree.py             # Project tree widget, ~200 lines
│   │   ├── tab_manager.py           # Multi-tab editor container, ~220 lines
│   │   ├── file_ops.py              # Open, save, new operations, ~180 lines
│   │   └── project.py               # Project root detection (lein, deps.edn), ~150 lines
│   ├── nrepl/
│   │   ├── __init__.py
│   │   ├── bencode.py               # Encoder/decoder, ~150 lines
│   │   ├── client.py                # nREPL TCP client class, ~250 lines
│   │   ├── socket_worker.py         # QThread for socket reads, ~180 lines
│   │   ├── messages.py              # Message builders (eval, clone, etc.), ~150 lines
│   │   └── session.py               # Session state tracking, ~180 lines
│   ├── repl/
│   │   ├── __init__.py
│   │   ├── repl_pane.py             # REPL UI widget, ~280 lines
│   │   ├── output_view.py           # Output history display, ~200 lines
│   │   ├── input_line.py            # REPL input with history, ~180 lines
│   │   ├── process_manager.py       # QProcess for lein/clj, ~220 lines
│   │   └── port_detector.py         # Parse nREPL port from output, ~100 lines
│   ├── namespace/
│   │   ├── __init__.py
│   │   ├── ns_browser.py            # Namespace list widget, ~180 lines
│   │   └── ns_operations.py         # Reload, switch, require, ~150 lines
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── toolbar.py               # Main toolbar, ~150 lines
│   │   ├── menubar.py               # Menu construction, ~200 lines
│   │   ├── status_bar.py            # Status bar widget, ~120 lines
│   │   ├── preferences_dialog.py    # Preferences UI, ~250 lines
│   │   └── icons.py                 # Icon loading, ~80 lines
│   └── resources/
│       ├── icons/                   # SVG icons
│       ├── themes/                  # Theme JSON files
│       └── syntax/                  # Clojure syntax definitions
└── tests/
    ├── __init__.py
    ├── test_bencode.py
    ├── test_form_detector.py
    ├── test_messages.py
    ├── test_port_detector.py
    └── test_project.py
```

**Line count estimate total:** approximately 5,500–6,500 lines of Python across roughly 35 modules. This is realistic for an 8-phase personal IDE project.

---

## Phase 1 — Foundation & Application Shell

### 1.1 Objective

Establish the project skeleton, dependency management, entry point, and a functioning PyQt6 main window with empty panels in their final layout positions. No functionality — this phase proves the structure works end-to-end.

### 1.2 Deliverables

- `pyproject.toml` and `requirements.txt` with pinned dependencies
- Directory structure matching Section 4
- `main.py` entry point that launches a window
- `MainWindow` class with dock-based layout containing named empty placeholders for: file tree, editor area, namespace browser, REPL pane
- Menu bar with File / Edit / View / REPL / Help menus (items can be stubs that log "not implemented")
- Toolbar with standard buttons (stubs acceptable)
- Status bar with three sections: file info, cursor position, REPL status
- Configuration system that reads/writes a JSON settings file in the platform config directory
- Theme module that defines the amber/blue/dark palette and applies it via QSS
- Logging configuration that writes to a rotating log file in the config directory

### 1.3 Module Scope

Build these modules: `main.py`, `clide/app.py`, `clide/main_window.py`, `clide/config/settings.py`, `clide/config/theme.py`, `clide/config/paths.py`, `clide/ui/menubar.py`, `clide/ui/toolbar.py`, `clide/ui/status_bar.py`.

### 1.4 Acceptance Criteria

- Running `python main.py` opens a window
- The window has the four-panel layout with visible placeholder labels
- Menu items exist and are clickable (stubs log to the log file)
- Resizing the window resizes panels proportionally
- Quitting saves window geometry to the settings file
- Reopening restores the saved geometry
- Applying a theme change via a hardcoded test shows immediate color changes

### 1.5 Out of Scope for Phase 1

File opening, syntax highlighting, REPL anything. Truly just the shell.

---

## Phase 2 — Editor Component

### 2.1 Objective

Build the Clojure source editor widget with syntax highlighting, line numbers, paren matching, and basic cursor/selection awareness. At the end of this phase, you can type Clojure code and see it highlighted, but cannot evaluate it.

### 2.2 Deliverables

- `EditorWidget` — QPlainTextEdit subclass with:
  - Line number gutter
  - Current line highlighting
  - Configurable font (monospace, size from settings)
  - Tab-to-spaces conversion (Clojure convention: 2 spaces)
  - Matching paren/bracket/brace highlight
  - Cursor position reporting (signal to status bar)
- `ClojureHighlighter` — QSyntaxHighlighter subclass recognizing:
  - Special forms (`def`, `defn`, `let`, `if`, `fn`, `do`, `loop`, `recur`, `quote`, `var`, etc.)
  - Core functions (a curated list, not exhaustive)
  - Keywords (`:foo`, `::ns/keyword`)
  - Strings (with escape handling)
  - Comments (`;`, `#_`, `(comment ...)`)
  - Numbers (integer, decimal, ratio, hex, octal)
  - Character literals (`\a`, `\newline`, `\u0041`)
  - Metadata (`^{...}`, `^:foo`)
- `ParenMatcher` — given a cursor position, finds the matching bracket and returns both positions or indicates imbalance
- Form detection logic that identifies the top-level form or innermost form enclosing the cursor (returned as a `(start_pos, end_pos)` tuple)

### 2.3 Module Scope

`clide/editor/editor_widget.py`, `clide/editor/clojure_highlighter.py`, `clide/editor/paren_matcher.py`, `clide/editor/line_numbers.py`, `clide/editor/form_detector.py`.

### 2.4 Acceptance Criteria

- Open a standalone editor test window and type Clojure code
- Observe syntax highlighting update as you type
- Observe matching parens highlight when cursor is adjacent to any `(`, `[`, `{`, `)`, `]`, `}`
- Verify that a call to `form_detector.form_at(cursor_pos, text)` returns correct boundaries for:
  - Top-level form (like a `defn`)
  - Nested form (cursor inside a `let`)
  - Cursor in whitespace between forms (returns None)
  - Cursor inside a string literal (does not treat quote chars as paren)
  - Cursor inside a comment (returns None)
- Line number gutter shows correct numbers and resizes with window
- Tab key inserts 2 spaces, not a tab character

### 2.5 Out of Scope for Phase 2

Autocomplete, goto-definition, any REPL interaction.

---

## Phase 3 — File & Project Management

### 3.1 Objective

Connect the editor to the filesystem. Enable opening projects, browsing files, opening multiple files in tabs, and saving changes.

### 3.2 Deliverables

- `FileTreeWidget` — QTreeView + QFileSystemModel rooted at a project directory
  - Double-click to open file in new tab
  - Right-click context menu (new file, rename, delete, reveal)
  - Filters hidden files by default (toggle in view menu)
  - Highlights the currently focused file
- `TabManager` — QTabWidget wrapping multiple `EditorWidget` instances
  - Close button on each tab
  - Modified indicator (asterisk in tab label)
  - Ctrl+Tab cycling
  - Unsaved-changes confirmation on close
  - Tab state persisted to settings (reopen same files on relaunch)
- `file_ops.py` — functional module with: `open_file`, `save_file`, `save_file_as`, `new_file`, `close_file` — these operate on the TabManager
- `project.py` — project root detection:
  - Walks up from a given path looking for `project.clj`, `deps.edn`, or `.git`
  - Exposes a `Project` dataclass with `root`, `type` (lein/deps/other), and `name`
- Recent files list in File menu (last 10)
- Project menu items: Open Project, Close Project

### 3.3 Module Scope

`clide/files/file_tree.py`, `clide/files/tab_manager.py`, `clide/files/file_ops.py`, `clide/files/project.py`.

### 3.4 Acceptance Criteria

- Open a Clojure project directory and see its tree in the file tree panel
- Double-click a `.clj` file and see it open in a tab with syntax highlighting
- Edit the file, see the modified indicator appear
- Save with Ctrl+S, see the indicator clear
- Close a modified tab, see a confirmation dialog
- Close CLIDE with open tabs, relaunch, see the same tabs reopened with cursor positions restored
- Open a second project; verify old tabs are handled sensibly (close or migrate)
- Recent files menu populates and works

### 3.5 Out of Scope for Phase 3

Still no REPL.

---

## Phase 4 — nREPL Protocol Client

### 4.1 Objective

Build the network layer that speaks nREPL over TCP. No UI work in this phase — this is a library that the next phase consumes.

### 4.2 Deliverables

- `bencode.py` — encoder and decoder for the four bencode types (integer, byte string, list, dictionary). Handles nested structures. Returns Python dicts/lists/bytes. Includes a streaming decoder that can handle partial reads.
- `SocketWorker` — QThread subclass that owns a socket, runs a read loop, decodes bencode messages from the stream, and emits a signal for each complete message received. Handles connection errors gracefully.
- `NreplClient` — the public API class:
  - `connect(host, port)` — establishes connection, starts SocketWorker
  - `disconnect()` — clean shutdown
  - `send(message_dict)` — encodes and sends; returns a message ID
  - `response_signal` — Qt signal emitting `(message_id, response_dict)` for each response
  - `connection_state_signal` — emits `"connecting" | "connected" | "disconnected" | "error"`
  - Handles the "clone session" handshake on connect to get a session ID
  - Tracks pending requests by ID
- `messages.py` — pure functions that build nREPL message dictionaries:
  - `build_eval(code, session, ns=None)`
  - `build_clone(session=None)`
  - `build_close(session)`
  - `build_describe()`
  - `build_interrupt(session, interrupt_id)`
  - `build_load_file(file_contents, file_name, file_path, session)`
- `session.py` — tracks active session IDs, current namespace per session, and pending eval tracking

### 4.3 Module Scope

`clide/nrepl/bencode.py`, `clide/nrepl/client.py`, `clide/nrepl/socket_worker.py`, `clide/nrepl/messages.py`, `clide/nrepl/session.py`.

### 4.4 Acceptance Criteria

Test harness outside the GUI:

- Start an nREPL server manually (e.g., `clj -M:nrepl` in a scratch directory)
- Note the port from its output
- Run a test script that uses `NreplClient` to:
  - Connect to the port
  - Clone a session
  - Send `(+ 1 2)` and receive `3`
  - Send `(println "hello")` and receive `hello` as out plus `nil` as value
  - Send `(/ 1 0)` and receive an exception response correctly
  - Send a long-running eval and successfully interrupt it
  - Cleanly disconnect
- Unit tests for bencode round-trip, message builders, and partial-read handling

### 4.5 Out of Scope for Phase 4

No UI integration. This phase produces a testable library.

---

## Phase 5 — REPL Pane & Evaluation

### 5.1 Objective

Wire the nREPL client into the UI. Add the REPL pane. Enable evaluating forms from the editor and seeing results.

### 5.2 Deliverables

- `ReplPane` — the main REPL UI widget containing:
  - `OutputView` — a read-only text area showing interleaved eval commands, stdout, stderr, and results. Each category is styled differently (colors from theme).
  - `InputLine` — a single-line (or expandable) input at the bottom for typing expressions directly into the REPL
  - A small status strip showing: connection state indicator, current namespace, session ID (short form)
- `InputLine` behaviors:
  - Enter submits the current expression
  - Up/Down cycles through eval history
  - Shift+Enter inserts a newline without submitting
  - Tab cycles completions (stub — real completion is post-v1)
- Editor-to-REPL commands (wired in MainWindow):
  - **Ctrl+Enter** — evaluate the form at the cursor (uses `form_detector` from Phase 2)
  - **Ctrl+Shift+Enter** — evaluate the selection
  - **Ctrl+Alt+Enter** — evaluate the entire file (via `load-file` nREPL op)
  - Each command shows the submitted code and the response in the OutputView
- Error display: exceptions are rendered with their class, message, and stack trace section in a distinct color
- Print-capture handling: stdout and stderr messages are tagged and styled per their source

### 5.3 Module Scope

`clide/repl/repl_pane.py`, `clide/repl/output_view.py`, `clide/repl/input_line.py`, plus wiring updates in `main_window.py`.

### 5.4 Acceptance Criteria

Assumes a running nREPL server you manually connect to (Phase 6 automates this):

- Open the REPL pane, manually trigger a connect-to-host-port dialog, connect to a running nREPL
- Status strip shows "Connected" and the namespace (default: `user`)
- Type `(+ 1 2)` in the input line, press Enter, see `3` appear as a result
- Type `(println "test")` and see `test` styled as stdout and `nil` styled as return value
- In the editor, place cursor inside a `defn` form, press Ctrl+Enter, see the form submitted and `#'user/your-fn` returned
- Select an expression and press Ctrl+Shift+Enter, see only that expression evaluated
- Press Ctrl+Alt+Enter on a whole file with multiple defns, see it loaded
- Cause an exception, see it formatted clearly
- Test history: use Up/Down in the input line to recall previous expressions

### 5.5 Out of Scope for Phase 5

No process spawning — user still connects manually.

---

## Phase 6 — REPL Process Management

### 6.1 Objective

Eliminate manual nREPL connection. CLIDE can spawn an nREPL process in a project and auto-connect.

### 6.2 Deliverables

- `ReplProcessManager` — wraps QProcess to launch REPLs:
  - Detects project type (lein or deps) from the current project
  - For lein: runs `lein repl :headless :host 127.0.0.1`
  - For deps: runs `clojure -M:nrepl` or `clj -M:nrepl` (configurable command in settings)
  - Captures stdout to detect the "nREPL server started on port XXXX" line
  - Emits a `port_detected_signal(port)` when the port is known
  - Emits `process_state_signal` for start/stop/crash
  - Handles graceful shutdown on CLIDE quit
  - Logs process output to the REPL pane in a dimmed style (so you can see startup messages)
- `port_detector.py` — regex-based parser for the port line. Support both lein and clj variants.
- UI additions:
  - Toolbar button "Start REPL" (enabled when a project is open)
  - Toolbar button "Stop REPL" (enabled when running)
  - Toolbar button "Restart REPL"
  - Status bar REPL indicator shows: no project / stopped / starting / running (port) / crashed
- Connection flow:
  1. User clicks Start REPL
  2. ProcessManager spawns the appropriate command in the project dir
  3. port_detector parses the port from output
  4. NreplClient auto-connects to the detected port
  5. UI updates to reflect connected state
- Ability to connect to an external nREPL (retain the manual connect dialog from Phase 5 as an alternative)

### 6.3 Module Scope

`clide/repl/process_manager.py`, `clide/repl/port_detector.py`, updates to MainWindow and toolbar.

### 6.4 Acceptance Criteria

- Open a Leiningen project, click Start REPL, see startup messages in REPL pane, see "Connected" status, be able to evaluate
- Open a deps.edn project, same flow works
- Click Stop REPL, see clean shutdown, status updates
- Click Restart REPL, see clean restart
- Close CLIDE while REPL is running, verify the REPL process is terminated (no orphans)
- Kill the REPL process externally, verify CLIDE detects this and updates UI state without crashing
- Startup messages that aren't the port line are still displayed (useful for debugging)

### 6.5 Out of Scope for Phase 6

Nothing deferred — this closes the critical path for a usable IDE.

---

## Phase 7 — Structural Awareness & Namespace Tools

### 7.1 Objective

Add the quality-of-life features that distinguish a Clojure IDE from a text editor with a REPL.

### 7.2 Deliverables

- **Paren balance checking**: editor shows a red underline or margin marker on unbalanced forms. Runs on a 500ms debounce after typing stops.
- **Rainbow parens** (togglable in settings): nested brackets colored by depth.
- **Structural editing basics**:
  - Slurp forward (Alt+Shift+Right): extend current form to include next form
  - Barf forward (Alt+Shift+Left): eject last element of current form
  - Wrap with parens (Alt+W, then `(`, `[`, or `{`)
  - Unwrap (Alt+U): replace current form with its contents
  - (Full paredit is out of scope; these are the highest-value operations.)
- **Namespace browser** (`NsBrowser`):
  - Lists all currently loaded namespaces in the connected REPL
  - Refreshes on demand and after evaluations
  - Double-click a namespace to switch to it (sends `in-ns`)
  - Right-click menu: Switch To, Reload, Remove (ns-unmap)
- **Namespace operations** (toolbar buttons and menu items):
  - Reload current file's namespace (`(require 'ns :reload)`)
  - Reload all changed namespaces (if `tools.namespace` is available, use `refresh`; else fallback)
  - Switch current REPL namespace to current file's ns
- **Go to namespace dialog** (Ctrl+Shift+N): fuzzy-match picker over loaded namespaces

### 7.3 Module Scope

`clide/namespace/ns_browser.py`, `clide/namespace/ns_operations.py`, structural editing additions to `clide/editor/editor_widget.py`, balance checker possibly as new `clide/editor/balance_checker.py`.

### 7.4 Acceptance Criteria

- Type an unbalanced form, see the indicator after pause
- Balance an existing form, see the indicator clear
- Rainbow parens toggle via View menu, effect is immediate
- Slurp/barf operations work on well-formed code and don't destroy code on malformed input (refuse and beep instead)
- Namespace browser populates after connecting and evaluating a `require`
- Switching namespace via double-click updates the REPL's current ns indicator
- Reload command re-requires the namespace and picks up recent edits

### 7.5 Out of Scope for Phase 7

Full paredit, autocomplete, goto-definition. These are post-v1.

---

## Phase 8 — Polish, Preferences & Packaging

### 8.1 Objective

Convert the working IDE into something you would enjoy using daily. Package it for distribution.

### 8.2 Deliverables

- **Preferences dialog** with tabs:
  - Editor: font, size, tab width, line numbers, current-line highlight, rainbow parens
  - Theme: color overrides (expose the palette variables)
  - REPL: lein command, clj command, default connect host/port, max output history lines
  - Keyboard: view (not edit) the shortcut map
  - Paths: REPL working directory default, log file location
- **Keyboard shortcut finalization**: all commands bound to sensible keys, documented in Help menu
- **Help menu**:
  - About dialog (version, license, Fragillidae branding)
  - Keyboard shortcut reference (opens a viewable dialog)
  - Link to nREPL documentation
  - Report issue (opens GitHub issue URL in browser)
- **Icons**: amber/blue/dark SVG icons for toolbar and tabs consistent with other Fragillidae tools. Clojure syntax-character lambda glyph as app icon.
- **Splash screen** on startup (fast, not gratuitous)
- **Logging review**: ensure useful diagnostic info is captured; rotate logs at 5MB
- **README** with installation, quick start, and screenshots
- **Packaging**:
  - PyInstaller spec file for Linux x86_64
  - AppImage build (optional)
  - Install instructions for running from source
  - Version tagging in Git

### 8.3 Module Scope

`clide/ui/preferences_dialog.py`, `clide/ui/icons.py`, resource files, packaging scripts.

### 8.4 Acceptance Criteria

- Preferences dialog opens, changes persist, take effect without restart where possible
- All shortcuts from Appendix B work
- Icons render correctly at all sizes
- Packaged executable runs on a fresh LMDE 7 install
- README is sufficient for you to set up a fresh dev environment from scratch
- Version 1.0.0 tagged in Git

### 8.5 Out of Scope for Phase 8

macOS and Windows packaging (can be added later from the same codebase).

---

# AI Agent Prompts

This section contains self-contained prompts designed for cold AI agent sessions. Each prompt includes the full context an agent needs to execute the phase without prior conversation history. Copy-paste the relevant prompt into a fresh session.

---

## AI Prompt — Universal Preamble

Use this preamble at the start of every phase prompt. It establishes project-wide conventions so you don't repeat them in every phase.

```
You are helping me build CLIDE, a Clojure IDE written in Python 3.11+ with PyQt6.

PROJECT CONTEXT:
- Single-developer project; target user is the developer (me, Chuck Finch)
- Target platform primarily Linux (LMDE 7 and Mint 22.3)
- License will be MIT
- Design aesthetic: amber/blue/dark theme consistent with Fragillidae Software tools
- I have 49 years of computing experience, 9+ IDE projects shipped, so you can assume technical fluency
- I prefer procedural clarity over deep OOP hierarchies
- I prefer readable, explicit code over clever code

ABSOLUTE CONVENTIONS (do not violate without asking):
1. Python 3.11+ only. Use modern syntax (match statements where appropriate, union types with |, etc.)
2. Type hints on all public function signatures
3. Docstrings on modules, classes, and public functions (first line is a summary sentence)
4. File size target: UI widgets ~250 lines, protocols ~200 lines, entry points ~80 lines
5. Hard ceiling: 400 lines for any single Python module. If approaching, propose a split.
6. No wildcard imports. Grouped imports: stdlib / third-party / local.
7. snake_case functions/vars, PascalCase classes, SCREAMING_SNAKE_CASE constants
8. Qt signals suffixed _signal
9. QThread for blocking I/O (socket reads). QProcess for external processes. No asyncio.
10. Never use assert for user input or network validation — only for developer invariants.
11. File I/O via context managers always.
12. Procedural preference: if a class has one method and only __init__ state, make it a function.

DELIVERABLE FORMAT:
- When creating files, provide the full file content with the target path as a header
- When modifying files, show the full modified file (not diffs) unless the file is large and unchanged regions are clearly marked
- Group related files together in your response
- End each response with a testing checklist — exactly what I should do to verify the phase is working

ASK BEFORE:
- Adding new third-party dependencies
- Deviating from the specified module structure
- Making architectural decisions that affect other phases
- Exceeding the file size ceiling

BEGIN READING THE SPECIFIC PHASE INSTRUCTIONS BELOW.
```

---

## AI Prompt — Phase 1: Foundation & Application Shell

```
[PASTE UNIVERSAL PREAMBLE ABOVE]

PHASE 1 — Foundation & Application Shell

OBJECTIVE:
Create the CLIDE project structure and a working PyQt6 main window with empty panels
laid out in their final positions. No functionality yet — just the structural
skeleton that proves the layout, configuration, theming, and logging all work
end to end.

DELIVERABLES:
1. Project files:
   - pyproject.toml with project metadata and dependencies
   - requirements.txt with pinned versions
   - README.md with a brief project description and run instructions
   - .gitignore suitable for Python/PyQt6 projects
   - LICENSE file (MIT)

2. Directory structure exactly as follows:
   clide/
     main.py
     clide/
       __init__.py
       app.py
       main_window.py
       config/
         __init__.py
         settings.py
         theme.py
         paths.py
       ui/
         __init__.py
         menubar.py
         toolbar.py
         status_bar.py
       resources/
         themes/
           default.json

3. Python modules:
   - main.py: entry point, ~80 lines. Initializes logging, QApplication, MainWindow.
   - clide/app.py: QApplication subclass or factory function, ~100 lines.
     Sets org/app name, loads theme, handles app-wide signals.
   - clide/main_window.py: MainWindow class, ~300 lines. QMainWindow subclass.
     Uses QDockWidget or QSplitter layout with four zones:
       LEFT:   file tree placeholder (QLabel "File Tree")
       CENTER: editor tabs placeholder (QLabel "Editor Area")
       RIGHT:  namespace browser placeholder (QLabel "Namespaces")
       BOTTOM: REPL pane placeholder (QLabel "REPL")
     Saves and restores window geometry and dock state to settings on quit/launch.
   - clide/config/settings.py: load/save JSON settings file. Auto-creates on first
     run with sensible defaults. ~150 lines.
   - clide/config/theme.py: defines the amber/blue/dark palette and generates a
     QSS stylesheet string. ~120 lines. Palette should be:
       background dark:   #1a1a1a
       background medium: #252525
       background light:  #2d2d2d
       foreground:        #e0e0e0
       foreground dim:    #a0a0a0
       amber primary:     #ffb000
       amber bright:      #ffcc44
       blue primary:      #4a90e2
       blue bright:       #6bb6ff
       error red:         #e04848
       success green:     #50c878
   - clide/config/paths.py: determines platform config dir (XDG on Linux,
     ~/Library/Application Support on macOS, %APPDATA% on Windows) and provides
     resolved paths for settings file, log file, session cache. ~80 lines.
   - clide/ui/menubar.py: constructs the menu bar. Menus: File (New, Open File,
     Open Project, Save, Save As, Recent, Exit), Edit (Undo, Redo, Cut, Copy,
     Paste, Find), View (Toggle File Tree, Toggle REPL, Toggle Namespaces,
     Rainbow Parens, Full Screen), REPL (Start, Stop, Restart, Connect External,
     Eval Form, Eval Selection, Eval File, Reload NS, Switch NS), Help (About,
     Shortcuts, Report Issue). All items wired to stub methods on MainWindow
     that log "not implemented: <menu path>" via logging. ~200 lines.
   - clide/ui/toolbar.py: main toolbar with stub buttons for common actions.
     ~150 lines.
   - clide/ui/status_bar.py: status bar with three QLabel sections — file info,
     cursor position, REPL status. Public update methods. ~120 lines.

4. Logging:
   - Configured in main.py
   - Rotating file handler writing to the log path from paths.py
   - Console handler at INFO level
   - File handler at DEBUG level
   - Log format includes timestamp, level, module, message

5. Theme application:
   - theme.py generates QSS
   - app.py applies it on startup
   - Verify by observing dark backgrounds, amber accents on default Qt widgets

DEPENDENCIES (put in requirements.txt, pin to currently stable versions):
- PyQt6
- No others yet

ACCEPTANCE TEST:
After your implementation, I should be able to:
1. Create a venv, pip install -r requirements.txt, python main.py
2. See a window open with the four-panel layout and placeholder labels
3. Click menu items and see "not implemented" messages in the log file
4. Resize the window; panels resize proportionally
5. Close and reopen; window returns to the previous size and position
6. Inspect the settings JSON file and see it contains geometry data
7. Inspect the log file and see startup messages

OUT OF SCOPE:
Do not implement any file editing, syntax highlighting, or REPL functionality.
Placeholders only. Phase 2 adds the editor.

OUTPUT FORMAT:
Start with a brief plan of what files you'll create. Then produce each file in
full with its target path as a heading. End with the testing checklist.
```

---

## AI Prompt — Phase 2: Editor Component

```
[PASTE UNIVERSAL PREAMBLE ABOVE]

PHASE 2 — Editor Component

CONTEXT:
Phase 1 produced a working PyQt6 shell with empty panels. The project
structure matches Section 4 of the implementation plan. Theme, settings,
and logging are functional. No file editing exists yet.

OBJECTIVE:
Build a complete Clojure source editor widget with syntax highlighting, line
numbers, paren matching, and form detection. At the end of this phase I can
type Clojure code into the editor area and see it highlighted correctly, but
there is still no REPL interaction.

FILES TO CREATE:
- clide/editor/__init__.py
- clide/editor/editor_widget.py (~250 lines)
- clide/editor/clojure_highlighter.py (~200 lines)
- clide/editor/paren_matcher.py (~150 lines)
- clide/editor/line_numbers.py (~120 lines)
- clide/editor/form_detector.py (~180 lines)
- tests/test_form_detector.py (pytest tests for form boundary detection)

FILES TO MODIFY:
- clide/main_window.py: replace the "Editor Area" placeholder label with a single
  EditorWidget instance for testing. (Tab management comes in Phase 3 — for now,
  just one editor in the center.)

SPECIFICATIONS:

EditorWidget (QPlainTextEdit subclass):
- Custom line number gutter on the left
- Highlights the current line (subtle background tint from theme)
- Font from settings (default: monospace family, 11pt); configurable
- Tab key inserts 2 spaces
- Shift+Tab outdents 2 spaces
- Emits cursor_position_changed_signal(line, column) — MainWindow connects this
  to the status bar
- Public method set_text(s: str), get_text() -> str
- Uses ClojureHighlighter on its document

ClojureHighlighter (QSyntaxHighlighter subclass):
Recognize and style (with theme colors):
- Special forms: def, defn, defn-, defmacro, let, let*, letfn, if, if-not, if-let,
  when, when-not, when-let, fn, fn*, do, loop, recur, quote, var, try, catch,
  finally, throw, cond, condp, case, and, or, not, ns, in-ns, require, use, import,
  deref, reify, defrecord, defprotocol, defmulti, defmethod, extend, extend-type,
  extend-protocol, for, doseq, dotimes, while, binding, with-open, with-meta,
  set!, new, ., .., ->, ->>, as->, some->, some->>, cond->, cond->>
  (styled in amber bright, bold)
- Core functions: a curated list of ~60 common ones (map, filter, reduce, apply,
  first, rest, cons, conj, count, range, partition, take, drop, etc.)
  (styled in amber primary)
- Keywords (:foo, ::foo, :ns/foo) — styled in blue bright
- Strings "..." with \\ escape handling — styled in success green
- Comments ; to end of line — styled in foreground dim, italic
- #_ form comment — entire next form dimmed (approximation OK for v1)
- (comment ...) — dimmed as a whole (approximation OK for v1)
- Numbers (integer, decimal, ratio 1/2, hex 0x1F, octal 0755, negative) — blue primary
- Character literals \\a \\newline \\u0041 \\space \\tab — success green
- Metadata ^{...} ^:foo ^String — blue primary, italic

ParenMatcher:
- Pure module-level functions, not a class
- find_matching(text: str, pos: int) -> int | None
  Given a cursor position, if adjacent to a bracket character, finds the matching
  bracket and returns its position. Otherwise returns None.
- Handles (), [], {}
- Correctly ignores brackets inside strings and comments
- Used by EditorWidget's selectionChanged handler to highlight matches

LineNumberArea:
- QWidget subclass painted by EditorWidget via a paint event
- Width scales with the number of digits needed
- Background and text colors from theme
- Current line number highlighted

FormDetector:
- Pure module-level functions
- form_at(text: str, pos: int) -> tuple[int, int] | None
  Returns (start, end) of the innermost form containing pos.
  Returns None if pos is in whitespace between forms, in a comment, or in a
  top-level string.
- top_level_form_at(text: str, pos: int) -> tuple[int, int] | None
  Returns (start, end) of the top-level form containing pos.
- Uses a simple hand-written scanner: track string state, comment state, and
  bracket depth while walking the text.
- Does NOT need to be a full reader. It needs to identify balanced forms
  treating parens/brackets/braces as equivalent and respecting string/comment
  escaping.

TESTS (tests/test_form_detector.py):
Cover at minimum:
- Cursor inside a top-level (defn ...) returns the defn bounds
- Cursor inside a nested (let [...] ...) returns the let bounds with form_at
- Cursor inside a nested let returns the defn bounds with top_level_form_at
- Cursor in whitespace between two forms returns None for form_at
- Cursor inside a string "..." returns the form containing the string, not the
  string itself; string quotes do not confuse bracket counting
- Cursor inside a ; comment returns None for form_at
- Cursor at a bracket character returns the form starting/ending at that bracket
- Unbalanced text does not crash; returns None gracefully

ACCEPTANCE TEST:
1. Launch CLIDE
2. Click in the editor area and type a nontrivial Clojure snippet
   (defn fib [n] (if (< n 2) n (+ (fib (dec n)) (fib (- n 2)))))
3. Verify highlighting of defn, if, <, +, dec, the keyword-like forms
4. Place cursor beside a paren; verify its match is highlighted
5. Place cursor inside the string "hello \\"world\\""; verify bracket highlighting
   inside the string does NOT fire
6. Cursor position should be shown in the status bar
7. Run pytest tests/ and see form_detector tests pass

OUT OF SCOPE:
File opening, tabs, REPL, autocomplete, goto-definition.

OUTPUT FORMAT:
Plan first, then files in full, then testing checklist.
```

---

## AI Prompt — Phase 3: File & Project Management

```
[PASTE UNIVERSAL PREAMBLE ABOVE]

PHASE 3 — File & Project Management

CONTEXT:
Phases 1 and 2 produced a CLIDE with a styled main window and a single working
Clojure editor widget placed in the center of the window. Syntax highlighting,
line numbers, paren matching, and form detection all work. The project structure
follows Section 4 of the implementation plan.

OBJECTIVE:
Connect the editor to the filesystem. Add a file tree, multi-tab editing, file
operations (open, save, new, close), and project root detection.

FILES TO CREATE:
- clide/files/__init__.py
- clide/files/file_tree.py (~200 lines)
- clide/files/tab_manager.py (~220 lines)
- clide/files/file_ops.py (~180 lines)
- clide/files/project.py (~150 lines)
- tests/test_project.py

FILES TO MODIFY:
- clide/main_window.py: replace the "File Tree" placeholder with FileTreeWidget;
  replace the single EditorWidget in the center with a TabManager; wire menu
  actions (Open File, Open Project, New, Save, Save As, Close, Recent) to
  file_ops functions; add keyboard shortcuts
- clide/config/settings.py: add fields for last_project_path, recent_files list,
  open_tabs list (for session restore)

SPECIFICATIONS:

FileTreeWidget (QWidget containing a QTreeView):
- Uses QFileSystemModel rooted at the current project root
- Default filter hides hidden files; toggleable via View menu
- Double-click on a file emits file_requested_signal(path: str)
  MainWindow connects this to open the file in TabManager
- Right-click context menu: New File, New Directory, Rename, Delete, Reveal
  in File Manager (use xdg-open on Linux)
- Highlights the path of the currently active editor tab (via a slot that listens
  to TabManager's current_file_changed_signal)
- Shows project name at the top in amber

TabManager (QTabWidget subclass):
- Holds multiple EditorWidget instances, one per tab
- Close button on each tab
- Tab label: filename; prepended with '*' when modified
- current_file_changed_signal(path: str | None)
- file_modified_signal(path: str, modified: bool)
- Public API:
    open_file(path: str) -> None   # if already open, switches to that tab
    close_file(path: str) -> bool  # returns False if user cancelled save prompt
    close_current() -> bool
    save_current() -> bool
    save_current_as(path: str) -> bool
    current_editor() -> EditorWidget | None
    current_file_path() -> str | None
    modified_files() -> list[str]
- On close of a modified tab: prompt "Save / Discard / Cancel"
- Ctrl+Tab cycles tabs forward; Ctrl+Shift+Tab backward
- Tabs are reorderable by drag

file_ops.py:
- Pure functional module, not a class. Functions take TabManager and/or MainWindow
  as arguments.
- Functions:
    new_file(tab_mgr: TabManager) -> None
    open_file_dialog(parent, tab_mgr, start_dir: str) -> None
    open_file(tab_mgr: TabManager, path: str) -> None
    save_file(tab_mgr: TabManager) -> bool
    save_file_as(parent, tab_mgr) -> bool
    close_file(tab_mgr: TabManager) -> bool
    open_project_dialog(parent, main_window) -> None
    open_project(main_window, path: str) -> None
- File dialogs use QFileDialog
- All operations update settings (recent files, last project)

project.py:
- Project dataclass: root: Path, type: Literal["lein", "deps", "other"], name: str
- detect_project(path: Path) -> Project | None
  Walks upward from `path` looking for:
    project.clj -> type="lein"
    deps.edn -> type="deps"
    .git -> type="other"
  Returns the first match. Project name from project.clj if possible (read first
  form, look for the defproject name), else from directory name.
- is_clojure_file(path: Path) -> bool — returns True for .clj, .cljs, .cljc, .edn

TESTS (tests/test_project.py):
- Use tmp_path fixture
- Create a fake lein project (project.clj with a simple defproject form), verify
  detect_project returns type="lein" and correct name
- Create a fake deps project (deps.edn file), verify type="deps"
- Create a directory with just .git, verify type="other"
- Create a plain directory, verify None
- Start detection from a nested subdirectory, verify it walks up correctly

SESSION RESTORE:
On launch:
- Read last_project_path from settings
- If valid, open it (populates file tree)
- Read open_tabs list from settings
- For each, open the file and restore cursor position (line, column)
- Restore current_tab_index

On quit:
- Save open tabs list (paths + cursor positions)
- Save current_tab_index
- Save last project path

ACCEPTANCE TEST:
1. Launch CLIDE with no prior project
2. File > Open Project, select a Clojure project directory
3. File tree populates with project contents
4. Double-click a .clj file; it opens in a tab with syntax highlighting
5. Modify the file; asterisk appears in tab label
6. Ctrl+S saves; asterisk disappears
7. Open a second file; now two tabs
8. Ctrl+Tab switches between them
9. Close a modified tab; see save prompt
10. File > Recent Files shows opened files
11. Quit CLIDE with two tabs open
12. Relaunch; project and tabs restored with cursor positions
13. Run pytest tests/test_project.py; all pass

OUT OF SCOPE:
REPL, eval, Git, diff, rename refactoring.

OUTPUT FORMAT:
Plan first, then files in full, then testing checklist.
```

---

## AI Prompt — Phase 4: nREPL Protocol Client

```
[PASTE UNIVERSAL PREAMBLE ABOVE]

PHASE 4 — nREPL Protocol Client

CONTEXT:
Phases 1–3 produced a CLIDE with a styled main window, working editor with
Clojure syntax highlighting, file tree, multi-tab editing, and project detection.
No REPL functionality exists yet. This phase builds the network protocol layer
as a standalone library — no UI work in this phase.

OBJECTIVE:
Build a robust nREPL client that speaks bencode over TCP, handles async responses
via Qt signals, and exposes a clean API for the REPL UI to consume in Phase 5.

FILES TO CREATE:
- clide/nrepl/__init__.py
- clide/nrepl/bencode.py (~150 lines)
- clide/nrepl/messages.py (~150 lines)
- clide/nrepl/socket_worker.py (~180 lines)
- clide/nrepl/client.py (~250 lines)
- clide/nrepl/session.py (~180 lines)
- tests/test_bencode.py
- tests/test_messages.py
- scratch/nrepl_smoke_test.py (standalone test script)

SPECIFICATIONS:

bencode.py:
Bencode is the nREPL wire format. Four types:
- Integer:    i42e
- Byte string: 5:hello   (length-prefixed raw bytes)
- List:       l<items>e
- Dictionary: d<key-value pairs>e (keys sorted lexicographically)

Implement:
- encode(obj: Any) -> bytes
  Accepts: int, str (encoded as UTF-8 byte string), bytes, list, tuple, dict.
  Rejects other types with TypeError.
- decode(data: bytes) -> tuple[Any, bytes]
  Returns (parsed_value, remaining_bytes). Raises BencodeError on malformed input.
- decode_all(data: bytes) -> tuple[list[Any], bytes]
  Decodes as many complete values as possible, returns (values, leftover).
  Leftover can be buffered and retried when more bytes arrive.

Unit tests: round-trip for each type, nested structures, partial-read handling,
malformed input, empty strings, negative integers, large integers.

messages.py:
Message builders — pure functions returning dicts ready for bencode encoding.
Every message dict must include an "id" (random UUID hex, 8 chars is fine) and,
where applicable, a "session" key.
- new_id() -> str
- build_clone(session: str | None = None) -> dict
- build_close(session: str) -> dict
- build_describe() -> dict
- build_eval(code: str, session: str, ns: str | None = None, file: str | None = None,
             line: int | None = None, column: int | None = None) -> dict
- build_interrupt(session: str, interrupt_id: str) -> dict
- build_load_file(file_contents: str, file_name: str, file_path: str,
                  session: str) -> dict
- build_stdin(input: str, session: str) -> dict
- build_ls_sessions() -> dict

socket_worker.py:
SocketWorker (QThread subclass):
- __init__(host: str, port: int)
- Signals:
    message_received_signal(dict)
    connected_signal()
    disconnected_signal(str)  # reason
    error_signal(str)
- run():
    - Opens socket
    - Emits connected_signal
    - Read loop: accumulates bytes, calls bencode.decode_all, emits each message
    - On connection loss, emits disconnected_signal and exits
    - Catches all exceptions, emits error_signal, exits
- send_bytes(data: bytes) via a thread-safe queue (NOT direct socket.send from
  other threads — use a Queue and send in the read loop's idle periods, or
  use a separate sending thread. Simplest: use socket.sendall with a lock.)
- stop() method to request graceful shutdown

client.py:
NreplClient (QObject):
- Signals:
    response_signal(msg_id: str, response: dict)
    connection_state_signal(state: str)  # "connecting" | "connected" | "disconnected" | "error"
    session_cloned_signal(session_id: str)
- Methods:
    connect(host: str, port: int) -> None
    disconnect() -> None
    send(message: dict) -> str  # returns the message id
    is_connected() -> bool
    default_session() -> str | None
- On connection:
    1. Start SocketWorker
    2. On connected_signal, immediately send a clone message
    3. When response to clone arrives with new-session, store it as default_session
    4. Emit session_cloned_signal
    5. Emit connection_state_signal("connected")
- Routes incoming messages: extracts "id" and emits response_signal
- Tracks pending message ids in a dict (id -> metadata), cleared when "done" status
  is received for that id
- Thread-safe send (the SocketWorker owns the socket; sends go through a queue
  monitored by the worker)

session.py:
Session dataclass:
- session_id: str
- current_ns: str = "user"
- pending_evals: dict[str, dict]  # msg_id -> eval metadata

SessionManager:
- track_session(session_id: str)
- get_current_ns(session_id) -> str
- update_ns_from_response(session_id, response)  # watches for :ns in responses
- track_eval(session_id, msg_id, code, source_location)
- complete_eval(session_id, msg_id)
- Keeps a history of completed evals (capped at 1000)

SMOKE TEST SCRIPT (scratch/nrepl_smoke_test.py):
A standalone script using PyQt6's QApplication + NreplClient with no main window.
- Takes a host/port argument
- Connects, prints all received messages to stdout
- Sends a sequence of test evals:
    (+ 1 2)
    (println "hello from clide")
    (/ 1 0)       # exception
    (Thread/sleep 5000)   # long-running, then interrupt it
- Prints results as they arrive
- Exits cleanly after 10 seconds

Running the smoke test:
1. In another terminal: cd to any Clojure project and run `clj -M:nrepl` or
   `lein repl :headless`
2. Note the port
3. python scratch/nrepl_smoke_test.py 127.0.0.1 <port>
4. Observe output

UNIT TESTS:
- test_bencode.py: comprehensive coverage per the bencode.py spec
- test_messages.py: every message builder produces expected structure with valid id

ACCEPTANCE TEST:
1. pytest tests/test_bencode.py — all green
2. pytest tests/test_messages.py — all green
3. Start an nREPL server externally
4. Run scratch/nrepl_smoke_test.py — observe successful eval responses, exception
   handling, and interrupt handling
5. Verify clean disconnect (no traceback on script exit)

OUT OF SCOPE:
No UI changes. This phase produces a tested library. Phase 5 builds the UI
that uses it.

OUTPUT FORMAT:
Plan first, then files in full, then testing checklist.
```

---

## AI Prompt — Phase 5: REPL Pane & Evaluation

```
[PASTE UNIVERSAL PREAMBLE ABOVE]

PHASE 5 — REPL Pane & Evaluation

CONTEXT:
Phases 1–4 produced:
- A styled CLIDE main window with editor, file tree, tabs, project detection
- A fully tested nREPL client library in clide/nrepl/ with bencode, message
  builders, socket worker, NreplClient, and SessionManager
- A working smoke test that proves the client can connect, eval, handle
  exceptions, and interrupt

OBJECTIVE:
Build the REPL UI and wire it to the nREPL client. Enable evaluating forms
from the editor (cursor form, selection, whole file) and seeing results,
stdout, and stderr in the REPL pane.

FILES TO CREATE:
- clide/repl/__init__.py
- clide/repl/repl_pane.py (~280 lines)
- clide/repl/output_view.py (~200 lines)
- clide/repl/input_line.py (~180 lines)
- clide/ui/connect_dialog.py (~100 lines) — manual host/port dialog

FILES TO MODIFY:
- clide/main_window.py:
    - replace the "REPL" placeholder with ReplPane
    - instantiate NreplClient and SessionManager, hold as attributes
    - wire menu items and shortcuts:
        Ctrl+Enter          -> eval form at cursor
        Ctrl+Shift+Enter    -> eval selection
        Ctrl+Alt+Enter      -> eval whole file
        REPL > Connect External -> opens connect dialog
        REPL > Disconnect       -> disconnects
    - add MainWindow methods: eval_form_at_cursor, eval_selection, eval_current_file
    - update status bar REPL indicator based on connection_state_signal

SPECIFICATIONS:

OutputView (QTextEdit read-only):
- Styled text output of interleaved messages
- Categories, each styled distinctly per theme:
    command (amber bright): echoes the code being evaluated, prefixed with "=> "
    value (foreground): the return value
    stdout (foreground dim)
    stderr (error red)
    exception (error red, bold)
    info (blue primary): system messages like "Connected to nrepl://..."
- Public API:
    append_command(code: str, ns: str)
    append_value(value: str, ns: str)
    append_stdout(text: str)
    append_stderr(text: str)
    append_exception(ex_class: str, message: str, trace: str)
    append_info(text: str)
    clear()
- Scroll-to-bottom on new output unless the user has scrolled up
- Configurable max lines (from settings, default 5000); older lines dropped

InputLine (QPlainTextEdit subclass, single-line by default, expandable on Shift+Enter):
- Enter submits; emits submit_signal(code: str)
- Shift+Enter inserts newline, grows the widget vertically
- Up/Down when the cursor is on the first/last line cycles through eval history
- Eval history kept in memory (list), capped at 500 entries
- ClojureHighlighter applied for input styling consistency
- Paren matching active

ReplPane (QWidget):
Layout (vertical):
  - Small status strip (horizontal): connection indicator LED, "ns: <current>",
    "session: <short id>", Clear button
  - OutputView (stretch)
  - InputLine (fixed height, expandable)
- Holds a reference to NreplClient and SessionManager (passed in __init__)
- Listens to NreplClient signals:
    connection_state_signal -> updates status strip + status bar
    response_signal         -> routes to output view by response content
- Listens to InputLine submit_signal -> sends eval via client
- Public methods:
    eval(code: str, ns: str | None = None, file: str | None = None,
         line: int | None = None, column: int | None = None) -> None
    connect_to(host: str, port: int) -> None
    disconnect() -> None
- Response routing: an nREPL response dict can contain any of:
    "value"     -> append_value
    "out"       -> append_stdout
    "err"       -> append_stderr
    "ex"        -> append_exception (use ex_class + message; trace if provided)
    "ns"        -> update session's current ns, update status strip
    "status"    -> list of status flags; "done" means completion; "interrupted"
                   means we interrupted; "eval-error" prompts stacktrace request
    "root-ex"   -> sometimes present for exceptions

Evaluation flow (from MainWindow methods):
- eval_form_at_cursor:
    1. Get active editor
    2. Use form_detector.form_at to find form bounds
    3. If None, beep and show "No form at cursor" in status bar
    4. Extract form text
    5. Determine current file ns from the (ns ...) declaration at top of file,
       or default to "user"
    6. Call repl_pane.eval(form_text, ns=detected_ns, file=path, line=line, column=col)
    7. repl_pane echoes the command to OutputView
- eval_selection: similar but uses the selected text directly
- eval_current_file: reads full file text, sends as load-file op

File-namespace detection helper (add to clide/editor/form_detector.py or a new
clide/namespace/ns_detector.py):
- detect_file_namespace(text: str) -> str | None
  Finds the first (ns ...) form at the top of the file and extracts the name.

ConnectDialog (modal QDialog):
- Two fields: host (default 127.0.0.1), port (numeric)
- Connect and Cancel buttons
- Remembers last-used host/port in settings

ACCEPTANCE TEST:
Prerequisite: start an nREPL server externally (`clj -M:nrepl`)

1. Launch CLIDE
2. REPL > Connect External, enter 127.0.0.1 and the port
3. Status bar shows "Connected to :port | ns: user"
4. REPL pane status strip shows green LED, "ns: user"
5. Type (+ 1 2) in the REPL input line, press Enter
6. See "=> (+ 1 2)" echoed, then "3" as value
7. Type (println "hi") — see "hi" as stdout, "nil" as value (in distinct colors)
8. Type (/ 1 0) — see exception formatted in red
9. Up arrow recalls previous expressions
10. Open a .clj file in the editor, place cursor inside a defn, press Ctrl+Enter
11. See the defn echoed in REPL, result #'user/foo shown
12. Select an expression in the editor, press Ctrl+Shift+Enter — see it evaluated
13. Change the file's ns declaration, press Ctrl+Alt+Enter to load-file — see it
    loaded and namespace updated
14. REPL > Disconnect — see status update cleanly

OUT OF SCOPE:
REPL process spawning (Phase 6). No autocomplete or goto-def.

OUTPUT FORMAT:
Plan first, then files in full, then testing checklist.
```

---

## AI Prompt — Phase 6: REPL Process Management

```
[PASTE UNIVERSAL PREAMBLE ABOVE]

PHASE 6 — REPL Process Management

CONTEXT:
Phases 1–5 produced a CLIDE that can connect to an externally-running nREPL
server and evaluate forms from the editor. The user must currently start the
nREPL manually in a separate terminal.

OBJECTIVE:
Automate REPL startup. CLIDE spawns an nREPL process for the current project,
parses its port, and auto-connects. Add Start/Stop/Restart REPL controls.

FILES TO CREATE:
- clide/repl/process_manager.py (~220 lines)
- clide/repl/port_detector.py (~100 lines)
- tests/test_port_detector.py

FILES TO MODIFY:
- clide/main_window.py:
    - instantiate ReplProcessManager
    - wire REPL > Start / Stop / Restart menu items and toolbar buttons
    - chain: Start REPL -> spawn process -> detect port -> auto-connect client
    - handle process crashes gracefully
- clide/ui/toolbar.py: add Start / Stop / Restart buttons with icons and
  enable-state logic
- clide/config/settings.py: add fields for lein_command and clj_command
  (defaults: "lein repl :headless" and "clj -M:nrepl")

SPECIFICATIONS:

port_detector.py:
- Pure functions
- detect_port_in_line(line: str) -> int | None
  Regexes to match the port line variants:
    "nREPL server started on port 56789 on host 127.0.0.1"
    "Started nREPL server at :56789"
    Also handles just "nREPL server started on port 56789"
- A running buffer helper: feed chunks of output, get port when detected:
  PortDetector class with:
    feed(chunk: str) -> int | None
    reset()

ReplProcessManager (QObject wrapping QProcess):
- __init__ takes no args
- Signals:
    process_state_signal(state: str)
    # states: "idle" | "starting" | "running" | "crashed" | "stopping" | "stopped"
    port_detected_signal(port: int)
    output_line_signal(line: str, stream: str)  # stream = "stdout" | "stderr"
    error_signal(message: str)
- Methods:
    start(project: Project, settings: Settings) -> None
    stop(timeout_ms: int = 3000) -> None
    restart(project: Project, settings: Settings) -> None
    is_running() -> bool
    current_port() -> int | None
    current_project() -> Project | None
- Command selection:
    project.type == "lein" -> split settings.lein_command + working dir = project.root
    project.type == "deps" -> split settings.clj_command + working dir = project.root
    project.type == "other" -> error: "Cannot start REPL for non-Clojure project"
- Stream handling: buffer stdout/stderr lines; emit output_line_signal for each
  complete line; feed to PortDetector until port found; emit port_detected_signal
  once
- Crash detection: QProcess::finished with nonzero exit code or unexpected exit
  while running -> emit process_state_signal("crashed"), error_signal with details
- Shutdown: send SIGTERM (QProcess::terminate); wait for timeout_ms; then
  SIGKILL (QProcess::kill); emit "stopped"
- Graceful app quit: MainWindow connects closeEvent to ReplProcessManager.stop

MainWindow orchestration:
- A single method start_repl():
    1. If no current project, show error
    2. If process already running, warn and return (or call restart)
    3. repl_pane.output_view.append_info(f"Starting REPL in {project.root}...")
    4. process_manager.start(project, settings)
    5. Connect port_detected_signal to auto_connect_after_startup
    6. Connect output_line_signal to repl_pane.output_view.append_info for
       dim visibility of startup logs
- auto_connect_after_startup(port):
    1. repl_pane.output_view.append_info(f"nREPL on port {port}, connecting...")
    2. nrepl_client.connect("127.0.0.1", port)
- stop_repl():
    1. nrepl_client.disconnect()
    2. process_manager.stop()
- restart_repl(): stop then start; ordered properly with signals

Toolbar state logic:
- Start REPL enabled when: project open AND not running
- Stop REPL enabled when: running
- Restart REPL enabled when: running
- These update when process_state_signal or project changes

Status bar REPL indicator (update the existing section):
- No project: gray dash "—"
- Project open, not running: "stopped"
- Starting: "starting..."
- Running + connected: "running :<port> | ns: <current>"
- Crashed: "crashed" in red

TESTS (test_port_detector.py):
- Each known port line format parses correctly
- Unrelated output returns None
- PortDetector buffer handles lines split across chunks
- PortDetector ignores lines after port is detected

ACCEPTANCE TEST:
1. Launch CLIDE, open a Leiningen project
2. Click Start REPL (or REPL menu)
3. See startup messages streaming into REPL pane in dim color
4. See status go "starting" -> "running :<port>" within reasonable time
5. Evaluate (+ 1 2) — works
6. Click Stop REPL — clean shutdown, status -> "stopped"
7. Click Start REPL again — starts fresh
8. Click Restart REPL — stops then starts; eval works after
9. Open a deps.edn project — Start REPL uses clj command, works
10. While REPL running, kill the underlying process externally (kill -9)
11. See CLIDE detect the crash; status updates; no UI crash
12. Close CLIDE while REPL is running; verify no orphaned process

OUT OF SCOPE:
- Multiple simultaneous REPLs per project
- ClojureScript REPL
- Remote REPL over SSH

OUTPUT FORMAT:
Plan first, then files in full, then testing checklist.
```

---

## AI Prompt — Phase 7: Structural Awareness & Namespace Tools

```
[PASTE UNIVERSAL PREAMBLE ABOVE]

PHASE 7 — Structural Awareness & Namespace Tools

CONTEXT:
Phases 1–6 produced a CLIDE that can open projects, spawn or connect to nREPLs,
evaluate forms from the editor, and display results. It works as a minimal IDE
but lacks the quality-of-life features that make Clojure pleasant.

OBJECTIVE:
Add the Clojure-specific ergonomics: paren balance checking, rainbow parens,
basic structural editing (slurp/barf/wrap/unwrap), a namespace browser, and
namespace operations (reload, switch).

FILES TO CREATE:
- clide/editor/balance_checker.py (~150 lines)
- clide/editor/rainbow_parens.py (~130 lines)
- clide/editor/structural_edit.py (~220 lines)
- clide/namespace/__init__.py
- clide/namespace/ns_browser.py (~180 lines)
- clide/namespace/ns_operations.py (~150 lines)
- clide/ui/fuzzy_ns_dialog.py (~120 lines)

FILES TO MODIFY:
- clide/editor/editor_widget.py:
    - add keybindings for structural edits:
        Alt+Shift+Right  -> slurp forward
        Alt+Shift+Left   -> barf forward
        Alt+W then (, [, { -> wrap selection (or current form) with that bracket
        Alt+U            -> unwrap (splice current form's contents into parent)
    - wire balance checker to run on a debounced document-changed signal
    - wire rainbow parens toggle from settings
- clide/main_window.py:
    - replace "Namespaces" placeholder with NsBrowser
    - wire namespace operation menu items:
        REPL > Reload Current NS         (Ctrl+R)
        REPL > Switch to File NS         (Ctrl+Shift+R)
        REPL > Reload All Changed NS     (Ctrl+Shift+F5)
        File > Go to Namespace...        (Ctrl+Shift+N)
- clide/config/settings.py: add rainbow_parens: bool field

SPECIFICATIONS:

balance_checker.py:
- Pure functions
- check_balance(text: str) -> list[BalanceError]
  BalanceError: {pos: int, kind: "unmatched_open" | "unmatched_close" | "mismatch",
                 char: str}
- Walks the text, respects strings and comments, collects errors
- EditorWidget uses this in a debounced (500ms) slot:
    - Clears previous balance underlines
    - Adds red wavy underline (QTextCharFormat) at each error position

rainbow_parens.py:
- Color cycle: list of colors derived from theme (theme.py should gain a
  rainbow_cycle property returning ~7 colors)
- Function: apply_rainbow(document: QTextDocument, enabled: bool)
  Integrates with ClojureHighlighter: if enabled, brackets are colored by depth
  instead of the usual bracket color
- Implemented as an extension to ClojureHighlighter rather than a separate
  highlighter (avoids highlighter stacking issues). ClojureHighlighter gains a
  set_rainbow(enabled) method that toggles this behavior.

structural_edit.py:
- Pure functions on (text, cursor_pos) -> (new_text, new_cursor_pos) | None
- slurp_forward(text, pos): extends current form to swallow the next sibling form
- barf_forward(text, pos): ejects the last child of current form to its parent
- wrap_form(text, pos, open_char, close_char): wraps current form or selection
- unwrap_form(text, pos): replaces current form with its contents
- These rely on form_detector from Phase 2
- When the operation is impossible (malformed code, no form), return None;
  caller beeps and shows status message

EditorWidget integration:
- New methods: slurp_forward(), barf_forward(), wrap_form(char), unwrap_form()
- Each: gets current text + cursor, calls the structural_edit function, applies
  result via a single QTextCursor transaction (for undo integration)

NsBrowser (QWidget containing a QListWidget):
- Shows loaded namespaces in the connected REPL
- Refresh triggers:
    - Manual refresh button
    - After successful load-file eval
    - On demand via a signal from MainWindow
- Refresh mechanism:
    - Send eval (map str (map ns-name (all-ns)))
    - Parse response, populate list
- Sorted, with current namespace marked (amber)
- Double-click: switches REPL to that ns (sends "(in-ns 'foo)")
- Right-click menu: Switch To, Reload, Remove (ns-remove)
- Filter box at top for quick filtering

ns_operations.py:
- Functions that take NreplClient and return None (operations are fire-and-forget
  with results routed through the output view):
    reload_ns(client, ns_name)      # sends (require 'ns :reload)
    reload_all_changed(client)      # sends (clojure.tools.namespace.repl/refresh)
                                    # fallback: reload_ns on current
    switch_ns(client, ns_name)      # sends (in-ns 'ns)
    remove_ns(client, ns_name)      # sends (remove-ns 'ns)
    list_all_ns(client) -> None     # sends the query; result routed to NsBrowser
      (NsBrowser subscribes to NreplClient.response_signal and picks up its
       own message id)

FuzzyNsDialog:
- Modal dialog invoked by Ctrl+Shift+N
- Requests the current ns list from NsBrowser (cached)
- QLineEdit at top; QListWidget below with fuzzy-matched results
- Fuzzy match: subsequence match with score (count of consecutive matches)
- Enter switches to selected ns; Esc cancels

ACCEPTANCE TEST:
1. Launch CLIDE, open a project, start REPL
2. Type intentionally unbalanced code in the editor; see red underline on error
   position within ~500ms
3. Fix the imbalance; underline clears
4. View > Rainbow Parens toggles; effect is immediate
5. Place cursor inside (foo (bar) baz); Alt+Shift+Right slurps the form after
   it into the outer form: (foo (bar) baz <next>)
6. Alt+Shift+Left barfs the last child out
7. Select a form and Alt+W then ( wraps it in parens
8. Alt+U on a form replaces it with its contents
9. Namespace browser populates after REPL connect
10. After evaluating (require 'clojure.string), the browser refreshes to include it
11. Double-clicking a ns switches REPL to it; status bar updates
12. Ctrl+R on the current file's editor: reloads its namespace, sees the output
13. Ctrl+Shift+N: fuzzy-match dialog appears; typing "str" selects clojure.string
    quickly; Enter switches
14. Run pytest (if tests added); all pass

OUT OF SCOPE:
Full paredit (splice-killing-forward, raise-sexp, etc.), autocomplete,
goto-definition, hover documentation.

OUTPUT FORMAT:
Plan first, then files in full, then testing checklist.
```

---

## AI Prompt — Phase 8: Polish, Preferences & Packaging

```
[PASTE UNIVERSAL PREAMBLE ABOVE]

PHASE 8 — Polish, Preferences & Packaging

CONTEXT:
Phases 1–7 produced a fully functional Clojure IDE:
- Styled main window, four-panel layout
- Editor with syntax highlighting, paren matching, balance checking,
  rainbow parens, basic structural editing
- File tree, multi-tab editing, project detection, session restore
- nREPL client with process spawning, auto-connect
- REPL pane with inline eval of forms, selections, whole files
- Namespace browser, reload, switch, fuzzy ns picker

OBJECTIVE:
Convert the working IDE into a polished, distributable v1.0 release.

FILES TO CREATE:
- clide/ui/preferences_dialog.py (~250 lines)
- clide/ui/about_dialog.py (~100 lines)
- clide/ui/shortcuts_dialog.py (~120 lines)
- clide/ui/icons.py (~80 lines)
- clide/resources/icons/*.svg (a curated set)
- clide/resources/themes/default.json (finalized)
- build/clide.spec (PyInstaller spec)
- build/build_linux.sh (build script)
- docs/README.md (comprehensive)
- docs/KEYBOARD_SHORTCUTS.md
- CHANGELOG.md

FILES TO MODIFY:
- clide/main_window.py: wire Preferences, About, Shortcuts menu items;
  apply preference changes live where possible
- clide/config/settings.py: document and organize settings sections
- clide/app.py: add splash screen
- pyproject.toml: finalize metadata, version, entry points

SPECIFICATIONS:

PreferencesDialog (QDialog with QTabWidget):
Tabs and fields:
  EDITOR
    - Font family (QFontComboBox, monospace-filtered)
    - Font size (QSpinBox)
    - Tab width (QSpinBox)
    - Show line numbers (QCheckBox)
    - Highlight current line (QCheckBox)
    - Rainbow parens (QCheckBox)
    - Match brackets (QCheckBox)
    - Balance check debounce ms (QSpinBox)
  THEME
    - Color overrides for each palette slot (QPushButton opening QColorDialog)
    - Reset to defaults button
    - Live preview area
  REPL
    - Leiningen command (QLineEdit)
    - Clojure CLI command (QLineEdit)
    - Default connect host (QLineEdit)
    - Default connect port (QSpinBox)
    - Max output lines (QSpinBox)
    - History size (QSpinBox)
  KEYBOARD
    - Read-only tree of commands with their bindings
    - (Editing shortcuts is post-v1)
  PATHS
    - Config directory (display only, with "Open" button)
    - Log file (display only, with "Open" button)

OK/Cancel/Apply buttons. Apply writes settings and emits a setting_changed_signal
that MainWindow and editors listen to for live updates.

AboutDialog:
- App name "CLIDE" in amber, large
- Tagline: "A Clojure IDE by Fragillidae Software"
- Version
- Built with PyQt6, Python X.Y.Z
- License: MIT
- Copyright line
- Link to GitHub

ShortcutsDialog:
- Scrollable, categorized list of all keyboard shortcuts:
    Editor: Ctrl+S, Ctrl+Z, Ctrl+Y, Tab, Shift+Tab, structural edits
    File: Ctrl+N, Ctrl+O, Ctrl+W, Ctrl+Shift+W, Ctrl+Tab
    REPL: Ctrl+Enter, Ctrl+Shift+Enter, Ctrl+Alt+Enter, Ctrl+R, Ctrl+Shift+R
    Namespace: Ctrl+Shift+N
    View: F11, View toggles
- Each row: action description + shortcut

icons.py:
- ICON_DIR constant pointing to resources/icons
- load_icon(name: str, size: int = 16) -> QIcon
- Cached so we don't re-read SVG files
- All toolbar and menu icons routed through this

Icons to ship (in resources/icons/, SVG preferred):
  app.svg              (CLIDE lambda/paren mark, amber on dark)
  file-new.svg, file-open.svg, file-save.svg, folder-open.svg
  repl-start.svg, repl-stop.svg, repl-restart.svg, repl-connect.svg
  eval-form.svg, eval-selection.svg, eval-file.svg
  reload-ns.svg, switch-ns.svg
  preferences.svg, help.svg
All in the Fragillidae amber/blue/dark palette, consistent stroke weight,
pixel-perfect at 16px and 24px sizes.

Splash screen:
- QSplashScreen with CLIDE logo
- Shown during QApplication startup before main window
- Hides on main window show event
- Fast (<1s), just a loading indicator

Logging review:
- Log level selectable in settings (default INFO)
- Rotation: 5 files, 5MB each
- Startup log entry includes: version, Python version, PyQt version, platform

README:
- Logo/screenshot
- What it is (one paragraph)
- Why (the "unified workspace" motivation)
- Installation (venv + pip install)
- Quickstart (open project, start REPL, eval)
- Keyboard shortcuts (or link to KEYBOARD_SHORTCUTS.md)
- Configuration
- Building from source (PyInstaller)
- Contributing (simple: issues welcome, PRs by coordination)
- License

Packaging (build/ directory):
- clide.spec: PyInstaller spec, onefile binary, includes resources/
- build_linux.sh: script that sets up venv, installs deps, runs pyinstaller,
  puts output in dist/clide
- Optionally an AppImage wrapper (not required for v1.0)
- Test: build on LMDE 7, copy the binary to a fresh VM/user, verify it runs

Version tagging:
- pyproject.toml: version = "1.0.0"
- __init__.py: __version__ = "1.0.0"
- Git tag: v1.0.0

ACCEPTANCE TEST:
1. Launch CLIDE; splash screen shows briefly, then main window
2. Edit > Preferences opens dialog with all tabs populated
3. Change font size; click Apply; see editors update immediately
4. Change a theme color; see preview; click OK; see full UI reflect it
5. Help > About shows dialog with correct version
6. Help > Shortcuts shows categorized list
7. Toolbar icons render crisply, consistent palette
8. All keyboard shortcuts from the reference work
9. Log file at the configured path has rotation
10. Run build/build_linux.sh; dist/clide executable appears
11. Copy dist/clide to another user's home dir on the same machine; it runs
12. README is sufficient to get a new developer from clone to running
13. git tag v1.0.0 applied

OUT OF SCOPE FOR v1.0:
- macOS / Windows packaging
- AppImage build (if not done)
- Auto-updater
- Plugin system
- Localization

These can go in a post-v1.0 roadmap section of the README.

OUTPUT FORMAT:
Plan first, then files in full, then testing checklist. For the SVG icons,
produce them as SVG source code (these are small).
```

---

## Appendix A — nREPL Protocol Reference

### A.1 Wire Format

nREPL messages are bencode-encoded dictionaries exchanged over TCP. Each message has an `id` so responses can be matched to requests. Most messages have a `session` field identifying the logical session.

### A.2 Standard Operations

| op | description | key request fields | key response fields |
|----|-------------|-------------------|---------------------|
| `clone` | Create a new session | `session` (optional, to fork) | `new-session` |
| `close` | Close a session | `session` | `status: ["done", "session-closed"]` |
| `describe` | Query server capabilities | — | `ops`, `versions` |
| `eval` | Evaluate code | `code`, `session`, `ns`, `file`, `line`, `column` | `value`, `out`, `err`, `ns`, `ex`, `root-ex`, `status` |
| `load-file` | Load file contents | `file`, `file-name`, `file-path`, `session` | same as eval |
| `interrupt` | Interrupt running eval | `session`, `interrupt-id` | `status` |
| `stdin` | Provide stdin | `stdin`, `session` | `status` |
| `ls-sessions` | List active sessions | — | `sessions` |

### A.3 Response Status Flags

Responses may include a `status` field (a list of strings):
- `done` — end of responses for this id
- `interrupted` — eval was interrupted
- `eval-error` — exception occurred; use `stacktrace` op to get details
- `namespace-not-found` — `ns` field was invalid
- `need-input` — stdin required

### A.4 Typical Eval Message Sequence

```
Client -> Server: {id: "1", op: "eval", code: "(+ 1 2)", session: "abc"}
Server -> Client: {id: "1", session: "abc", ns: "user", value: "3"}
Server -> Client: {id: "1", session: "abc", status: ["done"]}
```

### A.5 Exception Handling

```
Client -> Server: {id: "2", op: "eval", code: "(/ 1 0)", session: "abc"}
Server -> Client: {id: "2", session: "abc", err: "Execution error...\n"}
Server -> Client: {id: "2", session: "abc", ex: "class java.lang.ArithmeticException",
                   root-ex: "class java.lang.ArithmeticException"}
Server -> Client: {id: "2", session: "abc", status: ["eval-error", "done"]}
```

---

## Appendix B — Keyboard Shortcut Map

### File Operations
- `Ctrl+N` — New file
- `Ctrl+O` — Open file
- `Ctrl+Shift+O` — Open project
- `Ctrl+S` — Save
- `Ctrl+Shift+S` — Save as
- `Ctrl+W` — Close tab
- `Ctrl+Q` — Quit

### Editing
- `Ctrl+Z` / `Ctrl+Y` — Undo / Redo
- `Ctrl+X` / `Ctrl+C` / `Ctrl+V` — Cut / Copy / Paste
- `Ctrl+A` — Select all
- `Ctrl+F` — Find
- `Tab` / `Shift+Tab` — Indent / Outdent

### Structural Editing
- `Alt+Shift+Right` — Slurp forward
- `Alt+Shift+Left` — Barf forward
- `Alt+W` then `(`, `[`, `{` — Wrap with brackets
- `Alt+U` — Unwrap

### Navigation
- `Ctrl+Tab` / `Ctrl+Shift+Tab` — Cycle tabs
- `Ctrl+Shift+N` — Go to namespace (fuzzy)

### REPL
- `Ctrl+Enter` — Evaluate form at cursor
- `Ctrl+Shift+Enter` — Evaluate selection
- `Ctrl+Alt+Enter` — Evaluate whole file
- `Ctrl+R` — Reload current namespace
- `Ctrl+Shift+R` — Switch REPL to file namespace
- `Ctrl+Shift+F5` — Reload all changed namespaces

### View
- `F11` — Full screen
- `Ctrl+,` — Preferences

### Help
- `F1` — Keyboard shortcuts
- `Shift+F1` — About

---

## Development Order and Milestones

| Phase | Est. LOC | Dependencies | Milestone |
|-------|----------|--------------|-----------|
| 1 | ~900 | — | App launches with shell |
| 2 | ~900 | 1 | Editor with Clojure highlighting |
| 3 | ~750 | 1, 2 | Can open and save Clojure files |
| 4 | ~900 | — (parallel to 2–3 possible) | nREPL library tested |
| 5 | ~760 | 4 + (2, 3) | Can eval from editor |
| 6 | ~320 | 5 | Auto-start REPL in project |
| 7 | ~950 | 6 | Quality-of-life features |
| 8 | ~600 | 7 | Packaged v1.0 release |

**Total:** ~6,000 LOC of Python across roughly 35 modules. A realistic effort of several focused development weekends per phase for someone with your IDE-building experience.

---

## Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| nREPL partial-read bugs | Medium | Comprehensive bencode tests; streaming decoder from day one |
| QThread/socket race conditions | Medium | Single-writer discipline on socket; signal-based communication only |
| Long-running evals freeze UI | Low (by design) | All blocking I/O in worker thread |
| Balance checker performance on large files | Low | Debounced; consider incremental checking if needed |
| QProcess output buffering delays port detection | Medium | Force unbuffered stdout on spawned processes |
| Session restore conflicts with new projects | Low | Validate paths on restore; gracefully drop missing files |
| PyInstaller binary too large | Low | Acceptable for v1.0; can optimize post-release |

---

## Post-v1.0 Roadmap (non-binding)

- Autocomplete via `nrepl/complete` or `cider-nrepl` middleware
- Goto-definition (via `cider-nrepl`)
- Inline doc lookup (hover)
- Test runner integration (clojure.test)
- ClojureScript support (shadow-cljs REPL)
- Git integration (status in file tree, diff viewer)
- Full paredit
- Plugin API
- macOS and Windows builds
- Dark/light theme switch

---

*End of CLIDE Implementation Plan v1.0*
