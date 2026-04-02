# DeepWiki CLI - Data Flow Document

> Version: 0.1.0 | Status: Draft | Updated: 2026-04-02

---

## 1. End-to-End Data Flow Overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        deepwiki-cli Data Flow                            │
│                                                                          │
│  ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐  │
│  │Input │───►│Resolve│───►│ Repo │───►│Index │───►│ Core │───►│Output│  │
│  │Parse │    │Config │    │ Load │    │Build │    │Engine│    │Format│  │
│  └──────┘    └──────┘    └──────┘    └──────┘    └──────┘    └──────┘  │
│     CLI        Config      Data        Data       Core        Output    │
│     Layer      Layer       Layer       Layer      Layer       Layer     │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. `deepwiki generate` — Wiki 生成流程

```
User Input
│  deepwiki generate https://github.com/owner/repo --provider openai -l zh
│
▼
┌─────────────────── CLI Layer ───────────────────┐
│  1. Parse CLI args (Typer)                      │
│  2. Merge global options → Context object       │
│  Output: GenerateOptions {                      │
│    repo: "https://github.com/owner/repo"        │
│    provider: "openai", model: null (use config) │
│    language: "zh", format: "terminal"           │
│  }                                              │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────── Config Layer ────────────────┐
│  3. ConfigLoader.load(cli_overrides)            │
│     Level 1: CLI flags → provider=openai        │
│     Level 2: Env vars → OPENAI_API_KEY=sk-...   │
│     Level 3: Project .deepwiki/config.yaml → ∅  │
│     Level 4: User ~/.config/deepwiki/ → model=  │
│              gpt-4o                              │
│     Level 5: Defaults → temperature=0.7, ...    │
│                                                  │
│  4. AgentDetector.detect()                      │
│     → CLAUDE_CODE=1 detected                    │
│     → But --provider overrides agent context    │
│                                                  │
│  Output: DeepWikiConfig {                        │
│    provider: {name: openai, model: gpt-4o,      │
│               api_key: sk-...}                   │
│    embedder: {provider: openai,                  │
│               model: text-embedding-3-small}     │
│    ...                                           │
│  }                                               │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────── Data Layer (Repo) ───────────┐
│  5. RepoManager.resolve(repo_url)               │
│     → Detect repo_type: "github"                │
│     → Check cache: ~/.cache/deepwiki/repos/{h}  │
│     → Cache miss → git clone --depth=1          │
│     → local_path: /tmp/deepwiki/repos/a1b2c3    │
│                                                  │
│  6. DocumentReader.read_all(local_path)          │
│     → Walk directory tree                       │
│     → Apply include/exclude filters (repo.json) │
│     → Read file contents                        │
│     → Compute token counts                      │
│     → Skip oversized files                      │
│                                                  │
│  Output: Document[] (150 files)                  │
│    [{text: "...", file_path: "src/main.py",     │
│      file_type: "code", is_code: true,          │
│      token_count: 850}, ...]                    │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────── Core Layer (Generate) ───────┐
│                                                  │
│  ┌── Phase 1: Structure Planning ──────────┐    │
│  │  7. Build file tree string               │    │
│  │  8. Extract README content               │    │
│  │  9. LLM call: plan wiki structure        │    │
│  │     → CompletionRequest {                │    │
│  │         messages: [system_prompt,         │    │
│  │                    file_tree + readme],   │    │
│  │         model: "gpt-4o",                 │    │
│  │         provider: "openai"               │    │
│  │       }                                  │    │
│  │     → CompletionResponse {               │    │
│  │         content: JSON wiki structure      │    │
│  │       }                                  │    │
│  │  10. Parse → WikiStructure               │    │
│  │      {title, description, pages[         │    │
│  │        {id, title, file_paths,           │    │
│  │         importance}]}                    │    │
│  └──────────────────────────────────────────┘    │
│                         │                        │
│                         ▼                        │
│  ┌── Phase 2: Page Generation ─────────────┐    │
│  │  For each page (可并发):                 │    │
│  │  11. Gather file contents for page       │    │
│  │  12. LLM call: generate page content     │    │
│  │      → CompletionRequest {               │    │
│  │          messages: [system_prompt,        │    │
│  │                     page_def + files],   │    │
│  │          model: "gpt-4o", stream: true   │    │
│  │        }                                 │    │
│  │  13. (optional) Generate Mermaid diagram │    │
│  │  14. → WikiPage {title, content(md),     │    │
│  │                   diagrams[]}            │    │
│  │                                          │    │
│  │  Progress callback:                      │    │
│  │    → ("generating", 3, 10,               │    │
│  │       "Generating: Architecture")        │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  Output: WikiResult {                            │
│    title, description, pages[10],                │
│    metadata: {duration, tokens_used, ...}        │
│  }                                               │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────── Output Layer ────────────────┐
│  15. OutputFormatter (terminal mode):            │
│      → Rich Panel: title + description          │
│      → Rich Tree: table of contents             │
│      → Rich Panel per page: Markdown rendered   │
│      → Rich Syntax: Mermaid code blocks         │
│      → Rich Progress: during generation         │
│                                                  │
│  15. OutputFormatter (JSON mode):                │
│      → Progress events → stderr (JSONL)         │
│      → Final WikiResult → stdout (single JSON)  │
│                                                  │
│  15. OutputFormatter (markdown mode):            │
│      → Write files to --output-dir              │
│      → README.md + numbered pages + diagrams/   │
└─────────────────────────────────────────────────┘
```

