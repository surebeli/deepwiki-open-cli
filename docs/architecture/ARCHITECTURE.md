# DeepWiki CLI - Architecture Document

> Version: 0.1.0 | Status: Draft | Updated: 2026-04-01

## 1. System Architecture Overview

```
                              ┌─────────────────────────────┐
                              │       User / AI Agent        │
                              └──────────────┬──────────────┘
                                             │
                              ┌──────────────▼──────────────┐
                              │        CLI Layer (Typer)      │
                              │  generate│ask│research│repl   │
                              │  export│config│serve          │
                              │  Global: --json --verbose     │
                              └──────────────┬──────────────┘
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     │                       │                       │
          ┌──────────▼──────────┐ ┌──────────▼──────────┐ ┌─────────▼─────────┐
          │   Output Layer      │ │   Agent Layer        │ │  Config Layer     │
          │                     │ │                      │ │                   │
          │  TerminalFormatter  │ │  AgentDetector       │ │  ConfigLoader     │
          │  JSONFormatter      │ │  AgentProtocol       │ │  5-level merge    │
          │  MarkdownFormatter  │ │  SKILL.md            │ │  Pydantic models  │
          └─────────────────────┘ └──────────┬──────────┘ └─────────┬─────────┘
                                             │                       │
                              ┌──────────────▼───────────────────────▼──┐
                              │           Core Engine                    │
                              │                                         │
                              │  WikiGenerator    ──  plan + generate   │
                              │  RAGEngine        ──  embed + retrieve  │
                              │  ResearchEngine   ──  multi-turn iter   │
                              │  DiagramGenerator ──  Mermaid syntax    │
                              │  Prompts          ──  template library  │
                              └──────────────┬──────────────────────────┘
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     │                       │                       │
          ┌──────────▼──────────┐ ┌──────────▼──────────┐ ┌─────────▼─────────┐
          │  Provider Layer     │ │   Data Layer         │ │  Server Layer     │
          │                     │ │                      │ │  (optional)       │
          │  BaseLLMProvider    │ │  RepoManager         │ │  FastAPI app      │
          │  LiteLLMProvider    │ │  DocumentReader      │ │  REST endpoints   │
          │  AgentProxy         │ │  TextSplitter        │ │  CORS, health     │
          │  Embedder           │ │  VectorStore         │ │                   │
          │                     │ │  CacheManager        │ │                   │
          └──────────┬──────────┘ └──────────┬──────────┘ └───────────────────┘
                     │                       │
          ┌──────────▼──────────┐ ┌──────────▼──────────┐
          │  External Services  │ │  Local Storage       │
          │                     │ │                      │
          │  OpenAI API         │ │  ChromaDB (vectors)  │
          │  Google AI API      │ │  YAML configs        │
          │  Ollama (local)     │ │  Wiki cache files    │
          │  OpenRouter         │ │  Git repositories    │
          │  Azure / Bedrock    │ │                      │
          └─────────────────────┘ └─────────────────────┘
```

## 2. Layer Responsibilities

### 2.1 CLI Layer (`src/deepwiki/cli/`)

**职责**: 解析命令行参数，编排核心引擎，分发输出。

```
cli/
├── app.py          # Typer 应用根 — 注册所有子命令，定义全局选项回调
├── generate.py     # `deepwiki generate` — 调用 WikiGenerator
├── ask.py          # `deepwiki ask` — 调用 RAGEngine.ask()
├── research.py     # `deepwiki research` — 调用 ResearchEngine
├── export.py       # `deepwiki export` — 调用 WikiGenerator + 文件写入
├── config_cmd.py   # `deepwiki config` — 配置 CRUD 操作
├── serve.py        # `deepwiki serve` — 启动 FastAPI 服务
├── repl.py         # `deepwiki repl` — prompt-toolkit 交互循环
└── callbacks.py    # 共享回调: 输出格式解析、provider 初始化
```

