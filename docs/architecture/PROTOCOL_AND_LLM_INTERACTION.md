# DeepWiki CLI - API Protocol & LLM Interaction Specification

This document serves as the single source of truth for the interaction protocols between the DeepWiki Open frontend (Next.js) and the DeepWiki CLI backend (FastAPI), as well as the backend's communication with large language models (LLMs). It is designed to be robust and reliable for deployments across different environments, particularly Linux servers.

---

## 1. Frontend-Backend API Protocol

The frontend communicates with the backend via HTTP REST endpoints. All JSON payloads must include `Content-Type: application/json`.

### 1.1 Endpoint Mappings (Next.js Rewrites)

The frontend Next.js server acts as a proxy for specific API calls to avoid CORS issues and simplify deployment. The following mappings must be maintained in `next.config.ts` or any reverse proxy (e.g., Nginx):

| Frontend Request Path          | Backend Destination Path                 | Method | Purpose                                      |
| :----------------------------- | :--------------------------------------- | :----- | :------------------------------------------- |
| `/api/wiki/projects`           | `/api/processed_projects`                | GET    | Retrieve list of generated wiki caches       |
| `/api/wiki_cache`              | `/api/wiki_cache`                        | GET/POST/DELETE | Manage wiki structure and page cache |
| `/local_repo/structure`        | `/local_repo/structure`                  | GET    | Fetch repository file tree                   |
| `/api/auth/status`             | `/auth/status`                           | GET    | Check authentication requirements            |
| `/api/auth/validate`           | `/auth/validate`                         | POST   | Validate user credentials                    |
| `/api/models/config`           | `/models/config`                         | GET    | Retrieve supported LLM providers and models  |
| `/api/lang/config`             | `/lang/config`                           | GET    | Retrieve supported output languages          |
| `/api/chat/stream`             | `/chat/completions/stream`               | POST   | Streaming LLM generation for Wiki and Chat   |

### 1.2 Core Data Models

#### The `AskRequest` Payload (`POST /chat/completions/stream`)
This is the most critical payload for generating content. The backend uses a flexible validation model (`AskRequest`) to maintain compatibility with varying frontend representations (e.g., `type` vs `repo_type`).

```json
{
  "repo_url": "local://hawk_agent-rs",  // For local repos, prefixed with local://
  "type": "local",                      // Fallback mapped to repo_type in backend
  "provider": "ollama",                 // LLM Provider (e.g., ollama, openai, anthropic)
  "model": "qwen3.5:9b",                // Specific model name
  "messages": [
    {
      "role": "user",
      "content": "Prompt text here..."
    }
  ]
}
```

#### Context Injection Formatting
The backend parses the `messages[-1].content` for specific markers to perform **Retrieval-Augmented Generation (RAG)** by reading actual source code from the disk:
1. **Directory Analysis**: If the prompt contains `[INTERNAL_CONFIG]` and `MODE: DATA_TRANSFORM`, the backend relies on the provided `SOURCE` file tree in the prompt.
2. **Page Generation**: If the prompt contains `using: path/to/file1.rs, path/to/file2.md. Language:`, the backend intercepts the request, reads the content of `file1.rs` and `file2.md` from the local disk, appends them to the prompt as `[SOURCE CONTEXT]`, and sends the final augmented prompt to the LLM.

---

## 2. Backend-LLM Communication

The backend abstracts LLM interactions using the `litellm` library, allowing seamless switching between local models (Ollama) and cloud providers.

### 2.1 Ollama Integration (Local Models)

When the `provider` is set to `"ollama"`, the backend bypasses default public endpoints and directs traffic to a specific Ollama host.

- **Environment Variable**: `OLLAMA_HOST`
- **Default Value**: `http://localhost:11434`
- **Usage**: Automatically injected into the `api_base` parameter of `litellm.acompletion()`.

**Important Constraints:**
- The connection must NOT use HTTPS unless specifically configured in Linux with valid certificates.
- If Ollama is running in Docker or another container network, `OLLAMA_HOST` must point to the container's IP (e.g., `http://172.17.0.1:11434`) rather than `localhost`.

### 2.2 Streaming Protocol

Responses from the LLM are streamed back to the frontend using **Server-Sent Events (SSE)**.
- **Content-Type**: `text/event-stream`
- **Error Handling**: If the LLM connection fails (e.g., `litellm.exceptions.APIConnectionError`), the backend catches the error, logs the traceback, and returns an HTTP `400 Bad Request` with the stringified exception.

---

## 3. Linux Deployment Guide

When deploying this architecture to a pure Linux environment (e.g., Ubuntu/Debian), strict adherence to network binding and environment variables is required.

### 3.1 Service Networking

1. **Ollama Binding**:
   By default, Linux Ollama binds to `127.0.0.1`. If your backend runs in a Docker container or needs to reach Ollama across a network interface, you **must** configure Ollama to listen on all interfaces.
   - `sudo systemctl edit ollama.service`
   - Add `Environment="OLLAMA_HOST=0.0.0.0"` under `[Service]`
   - `sudo systemctl daemon-reload && sudo systemctl restart ollama`

2. **Backend (FastAPI)**:
   Must be started with Uvicorn bound to `0.0.0.0` so it can receive proxy requests from the Next.js frontend.
   - `python -m uvicorn deepwiki.server.api:create_app --factory --host 0.0.0.0 --port 8001`

3. **Frontend (Next.js)**:
   The frontend requires the `SERVER_BASE_URL` environment variable at build and runtime to know where the backend resides.
   - `export SERVER_BASE_URL=http://127.0.0.1:8001`
   - `npm run start`

### 3.2 Environment Configuration File (`.env`)

For a production Linux deployment, prepare a `.env` file for the backend:

```env
# Backend Configuration
PYTHONPATH=src
DEEPWIKI_HOST=0.0.0.0
DEEPWIKI_PORT=8001

# LLM Configuration
OLLAMA_HOST=http://127.0.0.1:11434  # Update if Ollama is on a different server

# Optional: Cloud Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
```

### 3.3 Security & Credential Management (12-Factor App)

To ensure robust security during deployment:
- **No Hardcoded Keys**: NEVER hardcode API keys (e.g., `sk-...`), GitHub tokens (`ghp_...`), or authorization codes in the source code.
- **Environment Variables**: All credentials and sensitive settings (like `OPENAI_API_KEY`, `OLLAMA_HOST`, `WIKI_AUTH_CODE`) MUST be managed via environment variables (`os.environ.get(...)`).
- **File Exclusions**: NEVER commit `.env`, `.env.local`, or any file containing real credentials to the Git repository. Ensure these files are strictly ignored via `.gitignore`.
- **Log Masking**: When logging or printing errors, always mask full API keys (e.g., `sk-***XXXX`) to prevent leakage into production logs.

### 3.4 Reliability & Fallbacks

- **File Path Resolution**: The backend intercepts `local://` paths (used by the frontend) and actively attempts to resolve them against `Path.cwd()`, `Path.cwd().parent`, or absolute system paths. In Linux, ensure the backend process has read permissions (`chmod +r`) for the target codebase directories.
- **LLM Refusals**: The backend implements a robust interception layer. If an LLM stream detects refusal phrases (e.g., `"as an ai"`, `"cannot"`) in the first 20 characters of generating a Wiki structure, the backend immediately halts the stream and yields a hardcoded, structural XML fallback to prevent the frontend from collapsing.