---

## 3. `deepwiki ask` — RAG 问答流程

```
User Input
│  deepwiki ask ./my-repo "How does authentication work?"
│
▼
┌─────── CLI + Config (同 generate) ──────┐
│  Parse args → Resolve config            │
│  → repo: "./my-repo" (local)            │
│  → question: "How does auth work?"      │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────── Indexing Phase ───────────────┐
│                                                  │
│  1. CacheManager.check_index(repo, config)       │
│     → cache_key = sha256(repo_path + commit_sha) │
│     → Check ~/.cache/deepwiki/indexes/{key}/     │
│                                                  │
│  ┌── Cache HIT ─────────────────────────────┐    │
│  │  2a. VectorStore.load(cache_path)        │    │
│  │      → ChromaDB PersistentClient         │    │
│  │      → 2847 chunks loaded                │    │
│  │      → Skip to Query Phase               │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ┌── Cache MISS ────────────────────────────┐    │
│  │  2b. DocumentReader.read_all(repo_path)  │    │
│  │      → 150 Documents                     │    │
│  │                                          │    │
│  │  3. TextSplitter.split_documents(docs)   │    │
│  │     chunk_size=350, overlap=100          │    │
│  │     → 2847 Chunks                        │    │
│  │                                          │    │
│  │  4. Batch embedding (500 chunks/batch)   │    │
│  │     for batch in chunks[::500]:          │    │
│  │       EmbedProvider.embed(batch.texts)   │    │
│  │       → EmbeddingResponse {              │    │
│  │           embeddings: [[0.1, -0.3, ...]] │    │
│  │           dimensions: 256                │    │
│  │         }                                │    │
│  │       batch.embedding = response         │    │
│  │       progress(current, total)           │    │
│  │                                          │    │
│  │  5. VectorStore.add_documents(chunks)    │    │
│  │  6. VectorStore.persist(cache_path)      │    │
│  └──────────────────────────────────────────┘    │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────── Query Phase ─────────────────┐
│                                                  │
│  7. Embed the question                           │
│     EmbedProvider.embed(["How does auth work?"]) │
│     → query_embedding: [0.2, -0.1, ...]         │
│                                                  │
│  8. VectorStore.query(                           │
│       embedding=query_embedding,                 │
│       top_k=20                                   │
│     )                                            │
│     → relevant_chunks: Chunk[20]                 │
│       [{text: "class AuthMiddleware...",         │
│         metadata: {file_path: "src/auth.py",    │
│                    start_line: 45},              │
│         relevance_score: 0.94},                  │
│        ...]                                      │
│                                                  │
│  9. Build RAG prompt:                            │
│     messages = [                                 │
│       {"role": "system", "content":              │
│        "Answer based on the code context..."},   │
│       {"role": "user", "content":                │
│        "Context:\n{chunk_texts}\n\n              │
│         Question: How does auth work?"}          │
│     ]                                            │
│                                                  │
│  10. LLM call (streaming):                       │
│      LLMProvider.stream(CompletionRequest{       │
│        messages, model, provider                 │
│      })                                          │
│      → async yield "The authentication..."      │
│      → async yield " module uses JWT..."        │
│      → ...                                       │
│                                                  │
│  Output: answer_text + sources[]                 │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────── Output ──────────────────────┐
│  Terminal: stream chunks via Rich.print()        │
│  JSON: collect → single response JSON            │
│  Both: include sources[] with file_paths         │
└─────────────────────────────────────────────────┘
```

