# DeepWiki CLI - Technical Specification

> Version: 0.2.10 | Status: In Progress | Updated: 2026-04-07

---

## 1. CLI Interface Contract

### 1.1 Command Surface

```
deepwiki [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS] [ARGS]
```

### 1.2 Global Options

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--verbose` | `-v` | bool | false | 输出调试日志到 stderr |
| `--quiet` | `-q` | bool | false | 仅输出结果，抑制进度信息 |
| `--format` | `-f` | enum | terminal | 输出格式: `terminal` \| `json` \| `markdown` |
| `--json` | | bool | false | 等效于 `--format json` |
| `--config` | `-c` | path | null | 指定配置文件路径 |
| `--provider` | `-p` | string | null | LLM 提供商覆盖 |
| `--model` | `-m` | string | null | LLM 模型覆盖 |
| `--no-cache` | | bool | false | 跳过所有缓存 |
| `--version` | | bool | | 显示版本号 |
| `--help` | | bool | | 显示帮助信息 |

### 1.3 Commands Specification

#### 1.3.1 `deepwiki generate`

**Purpose**: 分析 Git 仓库，生成结构化 Wiki 文档。

```
deepwiki generate <REPO> [OPTIONS]

Arguments:
  REPO                     仓库路径或 URL (必填)
                           - 本地: ./my-repo, /absolute/path
                           - 远程: https://github.com/owner/repo
                           - 支持: github.com, gitlab.com, bitbucket.org

Options:
  --embed-provider TEXT    Embedding 提供商 (默认从配置读取)
  --embed-model TEXT       Embedding 模型 (默认从配置读取)
  --language, -l TEXT      输出语言 [default: en]
  --output-dir, -o PATH   输出目录 (仅 markdown 格式时生效)
  --include-dirs TEXT      仅包含指定目录 (逗号分隔)
  --exclude-dirs TEXT      排除指定目录 (逗号分隔)
  --include-files TEXT     仅包含指定文件模式 (glob, 逗号分隔)
  --exclude-files TEXT     排除指定文件模式 (glob, 逗号分隔)
  --token TEXT             私有仓库访问令牌
  --repo-type TEXT         仓库类型: github|gitlab|bitbucket [default: auto-detect]
  --max-pages INT          最大 Wiki 页数 [default: 20]
  --no-diagrams            跳过 Mermaid 图表生成
  --stream / --no-stream   启用/禁用流式输出 [default: stream]
```

**Exit codes**: 0 (success), 2 (config error), 3 (repo error), 4 (LLM error)

**Output contract (JSON mode)**:
```json
{
  "status": "success",
  "type": "wiki",
  "data": {
    "title": "string",
    "description": "string",
    "pages": [
      {
        "id": "string (slug)",
        "title": "string",
        "content": "string (markdown)",
        "file_paths": ["string"],
        "importance": "high | medium | low",
        "related_pages": ["string (id)"],
        "diagrams": [
          {
            "title": "string",
            "mermaid_code": "string",
            "diagram_type": "flowchart | sequence | class | state"
          }
        ]
      }
    ]
  },
  "metadata": {
    "repo": "string",
    "commit_sha": "string",
    "provider": "string",
    "model": "string",
    "language": "string",
    "duration_ms": 12345,
    "tokens_used": { "prompt": 1000, "completion": 2000 },
    "pages_generated": 10,
    "files_analyzed": 150
  }
}
```

#### 1.3.2 `deepwiki ask`

**Purpose**: 基于 RAG 回答关于仓库代码的问题。

```
deepwiki ask <REPO> <QUESTION> [OPTIONS]

Arguments:
  REPO                     仓库路径或 URL (必填)
  QUESTION                 自然语言问题 (必填)