**设计原则**:
- CLI 层是**薄层**，不包含业务逻辑
- 每个命令文件是独立的 Typer 子应用
- 全局选项通过 `typer.Context` 传递到子命令
- 所有命令共享一致的选项命名（`-p/--provider`, `-m/--model`, `-f/--format`）

### 2.2 Core Engine (`src/deepwiki/core/`)

**职责**: 实现核心业务逻辑 — Wiki 生成、RAG 问答、研究引擎。

```
core/
├── wiki_generator.py     # 规划 Wiki 结构 + 逐页生成内容
├── rag_engine.py         # 嵌入索引 + 向量检索 + 上下文增强生成
├── research_engine.py    # 多轮迭代研究 (基于 RAG)
├── diagram_generator.py  # 生成 Mermaid 图表代码
└── prompts.py            # 所有 LLM prompt 模板集中管理
```

**设计原则**:
- Core 层不感知 CLI 参数或输出格式
- 通过依赖注入接收 Provider 和 VectorStore 实例
- 支持 async/await 异步操作
- 进度回调通过 `Callable` 参数传入

### 2.3 Provider Layer (`src/deepwiki/providers/`)

**职责**: 抽象 LLM 调用，统一 completion/streaming/embedding 接口。

```
providers/
├── base.py               # 抽象基类 + 数据模型 (Request/Response)
├── litellm_provider.py   # 基于 litellm 的统一实现
├── agent_proxy.py        # Agent 模型直通 (检测 + 转发)
└── embedder.py           # Embedding 专用抽象
```

**设计原则**:
- 单一依赖: 所有 LLM 调用通过 litellm 路由
- Provider 是无状态的 — 每次调用携带完整配置
- Agent 检测在 Provider 初始化时执行一次，结果缓存

### 2.4 Data Layer (`src/deepwiki/data/`)

**职责**: 仓库读取、文档处理、向量存储、缓存管理。

```
data/
├── repo_manager.py       # Git clone/pull, 仓库路径解析
├── document_reader.py    # 文件遍历、读取、Document 对象构建
├── text_splitter.py      # 文本分块 (word-based, 可配置 chunk_size)
├── vector_store.py       # ChromaDB/FAISS 抽象层
└── cache_manager.py      # 基于文件系统的缓存 (向量索引 + Wiki 结果)
```

**设计原则**:
- 全程使用 `pathlib.Path`，不做字符串路径拼接
- VectorStore 接口与具体实现分离，支持运行时切换
- CacheManager 基于仓库 URL + commit SHA 生成缓存键

### 2.5 Output Layer (`src/deepwiki/output/`)

**职责**: 将核心引擎的结果渲染为不同格式。

```
output/
├── formatter.py          # OutputFormatter 协议 + 工厂函数
├── terminal.py           # Rich 终端渲染 (Panel, Tree, Markdown, Progress)
├── json_output.py        # 结构化 JSON (Agent 消费)
├── markdown_output.py    # Markdown 文件写入
└── mermaid_renderer.py   # Mermaid 代码渲染/导出
```

**设计原则**:
- 所有格式实现同一个 Protocol 接口
- JSON 模式下，progress 输出到 stderr，结果输出到 stdout
- 自动检测 `isatty()` 决定是否启用 Rich 渲染

### 2.6 Agent Layer (`src/deepwiki/agent/`)

**职责**: AI Agent 环境检测、通信协议、可发现性。

```
agent/
├── detector.py           # 环境变量嗅探，识别父 Agent
├── protocol.py           # Agent JSON 通信协议定义
└── skill.py              # SKILL.md 生成辅助工具
```

### 2.7 Config Layer (`src/deepwiki/config/`)

**职责**: 分层配置加载、验证、持久化。

```
config/
├── settings.py           # Pydantic 配置模型 + ConfigLoader
├── defaults.py           # 内置默认值
├── generator.json        # LLM 模型预设 (provider -> model 映射)
├── embedder.json         # Embedding 模型预设
└── repo.json             # 文件过滤规则 (extension whitelist/blacklist)
```

## 3. Key Design Decisions

### 3.1 litellm vs 直接 Provider 客户端