---

## 4. `deepwiki research` — 多轮研究流程

```
User Input
│  deepwiki research ./repo "Error handling patterns" --iterations 3
│
▼
┌── Indexing Phase (同 ask) ──┐
│  Build/load vector index    │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────── Research Loop ───────────────┐
│                                                  │
│  Iteration 1:                                    │
│  ┌──────────────────────────────────────────┐    │
│  │ question = initial_topic                  │    │
│  │ → RAG retrieve(question, top_k=20)       │    │
│  │ → LLM: analyze findings + identify gaps  │    │
│  │ → findings_1 = "..."                     │    │
│  │ → follow_ups = ["How are errors logged?",│    │
│  │                  "What retry strategies?"]│    │
│  └──────────────────────────────────────────┘    │
│                     │                            │
│                     ▼                            │
│  Iteration 2:                                    │
│  ┌──────────────────────────────────────────┐    │
│  │ question = follow_ups[best]              │    │
│  │ + context from iteration 1               │    │
│  │ → RAG retrieve(question, top_k=20)       │    │
│  │ → LLM: deepen analysis                  │    │
│  │ → findings_2 = "..."                     │    │
│  │ → follow_ups = [...]                     │    │
│  └──────────────────────────────────────────┘    │
│                     │                            │
│                     ▼                            │
│  Iteration 3:                                    │
│  ┌──────────────────────────────────────────┐    │
│  │ (same pattern, accumulating context)     │    │
│  │ → findings_3 = "..."                     │    │
│  └──────────────────────────────────────────┘    │
│                     │                            │
│                     ▼                            │
│  Synthesis:                                      │
│  ┌──────────────────────────────────────────┐    │
│  │ LLM: synthesize all findings into        │    │
│  │      comprehensive research report       │    │
│  │ → conclusion = "..."                     │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  Output: ResearchResult {                        │
│    topic, summary, iterations[], conclusion,     │
│    sources[]                                     │
│  }                                               │
└─────────────────────────────────────────────────┘
```

---

## 5. Agent Model Reuse — 决策流程

```
deepwiki <any-command>
         │
         ▼
┌── Provider Resolution ──────────────────────────────────────────────────┐
│                                                                         │
│  Step 1: Check CLI flags                                               │
│  ┌─────────────────────────────────────────────────┐                   │
│  │ --provider specified?                            │                   │
│  │   Yes → --model specified?                       │                   │
│  │           Yes → Use (provider, model) as-is      │──► RESOLVED      │
│  │           No  → Lookup default model for provider│──► RESOLVED      │
│  │   No  → Continue to Step 2                       │                   │
│  └─────────────────────────────────────────────────┘                   │
│                                                                         │
│  Step 2: Agent Detection                                               │
│  ┌─────────────────────────────────────────────────┐                   │
│  │ AgentDetector.detect()                           │                   │
│  │   → Check DEEPWIKI_AGENT_NAME env               │                   │
│  │   → Check CLAUDE_CODE env                        │                   │
│  │   → Check CURSOR_SESSION env                     │                   │
│  │   → Check GITHUB_COPILOT env                     │                   │
│  │   → Check AIDER_MODEL env                        │                   │
│  │                                                  │                   │
│  │ Agent detected?                                  │                   │
│  │   Yes → context.passthrough_available?            │                   │
│  │           Yes → Use agent's (provider, model,    │                   │
│  │                  api_key, api_base)               │──► RESOLVED      │
│  │           No  → Log "agent detected but cannot   │                   │
│  │                  passthrough", continue           │                   │
│  │   No  → Continue to Step 3                       │                   │
│  └─────────────────────────────────────────────────┘                   │
│                                                                         │
│  Step 3: Config File Lookup                                            │
│  ┌─────────────────────────────────────────────────┐                   │
│  │ ConfigLoader.load()                              │                   │
│  │   → Project config → User config → Defaults      │                   │
│  │   → provider.name configured?                    │                   │
│  │       Yes → API key available?                   │                   │
│  │               Yes → Use configured provider      │──► RESOLVED      │
│  │               No  → ConfigError (exit 2)         │──► ERROR         │
│  │       No  → Use default (google/gemini-2.5-flash)│                   │
│  │             → API key available?                  │                   │
│  │                 Yes →                             │──► RESOLVED      │
│  │                 No  → ConfigError (exit 2)        │──► ERROR         │
│  └─────────────────────────────────────────────────┘                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Cache System — 数据生命周期

```
┌─────────────────── Cache Directory Structure ───┐
│                                                  │
│  ~/.cache/deepwiki/    (or platform equivalent)  │
│  ├── repos/                                      │
│  │   ├── {hash1}/          # Cloned repository   │
│  │   │   ├── .git/                               │
│  │   │   └── src/...                             │
│  │   └── {hash2}/                                │
│  │                                               │
│  ├── indexes/                                    │
│  │   ├── {cache_key1}/     # Vector index        │
│  │   │   ├── chroma.sqlite3                      │
│  │   │   ├── *.bin                               │
│  │   │   └── metadata.json                       │
│  │   └── {cache_key2}/                           │
│  │                                               │
│  └── wikis/                                      │
│      ├── {cache_key1}.json # Generated wiki      │
│      └── {cache_key2}.json                       │
│                                                  │
└─────────────────────────────────────────────────┘