Options:
  --embed-provider TEXT    Embedding 提供商
  --embed-model TEXT       Embedding 模型
  --token TEXT             私有仓库访问令牌
  --repo-type TEXT         仓库类型
  --top-k INT              检索结果数量 [default: 20]
  --context-files TEXT     额外上下文文件路径 (逗号分隔)
  --stream / --no-stream   启用/禁用流式输出 [default: stream]
```

**Exit codes**: 0 (success), 2 (config error), 3 (repo error), 4 (LLM error), 5 (embedding error)

**Output contract (JSON mode)**:
```json
{
  "status": "success",
  "type": "answer",
  "data": {
    "answer": "string (markdown)",
    "sources": [
      {
        "file_path": "string",
        "chunk_preview": "string (first 200 chars)",
        "relevance_score": 0.95
      }
    ]
  },
  "metadata": {
    "repo": "string",
    "question": "string",
    "provider": "string",
    "model": "string",
    "top_k": 20,
    "chunks_retrieved": 20,
    "index_cached": true,
    "duration_ms": 5000,
    "tokens_used": { "prompt": 3000, "completion": 500 }
  }
}
```

#### 1.3.3 `deepwiki research`

**Purpose**: 多轮迭代深度研究某个主题。

```
deepwiki research <REPO> <TOPIC> [OPTIONS]

Arguments:
  REPO                     仓库路径或 URL (必填)
  TOPIC                    研究主题 (必填)

Options:
  --embed-provider TEXT    Embedding 提供商
  --embed-model TEXT       Embedding 模型
  --iterations, -n INT     研究迭代次数 [default: 3]
  --token TEXT             私有仓库访问令牌
  --output-dir, -o PATH   报告输出目录
  --stream / --no-stream   启用/禁用流式输出 [default: stream]
```

**Output contract (JSON mode)**:
```json
{
  "status": "success",
  "type": "research",
  "data": {
    "topic": "string",
    "summary": "string (markdown)",
    "iterations": [
      {
        "iteration": 1,
        "question": "string",
        "findings": "string (markdown)",
        "follow_up_questions": ["string"]
      }
    ],
    "conclusion": "string (markdown)",
    "sources": [{ "file_path": "string", "relevance_score": 0.9 }]
  },
  "metadata": {
    "repo": "string",
    "iterations_completed": 3,
    "provider": "string",
    "model": "string",
    "duration_ms": 30000,
    "tokens_used": { "prompt": 10000, "completion": 5000 }
  }
}
```

#### 1.3.4 `deepwiki export`

```
deepwiki export <REPO> [OPTIONS]

Options:
  --format TEXT            导出格式: markdown|json [default: markdown]
  --output-dir, -o PATH   输出目录 [default: ./deepwiki-export/]
  --language, -l TEXT      导出语言 [default: en]
  --token TEXT             私有仓库访问令牌
```

**Markdown 导出目录结构**:
```
deepwiki-export/
├── README.md              # Wiki 首页 (title + description + TOC)
├── 01-architecture.md     # 按重要性排序的页面
├── 02-data-model.md
├── ...
├── diagrams/
│   ├── architecture.mmd   # Mermaid 源文件
│   └── data-flow.mmd
└── metadata.json          # 生成元数据
```

#### 1.3.5 `deepwiki config`

```
deepwiki config show                     # 显示当前配置 (带来源标注)
deepwiki config set <KEY> <VALUE>        # 设置配置项到用户配置文件
deepwiki config init                     # 交互式配置向导
deepwiki config providers                # 列出所有可用提供商及模型
deepwiki config path                     # 显示配置文件路径
```

**`config show` 输出示例**:
```
Provider:  openai (from: env DEEPWIKI_PROVIDER)
Model:     gpt-4o (from: user config ~/.config/deepwiki/config.yaml)
Embed:     text-embedding-3-small (from: default)
API Key:   sk-proj-****Xm2F (from: env OPENAI_API_KEY)
Cache Dir: ~/.cache/deepwiki (from: default)
Format:    terminal (from: default)
```

#### 1.3.6 `deepwiki serve`

```
deepwiki serve [OPTIONS]

