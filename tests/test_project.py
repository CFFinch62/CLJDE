"""Tests for :mod:`cljde.files.project`."""

from __future__ import annotations

from pathlib import Path

from cljde.files.project import Project, detect_project, is_clojure_file


def _make_lein(root: Path, name: str = "fake-app") -> None:
    """Write a minimal ``project.clj`` to ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.clj").write_text(
        f'(defproject {name} "0.1.0"\n'
        '  :description "A fake project for tests"\n'
        '  :dependencies [[org.clojure/clojure "1.11.1"]])\n',
        encoding="utf-8",
    )


def _make_deps(root: Path) -> None:
    """Write a minimal ``deps.edn`` to ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "deps.edn").write_text(
        '{:paths ["src"]\n'
        ' :deps {org.clojure/clojure {:mvn/version "1.11.1"}}}\n',
        encoding="utf-8",
    )


def _make_git(root: Path) -> None:
    """Create an empty ``.git`` directory at ``root``."""
    (root / ".git").mkdir(parents=True, exist_ok=True)


def test_detects_lein_project(tmp_path: Path) -> None:
    """``project.clj`` yields a ``lein`` project with the declared name."""
    root = tmp_path / "proj"
    _make_lein(root, name="my-cool-app")
    project = detect_project(root)
    assert isinstance(project, Project)
    assert project.type == "lein"
    assert project.name == "my-cool-app"
    assert project.root == root


def test_detects_deps_project(tmp_path: Path) -> None:
    """``deps.edn`` yields a ``deps`` project with the directory name."""
    root = tmp_path / "deps-proj"
    _make_deps(root)
    project = detect_project(root)
    assert project is not None
    assert project.type == "deps"
    assert project.name == "deps-proj"
    assert project.root == root


def test_detects_git_only_project(tmp_path: Path) -> None:
    """A bare ``.git`` directory yields an ``other`` project."""
    root = tmp_path / "git-only"
    _make_git(root)
    project = detect_project(root)
    assert project is not None
    assert project.type == "other"
    assert project.name == "git-only"


def test_plain_directory_returns_none(tmp_path: Path) -> None:
    """A directory with no markers (and no marker ancestors) yields None."""
    root = tmp_path / "plain"
    root.mkdir()
    assert detect_project(root) is None


def test_walks_up_from_nested_subdirectory(tmp_path: Path) -> None:
    """Detection finds a marker several directories above the start path."""
    root = tmp_path / "app"
    _make_lein(root, name="nested-app")
    nested = root / "src" / "app" / "core"
    nested.mkdir(parents=True)
    project = detect_project(nested)
    assert project is not None
    assert project.type == "lein"
    assert project.name == "nested-app"
    assert project.root == root


def test_lein_beats_deps_at_same_directory(tmp_path: Path) -> None:
    """Within a single directory, ``project.clj`` takes priority."""
    root = tmp_path / "mixed"
    _make_lein(root, name="mixed-app")
    _make_deps(root)
    project = detect_project(root)
    assert project is not None
    assert project.type == "lein"


def test_unparseable_project_clj_falls_back_to_dirname(tmp_path: Path) -> None:
    """A ``project.clj`` without a defproject name uses the directory name."""
    root = tmp_path / "no-name"
    root.mkdir()
    (root / "project.clj").write_text("; empty\n", encoding="utf-8")
    project = detect_project(root)
    assert project is not None
    assert project.type == "lein"
    assert project.name == "no-name"


def test_detection_accepts_file_path(tmp_path: Path) -> None:
    """Starting from a file path, detection uses the file's parent."""
    root = tmp_path / "from-file"
    _make_deps(root)
    src = root / "src" / "foo.clj"
    src.parent.mkdir(parents=True)
    src.write_text("(ns foo)\n", encoding="utf-8")
    project = detect_project(src)
    assert project is not None
    assert project.type == "deps"
    assert project.root == root


def test_is_clojure_file_accepts_clj_family() -> None:
    """``.clj``, ``.cljs``, ``.cljc`` and ``.edn`` are Clojure files."""
    assert is_clojure_file(Path("foo.clj"))
    assert is_clojure_file(Path("foo.cljs"))
    assert is_clojure_file(Path("foo.cljc"))
    assert is_clojure_file(Path("foo.edn"))
    assert is_clojure_file(Path("FOO.CLJ"))


def test_is_clojure_file_rejects_other_extensions() -> None:
    """Unrelated extensions are not Clojure files."""
    assert not is_clojure_file(Path("foo.py"))
    assert not is_clojure_file(Path("README.md"))
    assert not is_clojure_file(Path("Makefile"))
