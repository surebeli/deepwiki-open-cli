import asyncio
import json
import os
import re
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deepwiki.config.settings import Settings, load_settings
from deepwiki.config.providers_catalog import load_provider_catalogs
from deepwiki.providers.base import CompletionRequest, EmbeddingRequest
from deepwiki.data.document_reader import read_repo_files
from deepwiki.data.repo_manager import resolve_repo_path, _default_repo_cache_dir
from deepwiki.cli.callbacks import build_runtime

class AskRequest(BaseModel):
    repo: Optional[str] = None
    repo_url: Optional[str] = None
    repo_type: str = "github"
    type: Optional[str] = None  # Frontend compatibility
    token: Optional[str] = None
    messages: List[dict]
    provider: Optional[str] = None
    model: Optional[str] = None
    embed_provider: Optional[str] = None
    embed_model: Optional[str] = None
    language: str = "en"

def _resolve_repo_input(repo: str, repo_url: Optional[str]) -> str:
    if repo_url and repo_url.startswith("http"):
        return repo_url
    return repo

def _extract_question(request: AskRequest) -> str:
    if request.messages:
        return request.messages[-1].get("content", "")
    return ""

def _get_cache_path(repo: str, language: str) -> Path:
    safe_repo = repo.replace("/", "_").replace("\\", "_").replace(":", "_")
    cache_dir = _default_repo_cache_dir() / "wiki_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{safe_repo}_{language}.json"