Options:
  --host TEXT              绑定地址 [default: 0.0.0.0]
  --port INT               端口号 [default: 8001]
  --reload                 开发模式自动重载
  --cors-origins TEXT      允许的 CORS 来源 (逗号分隔)
```

**REST API Endpoints** (与 deepwiki-open 兼容):

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | 健康检查 |
| POST | `/api/generate` | 生成 Wiki |
| POST | `/api/ask` | RAG 问答 |
| POST | `/api/research` | 深度研究 |
| GET | `/api/providers` | 可用提供商列表 |
| GET | `/api/models/{provider}` | 指定提供商的模型列表 |

#### 1.3.7 `deepwiki repl`

```
deepwiki repl <REPO> [OPTIONS]

Options:
  --embed-provider TEXT    Embedding 提供商
  --embed-model TEXT       Embedding 模型
  --token TEXT             私有仓库访问令牌
```

**REPL 内置命令**:

| Command | Description |
|---------|-------------|
| `/help` | 显示帮助 |
| `/clear` | 清除对话历史 |
| `/context` | 显示当前索引状态 |
| `/export [path]` | 导出对话历史为 Markdown |
| `/model <provider> <model>` | 切换模型 |
| `/quit` or `Ctrl+D` | 退出 REPL |

---

## 2. Provider Abstraction Interface

### 2.1 BaseLLMProvider (Abstract)

```python
class BaseLLMProvider(ABC):
    """所有 LLM 提供商的统一接口。"""

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """非流式 completion。"""
        ...

    @abstractmethod
    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """流式 completion，yield 文本片段。"""
        ...

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """批量文本嵌入。"""
        ...

    @abstractmethod
    def supports_streaming(self) -> bool: ...

    @abstractmethod
    def supports_embedding(self) -> bool: ...
```

### 2.2 Request/Response Data Models

```python
@dataclass
class CompletionRequest:
    messages: list[dict[str, str]]   # [{"role": "system"|"user"|"assistant", "content": "..."}]
    model: str                       # 模型标识符
    provider: str                    # 提供商标识符
    temperature: float = 0.7
    top_p: float = 0.8
    max_tokens: int | None = None
    stream: bool = True
    extra_kwargs: dict[str, Any] = field(default_factory=dict)

@dataclass
class CompletionResponse:
    content: str
    model: str
    provider: str
    usage: dict | None = None        # {"prompt_tokens": N, "completion_tokens": N}
    raw_response: Any | None = None

@dataclass
class EmbeddingRequest:
    texts: list[str]                 # 待嵌入文本列表
    model: str
    provider: str

@dataclass
class EmbeddingResponse:
    embeddings: list[list[float]]    # N x D 嵌入向量
    model: str
    dimensions: int                  # 向量维度
```

### 2.3 litellm Provider Mapping

| Provider ID | litellm Prefix | Model Example | Env Var (API Key) |
|-------------|---------------|---------------|-------------------|
| `openai` | *(none)* | `gpt-4o` | `OPENAI_API_KEY` |
| `google` | `gemini/` | `gemini/gemini-2.5-flash` | `GOOGLE_API_KEY` |
| `anthropic` | `anthropic/` | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| `ollama` | `ollama/` | `ollama/llama3` | *(none, uses OLLAMA_HOST)* |
| `openrouter` | `openrouter/` | `openrouter/meta-llama/llama-3-70b` | `OPENROUTER_API_KEY` |
| `azure` | `azure/` | `azure/gpt-4o` | `AZURE_API_KEY` + `AZURE_API_BASE` |
| `bedrock` | `bedrock/` | `bedrock/anthropic.claude-3-sonnet` | AWS credentials |
| `openai-compat` | *(none)* | `qwen-plus` | `OPENAI_API_KEY` + `OPENAI_BASE_URL` |
| `kimi` | *(none, openai-compat)* | `kimi-k2.5` | `OPENAI_API_KEY` + `OPENAI_BASE_URL=https://api.kimi.com/coding/v1` |
| `glm` | *(none, openai-compat)* | `glm-4.7` | `OPENAI_API_KEY` + `OPENAI_BASE_URL=https://api.z.ai/api/paas/v4` |

