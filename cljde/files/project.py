"""Project root detection and Clojure file predicates.

Walks upward from a starting path looking for the nearest project
marker (``project.clj``, ``deps.edn``, or ``.git``) and classifies the
discovered project accordingly. Pure-function module; no Qt imports.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

ProjectType = Literal["lein", "deps", "other"]

CLOJURE_EXTENSIONS: frozenset[str] = frozenset({".clj", ".cljs", ".cljc", ".edn"})

_LEIN_DEFPROJECT_RE = re.compile(
    r"\(\s*defproject\s+([^\s()\[\]{}\"]+)",
)


@dataclass(frozen=True)
class Project:
    """A detected Clojure project root."""

    root: Path
    type: ProjectType
    name: str


def detect_project(path: Path) -> Project | None:
    """Walk up from ``path`` and return the nearest enclosing project.

    Priority within a single directory: ``project.clj`` (lein) beats
    ``deps.edn`` (deps) beats ``.git`` (other). Returns ``None`` if no
    marker is found between ``path`` and the filesystem root.
    """
    start = path if path.is_dir() else path.parent
    for candidate in [start, *start.parents]:
        project_clj = candidate / "project.clj"
        if project_clj.is_file():
            name = parse_lein_name(project_clj) or candidate.name
            return Project(candidate, "lein", name)
        if (candidate / "deps.edn").is_file():
            return Project(candidate, "deps", candidate.name)
        if (candidate / ".git").exists():
            return Project(candidate, "other", candidate.name)
    return None


def parse_lein_name(project_clj: Path) -> str | None:
    """Return the project name from a Leiningen ``project.clj``, or ``None``."""
    try:
        with project_clj.open("r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        log.debug("Cannot read %s: %s", project_clj, exc)
        return None
    match = _LEIN_DEFPROJECT_RE.search(text)
    return match.group(1) if match else None


def is_clojure_file(path: Path) -> bool:
    """Return True if ``path`` has a Clojure-family source extension."""
    return path.suffix.lower() in CLOJURE_EXTENSIONS