Cache Key Computation:
  repo_identifier = canonical_url or absolute_path
  cache_key = sha256(repo_identifier + ":" + branch + ":" + commit_sha[:8])[:16]

Cache Lifecycle:
  ┌────────┐    ┌────────┐    ┌──────────┐    ┌────────┐
  │ CREATE │───►│  HIT   │───►│ VALIDATE │───►│  USE   │
  │        │    │(exists)│    │(sha match)│   │        │
  └────────┘    └───┬────┘    └────┬─────┘    └────────┘
                    │              │
                    │         MISMATCH
                    │              │
                    │              ▼
                    │         ┌──────────┐
                    │         │ REBUILD  │
                    │         │(re-index)│
                    │         └──────────┘
                    │
                MISS│
                    │
                    ▼
               ┌──────────┐
               │  BUILD   │
               │(index +  │
               │ persist) │
               └──────────┘

metadata.json:
{
  "repo_url": "https://github.com/owner/repo",
  "branch": "main",
  "commit_sha": "a1b2c3d4e5f6",
  "embed_provider": "openai",
  "embed_model": "text-embedding-3-small",
  "embed_dimensions": 256,
  "chunk_count": 2847,
  "file_count": 150,
  "created_at": "2026-04-01T12:00:00Z",
  "deepwiki_version": "0.1.0"
}
```

---

## 7. Error Propagation Flow

```
┌─────────────────── Error Bubbling ──────────────┐
│                                                  │
│  Provider Layer:                                 │
│    litellm.exceptions.APIError                   │
│    litellm.exceptions.RateLimitError             │
│    litellm.exceptions.AuthenticationError        │
│         │                                        │
│         ▼ (catch + wrap)                         │
│  Core Layer:                                     │
│    LLMError(message, provider, model, cause)     │
│    EmbeddingError(message, provider, cause)      │
│         │                                        │
│         ▼ (catch + wrap)                         │
│  CLI Layer:                                      │
│    format_error(error, output_format)            │
│         │                                        │
│         ├── Terminal mode:                        │
│         │   stderr: Rich Panel (red border)      │
│         │   "[Error] OpenAI API rate limit       │
│         │    exceeded. Retry after 60s.           │
│         │    Hint: Use --provider ollama for      │
│         │    local inference."                    │
│         │   exit(4)                               │
│         │                                        │
│         └── JSON mode:                           │
│             stdout: {                             │
│               "status": "error",                 │
│               "type": "llm_error",               │
│               "data": {                          │
│                 "code": 4,                        │
│                 "message": "API rate limit...",   │
│                 "hint": "Use --provider ...",     │
│                 "provider": "openai",             │
│                 "model": "gpt-4o"                │
│               }                                  │
│             }                                    │
│             exit(4)                               │
│                                                  │
└─────────────────────────────────────────────────┘

