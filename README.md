# deepwiki-cli

AI-powered wiki generator and code Q&A for git repositories. CLI-native, agent-friendly.

> Status: Spec-Driven Development Phase — see `docs/` for complete design documentation.

## What is this?

DeepWiki CLI brings [deepwiki-open](https://github.com/AsyncFuncAI/deepwiki-open)'s AI wiki generation to the command line, following [CLI-Anything](https://github.com/HKUDS/CLI-Anything)'s agent-native design patterns.

```bash
# Generate wiki for any repository
deepwiki generate https://github.com/owner/repo

# Ask questions about code (RAG-powered)
deepwiki ask ./my-repo "How does authentication work?"

# Deep research on a topic
deepwiki research ./my-repo "Error handling patterns" --iterations 3

# Interactive REPL session
deepwiki repl ./my-repo
```

## Key Features (Planned)

- **Multi-provider LLM**: OpenAI, Google, Anthropic, Ollama, OpenRouter, Azure, Bedrock
- **Fully offline**: Ollama local models for air-gapped environments
- **Agent model reuse**: Auto-detect Claude Code / Cursor / Copilot and reuse their LLM
- **Cross-platform**: Linux, macOS, Windows, CI/Headless, Docker
- **Structured output**: Terminal (Rich), JSON (for agents), Markdown (for export)
- **RAG Q&A**: Vector-indexed code search with conversational context

## Documentation

**⚠️ CRITICAL FOR DEVELOPERS & AI AGENTS:** Before attempting to start the full stack web interface, modify API routes, or deploy this project to a pure Linux environment, you **MUST** read the [API Protocol & LLM Interaction Spec](docs/architecture/PROTOCOL_AND_LLM_INTERACTION.md). This document contains the definitive configuration for Next.js proxies, FastAPI routing, Context Injection logic, and `OLLAMA_HOST` binding rules.

| Document | Description |
|----------|-------------|
| [PRD](docs/PRD.md) | Product requirements — what, why, for whom |
| [Technical Spec](docs/specs/TECHNICAL_SPEC.md) | CLI contracts, API definitions, data models |
| [Architecture](docs/architecture/ARCHITECTURE.md) | Layer design, module responsibilities, design decisions |
| [Protocol & LLM Interaction](docs/architecture/PROTOCOL_AND_LLM_INTERACTION.md) | **(START HERE)** Full-stack API routing, Linux deployment, and Ollama integration |
| [Data Flow](docs/architecture/DATA_FLOW.md) | Runtime data flow for each command, caching, streaming |
| [Constraints](docs/architecture/CONSTRAINTS.md) | Technical/platform/network/performance boundaries |
| [ADR-001: deepwiki-open Integration](docs/architecture/ADR-001-deepwiki-open-integration.md) | How to use upstream code via submodule without invasive changes |
| [Implementation Plan](docs/PLAN.md) | Phased roadmap with deliverables and dependencies |

## Full Stack Web Deployment

To run the web interface (Next.js) alongside the local CLI backend (FastAPI):

1. **Start the Backend:**
   ```bash
   # Set your Ollama host if it's not running on default localhost
   export OLLAMA_HOST=http://127.0.0.1:11434
   deepwiki serve
   # Or for development with hot-reload:
   # python -m uvicorn deepwiki.server.api:create_app --factory --host 0.0.0.0 --port 8001 --reload
   ```

2. **Start the Frontend:**
   ```bash
   cd vendor/deepwiki-open/
   npm install
   npm run dev
   ```
   Navigate to `http://localhost:3000`.

## License

MIT