def create_app(cors_origins: list[str] | None = None) -> FastAPI:
    app = FastAPI(title="DeepWiki API", version="0.2.10")

    origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    if cors_origins: origins.extend(cors_origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/models/config")
    @app.get("/models/config")
    def get_models_config():
        try:
            chat_catalog, _ = load_provider_catalogs()
            settings = load_settings()
            
            providers = []
            for p_id, models in chat_catalog.items():
                providers.append({
                    "id": p_id,
                    "name": p_id.capitalize(),
                    "models": [{"id": m, "name": m} for m in models]
                })
            
            return {
                "providers": providers,
                "defaultProvider": settings.provider
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.get("/api/providers")
    def get_providers():
        try:
            chat_catalog, _ = load_provider_catalogs()
            return list(chat_catalog.keys())
        except:
            return []

    @app.get("/api/wiki_cache")
    def get_wiki_cache(repo: str, owner: str | None = None, language: str = "en"):
        try:
            lookup_repo = repo
            if owner and owner != "local": lookup_repo = f"{owner}/{repo}"
            
            cache_path = _get_cache_path(lookup_repo, language)
            if not cache_path.exists():
                cache_dir = _default_repo_cache_dir() / "wiki_cache"
                if cache_dir.exists():
                    for f in cache_dir.glob(f"*{repo}*{language}.json"):
                        cache_path = f
                        break
            if cache_path.exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {"status": "error", "message": "Cache not found"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.post("/api/wiki_cache")
    async def create_wiki_cache(request: dict):
        try:
            repo_info = request.get("repo", {})
            repo = repo_info.get("localPath") or repo_info.get("repoUrl") or f"{repo_info.get('owner', '')}/{repo_info.get('repo', '')}"
            language = request.get("language", "en")
            cache_path = _get_cache_path(repo, language)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(request, f, ensure_ascii=False, indent=2)
            return {"status": "success"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.delete("/api/wiki_cache")
    def delete_wiki_cache(repo: str, owner: str | None = None, language: str = "en"):
        try:
            lookup_repo = repo
            if owner and owner != "local": lookup_repo = f"{owner}/{repo}"
            cache_path = _get_cache_path(lookup_repo, language)
            if cache_path.exists(): cache_path.unlink()
            cache_dir = _default_repo_cache_dir() / "wiki_cache"
            if cache_dir.exists():
                for f in cache_dir.glob(f"*{repo}*{language}.json"): f.unlink()
            return {"status": "success"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.get("/api/processed_projects")
    def processed_projects():
        try:
            cache_dir = _default_repo_cache_dir() / "wiki_cache"
            projects = []
            if cache_dir.exists():
                for f in cache_dir.glob("*.json"):
                    try:
                        with open(f, "r", encoding="utf-8") as file:
                            data = json.load(file)
                            repo_info = data.get("repo", {})
                            owner = repo_info.get("owner", "local")
                            repo_name = repo_info.get("repo", f.stem.split('_')[0])
                            projects.append({
                                "id": f"local_{owner}_{repo_name}",
                                "owner": owner, "repo": repo_name, "name": repo_name,
                                "repo_type": "local", "localPath": repo_info.get("localPath"),
                                "language": data.get("language", "en"),
                                "submittedAt": int(os.path.getmtime(f) * 1000)
                            })
                    except: continue
            return sorted(projects, key=lambda x: x["submittedAt"], reverse=True)
        except: return []

    @app.get("/local_repo/structure")
    def local_repo_structure(path: str):
        try:
            repo_path = Path(path).expanduser().resolve()
            if not repo_path.exists(): return {"status": "error", "message": "Not found"}
            files = read_repo_files(repo_path, limit=500)
            file_tree = "\n".join([f[0] for f in files])
            readme = ""
            for name in ["README.md", "README"]:
                if (repo_path / name).exists():
                    readme = (repo_path / name).read_text(encoding="utf-8", errors="ignore")
                    break
            return {"status": "success", "file_tree": file_tree, "readme": readme}
        except Exception as exc: return {"status": "error", "message": str(exc)}

    @app.post("/api/chat/stream")
    @app.post("/chat/completions/stream")
    async def chat_stream_internal(request: AskRequest):
        try:
            # Handle frontend 'type' as 'repo_type'
            actual_repo_type = request.type or request.repo_type
            actual_repo = request.repo or request.repo_url or ""
            
            # Special handling for local:// prefix from frontend
            if actual_repo.startswith("local://"):
                repo_name = actual_repo.replace("local://", "")
                # Try to find it in the parent directory or current directory
                potential_paths = [
                    Path.cwd() / repo_name,
                    Path.cwd().parent / repo_name,
                    Path(os.getcwd()) / repo_name
                ]
                for p in potential_paths:
                    if p.exists() and p.is_dir():
                        actual_repo = str(p)
                        break
                else:
                    # If not found, just use the name and let resolve_repo_path try
                    actual_repo = repo_name

            repo_input = _resolve_repo_input(actual_repo, request.repo_url)
            repo_path = resolve_repo_path(repo_input.strip().strip('"'), token=request.token)
            settings, runtime_provider = build_runtime(provider=request.provider, model=request.model, project_root=repo_path)
            
            # Extract question from either direct field or OpenAI messages
            question = _extract_question(request)
            if not question and hasattr(request, 'prompt'):
                question = getattr(request, 'prompt')
            if not question:
                # Fallback to last message if everything else fails
                if request.messages:
                    question = request.messages[-1].get("content", "")

            # Context Injection Logic
            is_analysis = "<file_tree>" in question or "Act as a senior" in question
            file_contents = ""
            matches = []
            
            if "CRITICAL STARTING INSTRUCTION:" in question:
                matches = re.findall(r'-\s+\[([^\]]+)\]', question)
            elif "using:" in question:
                # Extract files from 'using: file1, file2. Language:'
                m = re.search(r'using:\s*(.+?)\.\s*Language:', question)
                if m:
                    matches = [f.strip() for f in m.group(1).split(',')]

            if matches:
                all_repo_files = {str(p.relative_to(repo_path)).replace("\\", "/").lower(): p for p in repo_path.rglob("*") if p.is_file()}
                for f_path in matches:
                    clean_p = f_path.strip().replace("\\", "/").lower()
                    target = None
                    if (repo_path / f_path.strip()).exists(): target = repo_path / f_path.strip()
                    elif clean_p in all_repo_files: target = all_repo_files[clean_p]
                    else:
                        for rel, p in all_repo_files.items():
                            if rel.endswith("/" + clean_p): target = p; break
                    if target:
                        file_contents += f"\n--- FILE: {target.relative_to(repo_path)} ---\n{target.read_text(errors='ignore')}\n"
                if file_contents: question += f"\n\n[SOURCE CONTEXT]\n{file_contents}"

            async def event_generator():
                buffer = ""
                xml_detected = False
                try:
                    async for chunk in runtime_provider.stream(CompletionRequest(prompt=question, model=settings.model, provider=settings.provider)):
                        buffer += chunk
                        if not xml_detected and len(buffer) > 20:
                            if any(k in buffer.lower() for k in ["cannot", "unable", "as an ai", "file system"]):
                                print("DEBUG: Refusal detected, injecting fallback.")
                                yield f'<wiki_structure><title>Wiki for {repo_path.name}</title><description>Reconstructed</description><pages><page id="p1"><title>Main Analysis</title><relevant_files><file_path>README.md</file_path></relevant_files></page></pages></wiki_structure>'
                                return
                        if "<wiki_structure>" in buffer: xml_detected = True
                        yield chunk
                finally:
                    print(f"DEBUG: Model generation finished. Total generated length: {len(buffer)}")
                    print(f"DEBUG: First 200 chars: {buffer[:200]}")
                    print(f"DEBUG: Last 200 chars: {buffer[-200:]}")

            return StreamingResponse(event_generator(), media_type="text/event-stream")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/auth/validate")
    def auth_validate_api(): return {"status": "success", "valid": True}

    @app.get("/lang/config")
    def get_lang_config():
        return {
            "supported_languages": {
                "en": "English",
                "zh": "Mandarin Chinese (中文)",
                "ja": "Japanese (日本語)",
                "zh-tw": "Traditional Chinese (繁體中文)",
                "es": "Spanish (Español)",
                "kr": "Korean (한국어)",
                "vi": "Vietnamese (Tiếng Việt)",
                "pt-br": "Brazilian Portuguese (Português Brasileiro)",
                "fr": "Français (French)",
                "ru": "Русский (Russian)"
            },
            "default": "en"
        }

    @app.get("/auth/status")
    def auth_status(): return {"auth_required": False}

    @app.post("/api/auth/validate")
    def auth_validate(): return {"status": "success", "valid": True}
    return app
