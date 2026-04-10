from __future__ import annotations

from pathlib import Path


def display_repo_ref(path: Path) -> str:
    name = path.resolve().name
    return name or "."


def display_project_root(path: Path) -> str:
    name = path.resolve().name
    return name or "."


def display_config_path(path: Path) -> str:
    expanded = path.expanduser()
    if ".deepwiki" in expanded.parts:
        return str(Path(".deepwiki") / expanded.name)
    return expanded.name or str(expanded)