```
deepwiki-open (现状):                    deepwiki-cli (目标):
┌─────────────────────────┐              ┌─────────────────────────┐
│ openai_client.py        │              │                         │
│ openrouter_client.py    │              │                         │
│ azureai_client.py       │              │   litellm_provider.py   │
│ bedrock_client.py       │   ────►      │   (~150 lines)          │
│ dashscope_client.py     │              │                         │
│ google_embedder_client.py│             │   litellm.completion()  │
│ ollama_client.py        │              │   litellm.embedding()   │
│ (~2000 lines total)     │              │                         │
└─────────────────────────┘              └─────────────────────────┘
```

**决策理由**:
- litellm 一个函数调用覆盖 100+ 提供商
- 内置重试、fallback、token 计数
- 消除 7 个客户端的维护负担
- **Trade-off**: 引入一个额外依赖；如果 litellm 有 bug 需要等待上游修复

### 3.2 ChromaDB vs FAISS

| 维度 | ChromaDB | FAISS |
|------|----------|-------|
| 持久化 | 内置 PersistentClient | 需手动 pickle 序列化 |
| 元数据过滤 | 原生 where 子句 | 需要外部实现 |
| API 复杂度 | 高层抽象，简单 | 底层，需要 numpy 操作 |
| 依赖体积 | ~50MB | ~20MB (faiss-cpu) |
| 适用场景 | CLI 嵌入式使用 | 高性能、大规模场景 |

**决策**: ChromaDB 为主，FAISS 作为可选后端（`--vector-store faiss`）。

### 3.3 Typer vs Click

**决策**: Typer（基于 Click 构建）。

- 类型提示自动生成参数解析
- 自动 `--help` 和 shell 补全
- 包含 Rich 集成（通过 `typer[all]`）
- 底层仍是 Click，兼容 Click 插件

### 3.4 与 deepwiki-open 的集成策略

**决策**: Git Submodule（只读）+ 渐进式适配层。详见 [ADR-001](ADR-001-deepwiki-open-integration.md)。

**三个关键发现**（决定策略的前提）:
- `prompts.py` 是纯字符串常量 — **零耦合**，可直接 `import`
- `RAG` 类无 FastAPI 耦合 — 可独立调用 `rag = RAG(...); rag.call(query)`
- `api/api.py`（路由层）和 7 个 provider client 无复用价值，被 litellm 替代

**集成层次**:

```
vendor/deepwiki-open/        ← git submodule，只读，不修改任何文件
├── api/prompts.py           ← Phase 1: 直接 import，立即同步 prompt 改进
├── api/config/*.json        ← Phase 1: symlink，立即同步模型预设和过滤规则
├── api/data_pipeline.py     ← Phase 3: 通过适配层调用（类型转换）
└── api/rag.py               ← Phase 3: 通过适配层调用（RAG 算法）

src/deepwiki/adapters/       ← 适配层，仅负责类型转换，不含业务逻辑
├── upstream_rag.py          ← adalflow.Document ↔ deepwiki.Document
└── upstream_data.py         ← 参数格式适配
```

**不复用的部分**:
- `api/api.py` — FastAPI 路由层，被 deepwiki-cli 的 CLI 层替代
- `api/openai_client.py` 等 7 个 provider client — 被 litellm 统一替代
- adalflow 框架本身 — 作为 `[upstream]` 可选依赖，不强制要求

**同步方式**:
```bash
git submodule update --remote vendor/deepwiki-open  # 拉取上游所有改进
pytest tests/unit/test_adapters.py                  # 验证适配层契约未破坏
```

> **治理边界**：`vendor/deepwiki-open/` 是只读引用，任何情况下不得直接修改其中文件。
> 若必须修改，优先顺序为：适配层 → 向上游提 PR → Fork 管理。
> 详见 [ADR-001 §上游源码治理政策](ADR-001-deepwiki-open-integration.md)。

## 4. Data Models

