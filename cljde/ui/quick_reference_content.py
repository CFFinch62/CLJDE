"""Static HTML content for :class:`QuickReferenceDialog`.

Kept in its own module so the dialog's layout code stays short and the
rendered text is easy to eyeball and extend. Two constants are
exported: a Clojure cheat sheet and a CLJDE keybinding summary.
"""

from __future__ import annotations


def _section(title: str, rows: list[tuple[str, str]]) -> str:
    """Render a titled table of ``(name, description)`` rows."""
    body = "".join(
        f'<tr><td class="name"><code>{name}</code></td>'
        f'<td class="desc">{desc}</td></tr>'
        for name, desc in rows
    )
    return f"<h2>{title}</h2><table>{body}</table>"


CLOJURE_CHEATSHEET_HTML = (
    '<p class="lead">A minimal reference to the forms and functions you '
    "reach for every day. Run an expression with <code>Ctrl+Enter</code>; "
    "see the REPL dock for results.</p>"
    + _section("Definitions", [
        ("def", "Bind a var to a value: <code>(def x 42)</code>."),
        ("defn", "Define a function: <code>(defn add [a b] (+ a b))</code>."),
        ("defn-", "Private function (ns-local) — same syntax as <code>defn</code>."),
        ("fn", "Anonymous function: <code>(fn [x] (* x x))</code> or <code>#(* % %)</code>."),
        ("let", "Local bindings: <code>(let [a 1 b 2] (+ a b))</code>."),
        ("letfn", "Local functions that may be mutually recursive."),
        ("defmacro", "Define a macro — operates on code before evaluation."),
    ])
    + _section("Control flow", [
        ("if", "<code>(if test then else)</code>; missing else defaults to nil."),
        ("when", "<code>(when test body...)</code>; do-style body, nil on false."),
        ("cond", "Multi-branch: pairs of <code>test expr</code>; <code>:else</code> as default."),
        ("case", "Value dispatch on compile-time constants."),
        ("condp", "<code>(condp pred expr clauses)</code> — like case with a predicate."),
        ("do", "Sequence side effects; returns last value."),
        ("recur", "Tail-call back to the enclosing <code>loop</code>/<code>fn</code>."),
        ("loop", "Establish a recur target: <code>(loop [i 0] ...)</code>."),
    ])
    + _section("Threading macros", [
        ("-&gt;", "Thread-first: inserts value as 1st arg at each step."),
        ("-&gt;&gt;", "Thread-last: inserts value as last arg at each step."),
        ("as-&gt;", "Thread with an explicit name for the value."),
        ("some-&gt;", "Thread-first, short-circuit on nil."),
        ("some-&gt;&gt;", "Thread-last, short-circuit on nil."),
        ("cond-&gt;", "Conditionally thread through steps whose test is truthy."),
        ("doto", "Thread mutation: calls each form on the initial value."),
    ])
    + _section("Collections &amp; sequences", [
        ("list / vector / map / set", "Core collection constructors."),
        ("conj", "Add an element; vector-append, list-prepend, set-insert."),
        ("assoc / dissoc", "Associate / remove a key in a map or vector."),
        ("update", "Apply a function to a map/vector entry."),
        ("get / get-in", "Lookup; <code>get-in</code> walks a path."),
        ("assoc-in / update-in", "Deep update by path: <code>[:a :b 0]</code>."),
        ("map / filter / reduce", "Core sequence combinators (lazy for map/filter)."),
        ("for", "List comprehension: <code>(for [x xs :when (pos? x)] (* x x))</code>."),
        ("doseq", "Eager side-effect loop over a sequence."),
        ("first / rest / next / last", "Head/tail/last of a seq."),
        ("take / drop / partition", "Slice, skip, and group a sequence."),
        ("into", "Pour a seq into a target collection."),
    ])
    + _section("Predicates &amp; equality", [
        ("=", "Structural equality across Clojure types."),
        ("identical?", "Reference identity (rarely what you want)."),
        ("nil? / some?", "Is/is-not nil."),
        ("empty? / seq", "Empty test / coerce to seq (nil if empty)."),
        ("zero? / pos? / neg?", "Numeric sign tests."),
    ])
    + _section("State &amp; concurrency", [
        ("atom", "Uncoordinated synchronous state: <code>(atom 0)</code>."),
        ("swap!", "Apply a function to an atom: <code>(swap! a inc)</code>."),
        ("reset!", "Set atom to a new value unconditionally."),
        ("deref / @", "Read current value of an atom/ref/agent/future."),
        ("ref / alter / dosync", "Coordinated transactional refs (STM)."),
        ("agent / send / send-off", "Async, uncoordinated, queued updates."),
        ("future / promise", "One-shot deferred values."),
    ])
    + _section("Namespaces", [
        ("ns", "Declare a namespace (top of every Clojure file)."),
        ("require", "<code>(require '[clojure.string :as str])</code>."),
        ("refer", "Make symbols from another ns callable without a prefix."),
        ("in-ns", "Switch the current namespace in the REPL."),
        ("all-ns", "Return all loaded namespaces."),
    ])
    + _section("Destructuring", [
        ("[a b &amp; more]", "Vector destructuring with rest-arg."),
        ("{:keys [x y]}", "Map destructuring by keyword key."),
        (":as name", "Bind the whole collection alongside its parts."),
        (":or {k default}", "Default values for missing map keys."),
    ])
    + _section("Exceptions", [
        ("try / catch / finally", "Standard exception handling."),
        ("throw", "Throw any Throwable (usually <code>ex-info</code>)."),
        ("ex-info / ex-data", "Structured exceptions carrying a map."),
    ])
    + _section("Java interop", [
        ("(.method obj args)", "Instance-method call."),
        ("(Class/method args)", "Static-method call."),
        ("(Class. args)", "Constructor: <code>(java.util.Date.)</code>."),
        (".. / doto", "Chain method calls on a common receiver."),
    ])
)