> **Kimi**: Moonshot AI 的编程专用端点，支持 kimi-k2 / kimi-k2.5（256K context，视觉理解）。
> litellm 原生支持 `moonshot/` prefix，亦可用 `openai-compat` 通道。
>
> **GLM (Z.AI)**: 智谱 AI GLM 模型，提供两种接入模式（见下方 2.3a）：
> - OpenAI-compat 模式: 直接指定 GLM 模型名
> - Anthropic-compat 模式: 用 Claude 模型名，Z.AI 服务端做模型映射

#### 2.3a GLM Anthropic-compat 模式 (特殊)

Z.AI 提供 Anthropic 协议兼容端点，专为 Claude Code 等 Anthropic SDK 用户设计。
在此模式下发送 Claude 模型名，Z.AI 服务端自动映射到 GLM 模型：

| Claude Model (请求) | Z.AI 映射目标 |
|--------------------|--------------|
| `claude-opus-*` | `glm-4.7` |
| `claude-sonnet-*` | `glm-4.7` |
| `claude-haiku-*` | `glm-4.5-air` |

配置方式（等效于 Claude Code 的 settings.json 配置）：
```
ANTHROPIC_API_KEY  = <z.ai_api_key>
ANTHROPIC_BASE_URL = https://api.z.ai/api/anthropic
# 中国区: https://open.bigmodel.cn/api/anthropic
provider = anthropic
model    = claude-sonnet-4-20250514   # Z.AI 服务端映射到 glm-4.7
```

> litellm 支持 `anthropic/` provider 传入自定义 `api_base`，此模式可直接通过
> `LiteLLMProvider(provider="anthropic", api_base=ANTHROPIC_BASE_URL)` 实现。

### 2.4 Embedding Provider Mapping

| Provider | Model | Dimensions | Notes |
|----------|-------|-----------|-------|
| `openai` | `text-embedding-3-small` | 256 | 默认，高性价比 |
| `openai` | `text-embedding-3-large` | 1024 | 更高精度 |
| `google` | `text-embedding-004` | 768 | Google AI |
| `ollama` | `nomic-embed-text` | 768 | 本地运行 |
| `ollama` | `mxbai-embed-large` | 1024 | 本地高精度 |

---

## 3. Vector Store Interface

### 3.1 BaseVectorStore (Abstract)

```python
class BaseVectorStore(ABC):
    """向量存储统一接口。"""

    @abstractmethod
    def add_documents(self, documents: list[Document]) -> None:
        """添加已嵌入的文档到索引。"""

    @abstractmethod
    def query(self, embedding: list[float], top_k: int = 20,
              filter_metadata: dict | None = None) -> list[Document]:
        """相似度检索，返回 top_k 最相关文档。"""

    @abstractmethod
    def persist(self, path: str | None = None) -> None:
        """持久化索引到磁盘。"""

    @abstractmethod
    def load(self, path: str) -> bool:
        """从磁盘加载索引。返回 True 如果加载成功。"""

    @abstractmethod
    def count(self) -> int:
        """返回索引中的文档数量。"""

    @abstractmethod
    def clear(self) -> None:
        """清空索引。"""
```

### 3.2 实现选型

| Backend | Class | Dependency | Persistence | Use Case |
|---------|-------|-----------|-------------|----------|
| ChromaDB | `ChromaVectorStore` | `chromadb` (required) | 内置 `PersistentClient` | 默认 — CLI 嵌入式使用 |
| FAISS | `FAISSVectorStore` | `faiss-cpu` (optional) | 手动 pickle + numpy | 可选 — 高性能场景 |