### 4.1 Core Domain Objects

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Repository  │────►│  Document   │────►│   Chunk     │
│             │  1:N │             │  1:N │             │
│ url         │     │ text        │     │ text        │
│ local_path  │     │ file_path   │     │ chunk_id    │
│ repo_type   │     │ file_type   │     │ embedding   │
│ commit_sha  │     │ is_code     │     │ metadata    │
│ branch      │     │ token_count │     │ doc_ref     │
└─────────────┘     └─────────────┘     └─────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  WikiResult  │────►│  WikiPage   │────►│  Diagram    │
│             │  1:N │             │  1:N │             │
│ title       │     │ id          │     │ title       │
│ description │     │ title       │     │ mermaid_code│
│ pages[]     │     │ content     │     │ diagram_type│
│ metadata    │     │ file_paths[]│     │             │
└─────────────┘     │ importance  │     └─────────────┘
                    │ related[]   │
                    │ diagrams[]  │
                    └─────────────┘

┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐
│CompletionRequest│  │CompletionResponse│  │  AgentContext     │
│                 │  │                  │  │                   │
│ messages[]      │  │ content          │  │ agent_name        │
│ model           │  │ model            │  │ agent_version     │
│ provider        │  │ provider         │  │ model             │
│ temperature     │  │ usage            │  │ api_key           │
│ top_p           │  │ raw_response     │  │ api_base          │
│ max_tokens      │  │                  │  │ provider          │
│ stream          │  │                  │  │ passthrough_avail │
└─────────────────┘  └─────────────────┘  └──────────────────┘
```

### 4.2 Configuration Model

```
DeepWikiConfig
├── provider: ProviderConfig
│   ├── name: str           # "openai" | "google" | "ollama" | ...
│   ├── model: str          # "gpt-4o" | "gemini-2.5-flash" | ...
│   ├── api_key: str?
│   ├── api_base: str?
│   ├── temperature: float  # default 0.7
│   └── top_p: float        # default 0.8
├── embedder: EmbedderConfig
│   ├── provider: str       # "openai" | "google" | "ollama"
│   ├── model: str          # "text-embedding-3-small"
│   ├── dimensions: int     # default 256
│   └── batch_size: int     # default 500
├── rag: RAGConfig
│   ├── top_k: int          # default 20
│   ├── chunk_size: int     # default 350
│   ├── chunk_overlap: int  # default 100
│   └── vector_store: str   # "chromadb" | "faiss"
├── output: OutputConfig
│   ├── format: str         # "terminal" | "json" | "markdown"
│   ├── language: str       # "en" | "zh" | "ja" | ...
│   ├── color: bool         # default true
│   └── stream: bool        # default true
├── cache_dir: Path
└── log_level: str          # default "INFO"
```

## 5. Error Handling Strategy

### 5.1 Exit Codes

| Code | Name | Description | Example |
|------|------|-------------|---------|
| 0 | SUCCESS | 操作成功完成 | Wiki 生成完成 |
| 1 | GENERAL_ERROR | 未分类的运行时错误 | 内部异常 |
| 2 | CONFIG_ERROR | 配置缺失或无效 | Missing API key |
| 3 | REPO_ERROR | 仓库访问失败 | Clone failed, auth denied |
| 4 | LLM_ERROR | LLM 调用失败 | API rate limit, model not found |
| 5 | EMBEDDING_ERROR | 嵌入或向量存储错误 | Embedding API failure |

### 5.2 Error Response Format (JSON mode)

```json
{
  "status": "error",
  "type": "config_error",
  "data": {
    "code": 2,
    "message": "OpenAI API key not configured",
    "hint": "Run 'deepwiki config init' or set OPENAI_API_KEY environment variable",
    "details": null
  }
}
```

### 5.3 Error Handling Principles

- **Fail fast**: 在 CLI 入口层验证所有前提条件（API key、git 可用性、仓库可访问性）
- **不吞异常**: 所有捕获的异常必须输出到 stderr 或 JSON error
- **可恢复提示**: 每个错误信息附带 `hint` 字段，告诉用户如何修复
- **API Key 安全**: 错误信息中遮掩 API Key（仅显示前 4 位 + `***`）
