# CLJDE Operators Guide

A practical reference for using CLJDE — the Clojure-focused integrated
development environment built on Python 3.11+ and PyQt6. This guide
covers installation, day-to-day workflow, every menu and key binding,
and troubleshooting for the features delivered through Phase 7.

---

## 1. Overview

CLJDE organises its main window into four zones:

| Zone          | Contents                                           |
|---------------|----------------------------------------------------|
| Left dock     | File tree rooted at the current project            |
| Centre        | Tabbed Clojure editors                             |
| Right dock    | Namespace browser (filter + current-ns highlight)  |
| Bottom dock   | REPL pane (output view + input line)               |

A persistent status bar along the bottom reports the active file, cursor
position, REPL connection state, and transient notices. Docks can be
moved, tabbed, floated, or hidden — their layout is saved between runs.

Every file in the Python package obeys a **400-line hard ceiling** to
keep modules easy to reason about. Signals end in `_signal`; palette
colours come from `cljde.config.theme.DEFAULT_PALETTE`.

---

## 2. Installation

### Prerequisites

- Python 3.11 or newer
- A JVM with `clojure` on `PATH` (or a project `deps.edn` / `project.clj`
  that can spawn one)
- Linux, macOS, or Windows with a working Qt 6 runtime

### Install from source

```bash
git clone <your-fork-url> cljde
cd cljde
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

The `-e` install exposes the `cljde` console script:

```bash
cljde               # launches the IDE
cljde path/to/file  # opens a file on startup
```

### Configuration directory

Settings, window geometry, and session state live in
`~/.config/cljde/` on Linux (respecting `$XDG_CONFIG_HOME`). The
logger writes to `~/.config/cljde/cljde.log`. Delete this directory
to reset CLJDE to defaults.

---

## 3. Projects and Files

### Opening a project

**File → Open Project…** (`Ctrl+Shift+O`) prompts for a directory and
roots the file tree there. CLJDE remembers the most-recent project and
restores it on next launch. The file tree honours the project's
`.gitignore`; toggle **View → Show Hidden Files** to surface dotfiles
and ignored paths.

### Working with tabs

- **File → New** (`Ctrl+N`) — untitled buffer.
- **File → Open File…** (`Ctrl+O`) — open one or more files in tabs.
- **File → Save / Save As** (`Ctrl+S` / `Ctrl+Shift+S`).
- **File → Recent Files** — dynamically populated from history.
- Middle-click (or the tab's ✕) closes a tab; unsaved changes prompt.

The session (list of open files, cursor positions, active tab) is
restored on next launch unless you explicitly close each tab before
quitting.

### Go to Namespace…

**File → Go to Namespace…** (`Ctrl+Shift+N`) opens a fuzzy picker over
every Clojure file under the project root plus every namespace loaded
into the REPL. Selecting an entry opens the file (if one exists) and
switches the REPL to that namespace.

---

## 4. The Editor

CLJDE's editor is a subclass of `QPlainTextEdit` specialised for
Clojure. It provides:

- Syntax highlighting (forms, keywords, strings, comments, numbers).
- Paren matching — the bracket under the cursor and its mate are
  boxed in amber; unmatched brackets are underlined in red.
- Paren balance check — a debounced background check annotates the
  status bar with the first unbalanced line, if any.
- Rainbow parens — depth-coloured bracket pairs, toggled via
  **View → Rainbow Parens** and persisted to settings.
- Line numbers gutter in the editor margin.
- Structural editing commands (see § 6 below).

### Common edit commands

| Shortcut            | Action                        |
|---------------------|-------------------------------|
| `Ctrl+Z`            | Undo                          |
| `Ctrl+Shift+Z`      | Redo                          |
| `Ctrl+X` / `C` / `V`| Cut / Copy / Paste            |
| `Ctrl+F`            | Find in buffer                |
| `Tab` / `Shift+Tab` | Indent / outdent              |

All edit shortcuts are active when the editor has focus.

---

## 5. The REPL

CLJDE embeds an nREPL client. The REPL dock has two parts: an
output view that streams stdout, stderr, `:value`, and `:ex` messages
with colour coding, and an input line that supports history
(`Up`/`Down`) and multi-line entry (`Shift+Enter`).

### Starting and connecting

- **REPL → Start** — spawns an nREPL for the current project, auto-detects
  the listening port from the process output, and connects. The exact
  command comes from settings: `clj -M:nrepl` for deps.edn projects and
  `lein repl :headless …` for Leiningen projects.
- **REPL → Connect External…** — opens a dialog to connect to an
  already-running nREPL on a given host/port.
- **REPL → Disconnect** / **REPL → Stop** / **REPL → Restart** — manage
  the current connection or supervised process.

The status bar shows `REPL: connected (ns)` or `REPL: disconnected`,
colour-coded green/amber.

Note that the default deps.edn command (`clj -M:nrepl`) relies on the
**target project** defining an `:nrepl` alias that launches an nREPL
server; a bare `deps.edn` will not. The Leiningen path needs no alias.

### Bundled test projects

The repository ships two ready-to-use projects under `projects/` for
exercising the REPL end-to-end:

- `projects/deps-scratch/` — a deps.edn project with a working `:nrepl`
  alias (nREPL + Clojure pinned), namespace `scratch.core`.
- `projects/lein-scratch/` — a minimal Leiningen project, namespace
  `lein-scratch.core`.

Open either with **File → Open Project…**, open its `core.clj`, choose
**REPL → Start**, then put the cursor inside a form in the trailing
`(comment …)` block and press `Ctrl+Enter`. The first start downloads
dependencies; subsequent starts are fast.

### Evaluating code

| Shortcut            | Action                                   |
|---------------------|------------------------------------------|
| `Ctrl+Enter`        | Eval the top-level form at the cursor    |
| `Ctrl+Shift+Enter`  | Eval the current selection               |
| `Ctrl+Alt+Enter`    | Eval (load-file) the entire buffer       |

Results are appended to the output view; exceptions are expanded with
the class, message, and `ex-data`. Forms evaluate in the REPL's
**current namespace**, which is not necessarily the file's namespace —
see § 6 if you need them synchronised.

### Reloading

| Shortcut        | Action                                              |
|-----------------|-----------------------------------------------------|
| `Ctrl+R`        | Reload the active file's namespace via `:reload`    |
| `Ctrl+Shift+R`  | Switch the REPL to the active file's namespace      |
| `Ctrl+Shift+F5` | `clojure.tools.namespace.repl/refresh` (all changed)|

`(require 'ns :reload)` returns `nil` on success — if the REPL prints
`nil` after **Reload Current NS**, the reload completed without error.

---

## 6. Namespaces

The right-hand **Namespaces** dock lists every namespace loaded in
the REPL. Key behaviours:

- A filter line at the top performs case-insensitive substring match.
- The active namespace is highlighted in amber.
- Double-click a namespace to **in-ns** into it.
- Right-click a namespace for a context menu:
  - **Reload** — `(require 'ns :reload)`.
  - **Switch to** — `(in-ns 'ns)`.
  - **Remove** — `(remove-ns 'ns)` (use with care — the namespace
    disappears from the list and from the runtime).

The list auto-populates on connect and refreshes after every reload.
A manual **Refresh** button re-queries `(all-ns)` on demand.

### Current-namespace synchronisation

The REPL tracks its own current namespace independently of which
editor tab has focus. Use `Ctrl+Shift+R` (Switch to File NS) to jump
the REPL into the active file's namespace before evaluating forms,
or pick the namespace from the browser / fuzzy picker.

---

## 7. Structural Editing

Paredit-style commands operate on the S-expression surrounding the
cursor. They preserve paren balance — you cannot break it by accident.

| Shortcut              | Command          | Effect                                       |
|-----------------------|------------------|----------------------------------------------|
| `Alt+Shift+Right`     | Slurp forward    | Swallow the next sibling into the form       |
| `Alt+Shift+Left`      | Barf forward     | Eject the last child out of the form         |
| `Alt+W` → `(` `[` `{` | Wrap             | Wrap the form (or selection) with brackets   |
| `Alt+U`               | Unwrap / splice  | Remove the enclosing form, keep its contents |

### Wrap is a two-stroke chord

`Alt+W` alone does nothing visible — it **arms** a wrap, and the
status bar flashes `Wrap with ( [ or {`. The next keystroke:

- `(`, `[`, or `{` → completes the wrap with that bracket pair.
- Anything else → cancels the pending wrap; the key behaves normally.

If a selection is active, the selected text is wrapped verbatim.
Otherwise the form at the cursor is wrapped. If the cursor is not
inside a form, the status bar flashes `Nothing to wrap`.

### Wrap and unwrap are inverses

`Alt+W` `(` followed by `Alt+U` returns the buffer to its previous
state. After wrap, the cursor sits just inside the new opening
bracket; unwrap preferentially splices the parent form in that case,
so `(foo bar)` → `[(foo bar)]` → `(foo bar)` round-trips cleanly.

### Slurp / barf semantics

Slurp forward extends the current form to absorb the next sibling
expression, whitespace preserved. Barf forward is the inverse: the
last child leaves the form. Both are no-ops when there is nothing to
slurp or barf; they never edit when the buffer is unbalanced.

---

## 8. Settings and Configuration

`~/.config/cljde/settings.json` (JSON format) holds persistent settings,
grouped into top-level sections:

- `"window"` — geometry, dock state, width/height
- `"theme"` — active theme name
- `"editor"` — `font_family`, `font_size`, `tab_width`, `rainbow_parens`
- `"repl"` — `lein_command`, `clj_command`, `default_host`, `default_port`,
  `max_history_lines`
- `"files"` — `last_project_path`, `recent_files`, `open_tabs`,
  `current_tab_index`, `show_hidden`, `max_recent`

CLJDE writes this file on every clean shutdown. Manual edits are
honoured on next launch but overwritten by whatever the live settings
object decides at the next save. Use **View** toggles and the config
dialogs rather than editing `settings.json` directly when possible.

### Logging

`cljde.log` in the config directory captures `INFO`-level events from
every module. When reporting a bug, attach this file and the stderr
output of the terminal that launched `cljde`.

---

## 9. Troubleshooting

**The REPL won't start.**
- Confirm `clojure` (or `lein`) is on `PATH` by running it in the
  terminal that launched CLJDE.
- Inspect `cljde.log` for the full command line CLJDE invoked and the
  nREPL process's stderr.
- Try **REPL → Connect External…** against a REPL you start by hand
  in a terminal to isolate whether the issue is the process or the
  connection.

**Structural edits appear not to fire.**
- Click into the editor first — shortcuts only work when the editor
  has focus, not the namespace browser or REPL input.
- Verify the buffer is balanced; structural edits are suppressed on
  unbalanced buffers to avoid compounding damage.
- On Wayland / X11 some arrow-key events arrive with extra modifier
  bits (e.g. `KeypadModifier`); CLJDE already masks those, but if a
  specific chord misfires, capture the log output and open an issue.

**Namespace list is stale.**
- Press the **Refresh** button on the browser.
- Use `Ctrl+Shift+F5` to run `tools.namespace`'s `refresh` and then
  refresh again.

**Rainbow parens toggled off unexpectedly.**
- The setting lives in `"editor"` → `rainbow_parens`. Re-enable via
  **View → Rainbow Parens** or edit `settings.json`.

---

## 10. Shortcut Reference

The `Help → Quick Reference` dialog (`F1`) bundles every shortcut and
a Clojure cheat sheet in a searchable, themed window. Keep it open in
a second monitor while learning the IDE.
