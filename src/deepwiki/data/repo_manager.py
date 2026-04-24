from __future__ import annotations

import base64
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def _default_repo_cache_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "deepwiki" / "repos"
    return Path.home() / ".cache" / "deepwiki" / "repos"


def _is_remote_repo(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _sanitize_repo_url(repo: str) -> str:
    parsed = urlparse(repo)
    host = parsed.hostname or parsed.netloc
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return parsed._replace(netloc=host).geturl()


def _detect_repo_type(repo: str, repo_type: str | None) -> str:
    if repo_type:
        return repo_type.lower()
    host = (urlparse(repo).hostname or "").lower()
    if "github.com" in host:
        return "github"
    if "gitlab" in host:
        return "gitlab"
    if "bitbucket" in host:
        return "bitbucket"
    return "generic"


def _build_auth_header(token: str, provider: str) -> str:
    username = "git"
    if provider == "github":
        username = "x-access-token"
    elif provider == "gitlab":
        username = "oauth2"
    elif provider == "bitbucket":
        username = "x-token-auth"
    raw = f"{username}:{token}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return f"AUTHORIZATION: basic {encoded}"


def _target_clone_dir(repo: str) -> Path:
    digest = hashlib.sha1(repo.encode("utf-8")).hexdigest()[:16]
    parsed = urlparse(repo)
    repo_name = Path(parsed.path).name
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    if not repo_name:
        repo_name = "repo"
    return _default_repo_cache_dir() / f"{repo_name}-{digest}"


def _git_clone(repo: str, target_dir: Path, token: str | None, repo_type: str | None) -> Path:
    if shutil.which("git") is None:
        raise ValueError("Git executable not found in PATH")

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    clean_repo = _sanitize_repo_url(repo)
    command: list[str] = ["git"]
    if token:
        provider = _detect_repo_type(clean_repo, repo_type)
        command.extend(["-c", f"http.extraheader={_build_auth_header(token, provider)}"])
    command.extend(["clone", "--depth", "1", clean_repo, str(target_dir)])
    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"Git clone timeout for repository: {clean_repo}") from exc
    except subprocess.CalledProcessError as exc:
        error_output = (exc.stderr or exc.stdout or "").strip()
        raise ValueError(f"Git clone failed for repository: {clean_repo}\n{error_output}") from exc
    return target_dir


def resolve_repo_path(repo: str, token: str | None = None, repo_type: str | None = None) -> Path:
    # Handle local:// prefix used by the UI
    if repo.startswith("local://"):
        repo = repo[8:]

    if _is_remote_repo(repo):
        target_dir = _target_clone_dir(repo)
        if (target_dir / ".git").exists():
            return target_dir.resolve()
        return _git_clone(repo=repo, target_dir=target_dir, token=token, repo_type=repo_type).resolve()

    path = Path(repo).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Repository path not found: {repo}")
    return path