Error Classification:
  ┌─────────────────┬──────┬───────────────────────────────────┐
  │ Error Type      │ Code │ Trigger Examples                  │
  ├─────────────────┼──────┼───────────────────────────────────┤
  │ ConfigError     │  2   │ Missing API key, invalid YAML     │
  │ RepoError       │  3   │ Clone failed, private repo denied │
  │ LLMError        │  4   │ Rate limit, model not found,      │
  │                 │      │ context length exceeded            │
  │ EmbeddingError  │  5   │ Embedding API failure,            │
  │                 │      │ ChromaDB corruption                │
  │ GeneralError    │  1   │ Unexpected exceptions             │
  └─────────────────┴──────┴───────────────────────────────────┘

API Key Masking:
  Any error message containing API keys must mask them:
  "sk-proj-abcdefXm2F" → "sk-p****Xm2F"
  Pattern: show first 4 chars + "****" + last 4 chars
```

---

## 8. Streaming Data Flow

### 8.1 Terminal Mode Streaming

```
LLM Provider                     Rich Console
     │                                │
     │ yield "The "                   │
     ├───────────────────────────────►│ print("The ", end="")
     │                                │
     │ yield "authentication "        │
     ├───────────────────────────────►│ print("authentication ", end="")
     │                                │
     │ yield "module..."             │
     ├───────────────────────────────►│ print("module...", end="")
     │                                │
     │ (stream complete)              │
     ├───────────────────────────────►│ print("\n")
     │                                │ display metadata panel
```

### 8.2 JSON Mode Streaming

```
LLM Provider                  stdout                    stderr
     │                           │                         │
     │                           │  {"status":"streaming", │
     │                           │   "type":"progress"...} │
     │                           │         ◄───────────────┤
     │ yield "The "              │                         │
     ├──────────────────────────►│ (buffer)                │
     │ yield "authentication "   │                         │
     ├──────────────────────────►│ (buffer)                │
     │ ...                       │                         │
     │ (stream complete)         │                         │
     ├──────────────────────────►│ {"status":"success",    │
     │                           │  "type":"answer",       │
     │                           │  "data":{"answer":      │
     │                           │   "The authentication   │
     │                           │    module..."}}         │

Note: --no-stream 时整个响应在 LLM 完成后一次性输出
      --stream + --json 时可选择 JSONL 逐行输出或最终聚合
```

### 8.3 JSON Streaming Mode (JSONL)

当 `--stream --json` 同时使用时，支持 JSONL (每行一个 JSON) 输出:

```
stderr: {"status":"streaming","type":"progress","data":{"phase":"indexing","current":1,"total":5}}
stderr: {"status":"streaming","type":"progress","data":{"phase":"indexing","current":5,"total":5}}
stdout: {"status":"streaming","type":"chunk","data":{"content":"The "}}
stdout: {"status":"streaming","type":"chunk","data":{"content":"authentication "}}
stdout: {"status":"streaming","type":"chunk","data":{"content":"module..."}}
stdout: {"status":"success","type":"done","data":{"content":""},"metadata":{...}}
```

消费者处理方式:
```bash
# 管道消费 (逐行处理)
deepwiki ask ./repo "question" --json --stream 2>/dev/null | while read line; do
  echo "$line" | jq -r '.data.content // empty'
done

# 聚合消费 (等待最终结果)
deepwiki ask ./repo "question" --json --no-stream 2>/dev/null | jq '.data.answer'
```

---

## 9. Concurrency Model

```
┌─────────────────── Async Architecture ──────────┐
│                                                  │
│  CLI Entry (sync)                                │
│  └── asyncio.run(main_async())                  │
│      │                                           │
│      ├── Sequential operations:                  │
│      │   Config loading (sync, fast)             │
│      │   Agent detection (sync, fast)            │
│      │   Repo clone (async, I/O bound)           │
│      │   Document reading (sync, CPU bound)      │
│      │                                           │
│      ├── Parallelizable operations:              │
│      │   Embedding batches (async, 3 concurrent) │
│      │   Page generation (async, limited by      │
│      │     LLM rate limits, 2-3 concurrent)      │
│      │                                           │
│      └── Streaming operations:                   │
│          LLM streaming (async iterator)          │
│          Output rendering (sync, per-chunk)      │
│                                                  │
│  Concurrency limits:                             │
│    Embedding:  asyncio.Semaphore(3)              │
│    Generation: asyncio.Semaphore(2)              │
│    Total HTTP:  httpx connection pool (20)       │
│                                                  │
└─────────────────────────────────────────────────┘
```