### 3.3 Cache Key Strategy

向量索引缓存路径:
```
{cache_dir}/indexes/{cache_key}/
    ├── chroma.sqlite3       # ChromaDB 持久化文件
    ├── metadata.json        # 索引元数据 (commit_sha, file_count, timestamp)
    └── *.bin                # ChromaDB 内部文件

cache_key = sha256(repo_url + ":" + branch + ":" + commit_sha[:8])[:16]
```

**缓存失效条件**:
- `commit_sha` 变化 (有新提交)
- `--no-cache` 标志
- 手动删除缓存目录
- 嵌入模型变更 (存储在 metadata.json 中比对)

---

## 4. Configuration System

### 4.1 Priority Chain (高优先级在上)

```
┌─────────────────────────────────────────────────────┐
│ Level 1: CLI Flags                                  │
│   deepwiki generate --provider openai --model gpt-4o│
├─────────────────────────────────────────────────────┤
│ Level 2: Environment Variables                      │
│   DEEPWIKI_PROVIDER=openai OPENAI_API_KEY=sk-...    │
├─────────────────────────────────────────────────────┤
│ Level 3: Project Config                             │
│   ./.deepwiki/config.yaml (repo root)               │
├─────────────────────────────────────────────────────┤
│ Level 4: User Config                                │
│   ~/.config/deepwiki/config.yaml (Linux)            │
│   ~/Library/Application Support/deepwiki/ (macOS)   │
│   %APPDATA%/deepwiki/config.yaml (Windows)          │
├─────────────────────────────────────────────────────┤
│ Level 5: Built-in Defaults                          │
│   src/deepwiki/config/defaults.py                   │
│   src/deepwiki/config/generator.json                │
└─────────────────────────────────────────────────────┘
```

### 4.2 Config File Format

```yaml
# ~/.config/deepwiki/config.yaml

provider:
  name: openai
  model: gpt-4o
  temperature: 0.7
  top_p: 0.8
  # api_key: 不建议写在文件中，优先使用环境变量

embedder:
  provider: openai
  model: text-embedding-3-small
  dimensions: 256
  batch_size: 500

rag:
  top_k: 20
  chunk_size: 350
  chunk_overlap: 100
  vector_store: chromadb

output:
  format: terminal
  language: zh
  color: true
  stream: true

log_level: INFO
```

### 4.3 Environment Variable Mapping

| Environment Variable | Config Path | Notes |
|---------------------|-------------|-------|
| `DEEPWIKI_PROVIDER` | `provider.name` | |
| `DEEPWIKI_MODEL` | `provider.model` | |
| `DEEPWIKI_EMBED_PROVIDER` | `embedder.provider` | |
| `DEEPWIKI_EMBED_MODEL` | `embedder.model` | |
| `DEEPWIKI_FORMAT` | `output.format` | |
| `DEEPWIKI_LANGUAGE` | `output.language` | |
| `DEEPWIKI_CACHE_DIR` | `cache_dir` | |
| `DEEPWIKI_CONFIG_DIR` | *(special)* | 覆盖用户配置目录 |
| `DEEPWIKI_LOG_LEVEL` | `log_level` | |
| `OPENAI_API_KEY` | `provider.api_key` | 当 provider=openai |
| `GOOGLE_API_KEY` | `provider.api_key` | 当 provider=google |
| `ANTHROPIC_API_KEY` | `provider.api_key` | 当 provider=anthropic |
| `ANTHROPIC_BASE_URL` | `provider.api_base` | 当 provider=anthropic；用于 Z.AI GLM Anthropic-compat 模式、其他 Anthropic-compatible 代理 |
| `OPENROUTER_API_KEY` | `provider.api_key` | 当 provider=openrouter |
| `AZURE_API_KEY` | `provider.api_key` | 当 provider=azure |
| `AZURE_API_BASE` | `provider.api_base` | 当 provider=azure |
| `OLLAMA_HOST` | `provider.api_base` | 当 provider=ollama, default `http://localhost:11434` |
| `OPENAI_BASE_URL` | `provider.api_base` | OpenAI 兼容端点；Kimi (`https://api.kimi.com/coding/v1`)、GLM OpenAI 模式 (`https://api.z.ai/api/paas/v4`)、Qwen 等 |