CLJDE_SHORTCUTS_HTML = (
    '<p class="lead">Defaults for the editor, REPL, and structural '
    "editing commands. All shortcuts work when the editor has focus.</p>"
    + _section("File", [
        ("Ctrl+N", "New untitled buffer."),
        ("Ctrl+O", "Open file."),
        ("Ctrl+Shift+O", "Open project (folder)."),
        ("Ctrl+S / Ctrl+Shift+S", "Save / Save As."),
        ("Ctrl+Shift+N", "Go to namespace (fuzzy picker)."),
        ("Ctrl+Q", "Quit."),
    ])
    + _section("Editor", [
        ("Ctrl+Z / Ctrl+Shift+Z", "Undo / Redo."),
        ("Ctrl+X / Ctrl+C / Ctrl+V", "Cut / Copy / Paste."),
        ("Ctrl+F", "Find in buffer."),
        ("Tab / Shift+Tab", "Indent / outdent current line."),
    ])
    + _section("Structural editing", [
        ("Alt+Shift+Right", "Slurp forward — swallow next sibling into the form."),
        ("Alt+Shift+Left", "Barf forward — eject last child out of the form."),
        ("Alt+W then ( [ {", "Wrap the form at cursor with the chosen bracket."),
        ("Alt+U", "Unwrap (splice) the enclosing form."),
    ])
    + _section("REPL &amp; evaluation", [
        ("Ctrl+Enter", "Eval form at cursor."),
        ("Ctrl+Shift+Enter", "Eval selection."),
        ("Ctrl+Alt+Enter", "Eval current file (load-file)."),
        ("Ctrl+R", "Reload current namespace (<code>:reload</code>)."),
        ("Ctrl+Shift+R", "Switch REPL to current file's namespace."),
        ("Ctrl+Shift+F5", "Reload all changed namespaces (<code>tools.namespace</code>)."),
    ])
    + _section("View", [
        ("F9 / F10 / F11", "Toggle file tree / REPL / namespace docks."),
        ("F12", "Toggle full-screen."),
        ("F1", "Open this Quick Reference dialog."),
    ])
)
