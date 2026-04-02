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

| Document | Description |
|----------|-------------|
| [PRD](docs/PRD.md) | Product requirements — what, why, for whom |
| [Technical Spec](docs/specs/TECHNICAL_SPEC.md) | CLI contracts, API definitions, data models |
| [Architecture](docs/architecture/ARCHITECTURE.md) | Layer design, module responsibilities, design decisions |
| [Data Flow](docs/architecture/DATA_FLOW.md) | Runtime data flow for each command, caching, streaming |
| [Constraints](docs/architecture/CONSTRAINTS.md) | Technical/platform/network/performance boundaries |
| [Implementation Plan](docs/PLAN.md) | Phased roadmap with deliverables and dependencies |

## License

MIT