### 4.4 API Key Resolution Logic

```
resolve_api_key(provider_name, cli_override, config):
  1. If cli_override is not None → return cli_override
  2. If config.provider.api_key is not None → return config.provider.api_key
  3. Match provider_name to standard env var:
     openai      → OPENAI_API_KEY
     google      → GOOGLE_API_KEY
     anthropic   → ANTHROPIC_API_KEY
     openrouter  → OPENROUTER_API_KEY
     azure       → AZURE_API_KEY
     ollama      → None (no key needed)
     bedrock     → None (uses AWS credential chain)
  4. If still None and provider requires key → raise ConfigError(exit_code=2)
```

---

## 5. Agent Integration Protocol

### 5.1 Agent Detection

`AgentDetector` 按以下顺序检测父 Agent 环境，首次匹配即返回:

```
Detection Order:
  1. DEEPWIKI_AGENT_NAME env var    → Generic (user-configured) agent
  2. CLAUDE_CODE == "1"             → Claude Code
  3. CURSOR_SESSION present         → Cursor
  4. GITHUB_COPILOT present         → GitHub Copilot
  5. AIDER_MODEL present            → aider
  6. (none matched)                 → No agent context
```

**重要**: 通用检测 (`DEEPWIKI_AGENT_*`) 优先级最高，因为用户显式配置应覆盖自动检测。

### 5.2 AgentContext Data Model

```python
@dataclass
class AgentContext:
    agent_name: str                    # 标识符
    agent_version: str | None          # 版本
    model: str | None                  # Agent 使用的模型
    api_key: str | None                # 可复用的 API Key
    api_base: str | None               # 自定义端点
    provider: str | None               # 提供商标识
    passthrough_available: bool        # 能否直通请求
    env_vars: dict[str, str]           # 检测到的相关环境变量
```

### 5.3 Agent Model Reuse Flow

```
deepwiki ask ./repo "question"
         │
         ▼
    CLI 解析参数
         │
         ├── --provider 指定? ──Yes──► 使用 CLI 指定的 provider
         │
         No
         │
         ▼
    AgentDetector.detect()
         │
         ├── 检测到 AgentContext? ──Yes──► context.passthrough_available?
         │                                      │
         │                                 Yes──┤──No──► 降级到配置文件
         │                                      │
         │                              使用 Agent 的
         │                              model + api_key + provider
         │
         No
         │
         ▼
    ConfigLoader.load()
         │
         ▼
    使用配置文件中的 provider
```

### 5.4 JSON Output Protocol (Agent Consumption)

**所有 JSON 输出遵循统一信封格式**:

```json
{
  "status": "success | error | streaming",
  "type": "wiki | answer | research | config | progress | error",
  "data": { },
  "metadata": { }
}
```

**进度事件** (输出到 stderr，不影响 stdout 的 JSON):
```json
{"status":"streaming","type":"progress","data":{"phase":"indexing","current":5,"total":20,"message":"Embedding documents 5/20"}}
{"status":"streaming","type":"progress","data":{"phase":"generating","current":3,"total":10,"message":"Generating page 3/10: Architecture"}}
```

**流式内容** (输出到 stdout，每行一个 JSON):
```json
{"status":"streaming","type":"chunk","data":{"content":"The authentication"}}
{"status":"streaming","type":"chunk","data":{"content":" module uses JWT"}}
{"status":"streaming","type":"done","data":{"content":""},"metadata":{...}}
```

