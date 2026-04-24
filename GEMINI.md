# DeepWiki CLI - Project Context

DeepWiki CLI is an AI-powered wiki generator and code Q&A tool for git repositories. It is designed to be CLI-native and agent-friendly, following agent-native design patterns.

## Project Overview
- **Core Purpose**: Analyze repositories to generate structured wikis, answer code-related questions (RAG), and perform deep research on specific topics.
- **Main Technologies**:
  - **Language**: Python 3.10+
  - **CLI Framework**: [Typer](https://typer.tiangolo.com/) (with [Rich](https://rich.readthedocs.io/) for UI)
  - **LLM Interaction**: [LiteLLM](https://docs.litellm.ai/) (supports 100+ providers like OpenAI, Google, Anthropic, Ollama, etc.)
  - **Vector Store**: [ChromaDB](https://www.trychroma.com/) (default) and FAISS (optional).
  - **API/Server**: [FastAPI](https://fastapi.tiangolo.com/) & [Uvicorn](https://www.uvicorn.org/).
  - **Data Handling**: [tiktoken](https://github.com/openai/tiktoken) for tokenization, [PyYAML](https://pyyaml.org/) for config.
- **Architecture**: Layered design consisting of CLI, Output, Agent, Config, Core Engine, Provider, Data, and Server layers.

## Key Features
- **Multi-provider LLM**: Seamless switching between cloud and local models (Ollama).
- **Agent Integration**: Auto-detects environments like Claude Code, Cursor, or Copilot to reuse their LLM contexts.
- **Structured Output**: Supports Terminal (Rich), JSON (for AI agents), and Markdown (for export).
- **RAG Engine**: Vector-indexed code search for contextual Q&A.
- **Deep Research**: Iterative multi-turn analysis of codebase topics.

## Getting Started

### Full Stack Deployment & LLM Integration (CRITICAL FOR AGENTS)
The DeepWiki system consists of two parts that MUST run together for the web interface to work.
1. **Backend (FastAPI)**: Run `deepwiki serve` (or `python -m uvicorn deepwiki.server.api:create_app --factory --host 0.0.0.0 --port 8001`).
2. **Frontend (Next.js)**: Navigate to `vendor/deepwiki-open/` and run `npm run dev` (runs on port 3000).
3. **LLM Connection (Ollama)**: You MUST set the `OLLAMA_HOST` environment variable for the backend to connect to local models (e.g., `export OLLAMA_HOST=http://127.0.0.1:11434`). If running Ollama in Linux/WSL or Docker, ensure Ollama is bound to `0.0.0.0` (not just localhost).

**👉 CRITICAL READ:** For the exact API routing paths, proxy configurations, Context Injection prompts, and Linux deployment constraints, you MUST read `docs/architecture/PROTOCOL_AND_LLM_INTERACTION.md`.

### Installation
```bash
# Install dependencies (using uv or pip)
pip install -e .
```

### Key Commands
- `deepwiki generate <REPO>`: Analyze a repository and generate a structured wiki.
- `deepwiki ask <REPO> <QUESTION>`: Ask questions about the code using RAG.
- `deepwiki research <REPO> <TOPIC>`: Perform iterative deep research on a topic.
- `deepwiki config`: Manage configuration (init, show, set).
- `deepwiki export <REPO>`: Export generated wikis to Markdown or JSON.
- `deepwiki serve`: Start a FastAPI server providing REST endpoints.
- `deepwiki repl <REPO>`: Start an interactive REPL session.

## Development Context

### Project Structure
- `src/deepwiki/`: Source code root.
  - `cli/`: Typer command definitions and CLI logic.
  - `core/`: Core business logic (WikiGenerator, RAGEngine, ResearchEngine).
  - `providers/`: LLM and Embedding abstractions using LiteLLM.
  - `data/`: Repository management, document processing, and vector storage.
  - `output/`: Formatting logic for different output types.
  - `config/`: Configuration loading and defaults.
  - `agent/`: Agent environment detection and protocols.
- `docs/`: Comprehensive documentation (PRD, Technical Spec, Architecture, ADRs).
- `tests/`: Unit and E2E tests using `pytest`.
- `vendor/deepwiki-open/`: Submodule containing upstream logic (read-only reference).

### Development Workflow
- **Running Tests**: `pytest`
- **Linting/Type Checking**: Use `ruff` or `mypy` if configured.
- **Entry Point**: `src/deepwiki/cli/app.py`
- **Configuration**: Managed via `pyproject.toml` and environment variables (prefixed with `DEEPWIKI_`).

## Important Constraints & Guidelines
- **CRITICAL PROTOCOL DOCUMENT**: Before making any backend/frontend integration changes, routing modifications, or Linux deployment tweaks, you **MUST** read and adhere to `docs/architecture/PROTOCOL_AND_LLM_INTERACTION.md`. It is the definitive source of truth for the API protocol and Ollama/LLM bindings.
- **Upstream Integration**: `vendor/deepwiki-open/` is a read-only submodule. Do not modify files directly; use adapters in `src/deepwiki/` if needed.
- **JSON Mode**: When `--json` is used, all progress info should go to `stderr`, and the final structured result to `stdout`.
- **Path Handling**: Always use `pathlib.Path` for cross-platform compatibility.
- **Error Handling**: Follow the exit code contract (0: Success, 2: Config, 3: Repo, 4: LLM, 5: Embedding).
- **Security**: Never log or print full API keys; use masking (e.g., `sk-***XXXX`).
