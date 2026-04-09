from pathlib import Path


def read_repo_files(repo_path: Path, limit: int = 20) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for p in repo_path.rglob("*"):
        if not p.is_file():
            continue
        if ".git" in p.parts:
            continue
        if p.suffix.lower() not in {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt"}:
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
        files.append((str(p.relative_to(repo_path)), content))
        if len(files) >= limit:
            break
    return files