### 5.5 SKILL.md Contract

遵循 CLI-Anything SKILL.md 规范:

```yaml
---
name: deepwiki
description: AI-powered wiki generator and code Q&A for git repositories
version: "0.1.0"
---
```

内容包含: 安装方式、所有命令的用法示例、Agent 使用指南（`--json`、退出码、环境变量配置）、输出格式说明。

---

## 6. Document Processing Pipeline

### 6.1 File Filter Rules

**默认包含的文件扩展名** (来源于 deepwiki-open 的 repo.json):

```
Code:  .py .js .ts .jsx .tsx .java .go .rs .c .cpp .h .hpp .cs
       .rb .php .swift .kt .scala .lua .r .m .pl .sh .bash
       .zig .nim .dart .ex .exs .clj .hs .erl .jl .v .sv

Docs:  .md .txt .rst .adoc .org

Config: .yaml .yml .json .toml .ini .cfg .env.example
        .xml .gradle .sbt

Build:  Makefile Dockerfile docker-compose.yml
        Cargo.toml go.mod pom.xml build.gradle
        package.json pyproject.toml setup.py setup.cfg
```

**默认排除的目录**:
```
node_modules  .git  __pycache__  .venv  venv  env
.tox  .mypy_cache  .pytest_cache  dist  build
.next  .nuxt  .output  target  vendor  Pods
.idea  .vscode  .DS_Store
```

**文件大小限制**:
- 代码文件: 最大 81920 tokens (8192 * 10)
- 文档文件: 最大 8192 tokens
- 估算方法: `len(content) / 4` (粗估 token 数) 或 tiktoken 精确计算

### 6.2 Text Splitting Strategy

```
Algorithm: Word-based splitting (不在词中间断开)

Parameters:
  chunk_size:    350 tokens (default, configurable via rag.chunk_size)
  chunk_overlap: 100 tokens (default, configurable via rag.chunk_overlap)

Metadata per chunk:
  - chunk_id:    "{file_path}::{chunk_index}"
  - file_path:   源文件相对路径
  - file_type:   "code" | "doc" | "config" | "build"
  - is_code:     bool
  - language:    编程语言 (从扩展名推断)
  - start_line:  起始行号
  - end_line:    结束行号
```

### 6.3 Embedding Pipeline

```
Documents ──► TextSplitter ──► Chunks[]
                                  │
                                  ▼ (batch_size=500)
                          EmbeddingProvider.embed()
                                  │
                                  ▼
                          Chunks with embeddings[]
                                  │
                                  ▼
                          VectorStore.add_documents()
                                  │
                                  ▼
                          VectorStore.persist()
```

**批处理**: 每批最多 500 个 chunk，避免 API 单次请求过大。

---

## 7. Wiki Generation Algorithm

### 7.1 Two-Phase Generation

```
Phase 1: Structure Planning (单次 LLM 调用)
  Input:  仓库文件树 + README 内容 + 关键配置文件摘要
  Output: Wiki 结构 JSON — 页面列表 (title, description, file_paths, importance)
  Model:  使用用户配置的 LLM

Phase 2: Page Generation (每页一次 LLM 调用, 可并发)
  Input:  页面定义 + 对应文件的完整内容
  Output: Markdown 格式的页面内容 + Mermaid 图表
  Model:  使用用户配置的 LLM
```

### 7.2 Structure Planning Prompt (概要)

```
System: You are a technical documentation expert. Analyze the repository 
        structure and create a wiki outline.

User:   Repository: {repo_name}
        File tree:
        {file_tree}
        
        README content:
        {readme_content}
        
        Generate a JSON wiki structure with pages covering:
        - Project overview and architecture
        - Key modules and their responsibilities  
        - Data models and relationships
        - Configuration and deployment
        - API/Interface documentation

Output format:
{
  "title": "...",
  "description": "...",
  "pages": [
    {
      "id": "slug-format",
      "title": "...",
      "description": "Brief description of what this page covers",
      "file_paths": ["src/auth/", "src/middleware/auth.py"],
      "importance": "high|medium|low"
    }
  ]
}
```

### 7.3 Page Generation Strategy

- **高重要性页面**: 包含完整文件内容作为上下文
- **中重要性页面**: 包含文件摘要 + 关键函数签名
- **低重要性页面**: 仅包含文件列表和 README 描述
- **图表生成**: 每个高/中重要性页面附带一个 Mermaid 图表

---

## 8. Cross-Platform Specifications

### 8.1 Path Conventions

| Item | Linux/macOS | Windows |
|------|-------------|---------|
| User config | `$XDG_CONFIG_HOME/deepwiki/` or `~/.config/deepwiki/` | `%APPDATA%\deepwiki\` |
| User cache | `$XDG_CACHE_HOME/deepwiki/` or `~/.cache/deepwiki/` | `%LOCALAPPDATA%\deepwiki\` |
| Project config | `{repo_root}/.deepwiki/config.yaml` | Same |
| Temp clone | `{cache_dir}/repos/{hash}/` | Same (under cache dir) |

### 8.2 Terminal Capability Detection

```python
def detect_terminal_capabilities():
    is_tty = sys.stdout.isatty()
    no_color = os.environ.get("NO_COLOR") is not None  # https://no-color.org/
    ci = os.environ.get("CI") is not None
    
    if not is_tty or no_color or ci:
        return TerminalMode.PLAIN      # 无色彩，无进度条
    
    if platform.system() == "Windows":
        # Windows Terminal 和新版 cmd 支持 ANSI
        if os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM"):
            return TerminalMode.FULL
        return TerminalMode.BASIC       # 旧版 cmd.exe
    
    return TerminalMode.FULL            # Linux/macOS 全功能
```

### 8.3 External Dependencies Check

CLI 启动时验证:
```
Required:
  - Python >= 3.10     (运行时保证)
  - git >= 2.20        (仓库克隆，检查 `git --version`)

Optional:
  - ollama             (本地模型，仅当 --provider ollama 时检查)
```

验证失败时输出友好错误:
```
Error: git is not installed or not in PATH.
Hint:  Install git from https://git-scm.com/downloads
       Linux: sudo apt install git
       macOS: brew install git
```

---

## 9. Dependencies

### 9.1 Required Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `typer[all]` | >= 0.12.0 | CLI 框架 (包含 Rich, shellingham) |
| `litellm` | >= 1.40.0 | 统一 LLM/Embedding 接口 |
| `chromadb` | >= 0.5.0 | 向量存储 |
| `tiktoken` | >= 0.7.0 | Token 计数 (用于文本分块) |
| `pydantic` | >= 2.0 | 数据验证和配置模型 |
| `pyyaml` | >= 6.0 | YAML 配置文件解析 |
| `httpx` | >= 0.27.0 | 异步 HTTP 客户端 (仓库元数据获取) |
| `prompt-toolkit` | >= 3.0 | REPL 交互支持 |
| `python-dotenv` | >= 1.0 | .env 文件加载 |
| `gitpython` | >= 3.1 | Git 仓库操作 |

### 9.2 Optional Dependencies

| Group | Package | Version | Purpose |
|-------|---------|---------|---------|
| `faiss` | `faiss-cpu` | >= 1.8.0 | FAISS 向量存储后端 |
| `server` | `fastapi` | >= 0.111.0 | HTTP API 服务 |
| `server` | `uvicorn` | >= 0.30.0 | ASGI 服务器 |
| `all` | *(above all)* | | 安装所有可选依赖 |

### 9.3 Python Version Constraint

```
requires-python = ">=3.10"
```

**理由**: 
- `match/case` 语法 (3.10+)
- `X | Y` 类型联合语法 (3.10+)
- 主流 OS 默认 Python 版本已满足
