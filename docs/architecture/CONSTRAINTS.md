# DeepWiki CLI - Constraints & Design Boundaries

> Version: 0.1.0 | Status: Draft | Updated: 2026-04-02

---

## 1. Technical Constraints

### 1.1 Language & Runtime

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| Language | Python 3.10+ | 与 deepwiki-open、CLI-Anything 一致；3.10 最低要求来自 `X \| Y` 类型语法 |
| Async Runtime | asyncio | LLM API 调用是 I/O bound，需异步执行；litellm 原生支持 async |
| 包管理 | pyproject.toml (PEP 621) | 现代 Python 打包标准，兼容 pip/poetry/hatch |
| 入口点 | `console_scripts` | `pip install` 后 `deepwiki` 命令全局可用 |

### 1.2 依赖约束

| Constraint | Detail |
|-----------|--------|
| **litellm 为唯一 LLM 客户端** | 不维护独立的 OpenAI/Google/Ollama 等客户端。所有 LLM 调用通过 litellm 路由。如果 litellm 不支持某个 provider，则该 provider 不被支持 |
| **不依赖 adalflow** | deepwiki-open 使用 adalflow 框架，但其与 deepwiki-cli 的架构不兼容（OllamaClient、OpenAIClient 等专有类型），不引入 |
| **不依赖浏览器引擎** | 不使用 Playwright/Puppeteer/Chromium。Mermaid 图表仅输出源代码，不渲染为图片（用户可通过外部工具渲染） |
| **ChromaDB 为必须依赖** | 向量存储是核心功能，ChromaDB 是默认后端。FAISS 为可选 |
| **无 C 编译依赖** | 所有 required dependencies 必须提供预编译 wheel，不要求用户本地有 C 编译器 |

### 1.3 不 Fork deepwiki-open

**决策**: 重新实现核心逻辑，不直接 fork 或 vendor deepwiki-open 代码。

**原因**:
1. adalflow 框架耦合 — 其 `Generator`、`Embedder`、`Retriever` 类型与我们的抽象层冲突
2. FastAPI 路由耦合 — 业务逻辑散布在 HTTP handler 中
3. Web session 状态 — 聊天历史依赖 Web session，不适合 CLI
4. 7 个独立 provider 客户端 — 被 litellm 单一抽象替代

**保留复用的资产** (以概念/逻辑层面复用，不复制代码):
- Prompt 模板设计思路 (wiki 结构规划、页面生成、RAG 问答)
- 文件过滤规则 (repo.json 中的扩展名列表、排除目录)
- 文本分块策略 (word-based, 350 token chunk, 100 overlap)
- Wiki 结构规划的两阶段方法 (先规划结构，再逐页生成)

---

## 2. Platform Constraints

### 2.1 操作系统兼容性

| OS | Version | Status | Notes |
|----|---------|--------|-------|
| Ubuntu | 20.04+ | Primary | CI 测试目标 |
| macOS | 12+ (Monterey) | Primary | 包含 Apple Silicon |
| Windows | 10/11 | Primary | 需要 Windows Terminal 以获最佳体验 |
| Alpine Linux | 3.18+ | Secondary | Docker 基础镜像 |
| Headless/CI | Any | Secondary | 自动禁用 Rich 渲染 |

### 2.2 文件系统约束

| Constraint | Detail |
|-----------|--------|
| **路径处理** | 全程使用 `pathlib.Path`，禁止字符串拼接路径 |
| **Windows 长路径** | 文档说明需开启 `LongPathsEnabled`；ChromaDB 持久化路径可能超 260 字符 |
| **文件编码** | 代码文件统一按 UTF-8 读取，遇到解码错误则跳过该文件 |
| **符号链接** | 不跟踪符号链接 (避免循环引用) |
| **大文件** | 单文件超过 81920 tokens 时跳过 (代码)，超过 8192 tokens 时跳过 (文档) |

### 2.3 终端约束

| Scenario | Behavior |
|----------|----------|
| TTY + 支持 ANSI | 完整 Rich 渲染 (Panel, Tree, Progress, Syntax) |
| TTY + 不支持 ANSI (旧 cmd.exe) | 纯文本 + 基础格式 |
| Non-TTY (管道/重定向) | 纯文本，无色彩，无进度条 |
| `NO_COLOR` 环境变量 | 遵循 [no-color.org](https://no-color.org/) 标准，禁用色彩 |
| `CI=true` 环境变量 | 等同于 Non-TTY |

---

## 3. Network Constraints

### 3.1 在线 vs 离线模式

```
┌─────────────────────────────────────────────────────────┐
│                     Network Modes                        │
│                                                          │
│  Full Online:                                            │
│    Provider: openai/google/openrouter/azure/bedrock     │
│    Embedding: openai/google                              │
│    Repo: remote URL (clone via HTTPS)                    │
│    Requires: Internet + API keys                         │
│                                                          │
│  Partial Offline:                                        │
│    Provider: ollama (local)                              │
│    Embedding: ollama/nomic-embed-text (local)            │
│    Repo: remote URL (clone requires internet)            │
│    Requires: Ollama running + initial clone              │
│                                                          │
│  Full Offline (Air-gapped):                              │
│    Provider: ollama (local)                              │
│    Embedding: ollama/nomic-embed-text (local)            │
│    Repo: local path only                                 │
│    Requires: Ollama running, no internet needed          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3.2 网络超时

| Operation | Timeout | Retries |
|-----------|---------|---------|
| Git clone | 120s | 1 (用户可手动重试) |
| LLM completion | 300s (由 litellm 控制) | 3 (litellm 内置) |
| Embedding batch | 120s | 3 |
| Ollama health check | 5s | 0 |

### 3.3 数据隐私

| Constraint | Detail |
|-----------|--------|
| **代码不持久上传** | 代码仅在 LLM API 调用时发送到提供商，不持久存储于任何第三方服务 |
| **Ollama 完全本地** | 使用 Ollama 时，代码永远不离开本机 |
| **缓存仅本地** | 向量索引、Wiki 缓存仅存储在用户本地文件系统 |
| **无遥测** | 不收集使用数据、不发送匿名统计 |
| **API Key 不日志** | API Key 不出现在日志、错误输出中；错误信息中使用 mask (`sk-p****Xm2F`) |

---

## 4. LLM Constraints

### 4.1 上下文窗口管理

| Model | Context Window | Strategy |
|-------|---------------|----------|
| GPT-4o | 128K tokens | 可放入大量文件内容 |
| Gemini 2.5 Flash | 1M tokens | 几乎不受限 |
| Claude Sonnet | 200K tokens | 充足 |
| Llama 3 (Ollama) | 8K tokens | 需严格控制上下文大小 |

**上下文控制策略**:
```
Wiki Structure Planning:
  - 输入: file_tree (通常 < 2K tokens) + README (< 4K tokens)
  - 总计: < 8K tokens → 所有模型安全

Page Generation:
  - 输入: page_def + file_contents
  - 对于大上下文模型: 完整文件内容
  - 对于小上下文模型 (< 16K): 仅包含文件摘要 + 关键函数签名
  - 自动裁剪: 如果总 token 数超过 model_context * 0.6，截断文件内容

RAG Q&A:
  - 固定: top_k=20 chunks × 350 tokens = ~7K tokens
  - 加上 system prompt + question: ~8K tokens total
  - 在所有模型上下文范围内
```

### 4.2 Embedding 维度约束

| Embedding Model | Dimensions | Storage per 1K chunks |
|-----------------|-----------|----------------------|
| text-embedding-3-small (dim=256) | 256 | ~1 MB |
| text-embedding-3-large (dim=1024) | 1024 | ~4 MB |
| text-embedding-004 | 768 | ~3 MB |
| nomic-embed-text (Ollama) | 768 | ~3 MB |

**约束**: 不同 embedding model 的索引不可互换。切换 embedding model 时必须重建索引（通过 metadata.json 中的 embed_model 字段检测）。

### 4.3 Rate Limit Handling

依赖 litellm 内置的 rate limit 处理:
- 自动重试 (exponential backoff, 最多 3 次)
- 429 响应时读取 `Retry-After` header
- 并发控制通过 `asyncio.Semaphore` (embedding: 3, generation: 2)

---

## 5. Performance Constraints

### 5.1 资源上限

| Resource | Limit | Enforcement |
|----------|-------|-------------|
| 内存峰值 | 2 GB | ChromaDB 内存映射文件；大批量 embedding 分批处理 |
| 磁盘 (缓存) | 无硬限制 | 每个仓库索引约 5-50 MB；可通过 `--no-cache` 或手动清理 |
| 并发 HTTP | 20 连接 | httpx connection pool limit |
| 并发 LLM | 2 请求 | Semaphore(2)，避免 rate limit |
| 并发 Embedding | 3 请求 | Semaphore(3) |
| CLI 启动时间 | < 2s | 延迟导入重量级依赖 (chromadb, litellm) |

### 5.2 延迟导入策略

```python
# 重量级依赖在使用时才导入，不在顶层
# 好处: `deepwiki --help` 和 `deepwiki config show` 秒级响应

# 延迟导入:
import chromadb          # ~500ms import time
import litellm           # ~300ms import time
import tiktoken          # ~200ms import time

# 即时导入:
import typer             # CLI 框架，必须
import pydantic          # 配置加载，快速
import pathlib           # 标准库
import yaml              # 配置文件
```

---

## 6. Scope Boundaries (v0.1)

### 6.1 In Scope

- 单仓库分析 (本地路径或远程 URL)
- Wiki 生成 (结构化 Markdown)
- RAG 问答 (单问题 + REPL 多轮)
- 多轮研究
- 7+ LLM 提供商
- 完全离线运行 (Ollama)
- Agent 模型复用
- JSON/Terminal/Markdown 输出
- 缓存系统 (向量索引 + Wiki 结果)

### 6.2 Out of Scope (v0.1)

| Feature | Reason | Future Consideration |
|---------|--------|---------------------|
| Web UI | CLI 工具，不需要前端 | v1.0 可考虑 TUI (Textual) |
| 多仓库同时分析 | 增加复杂度，优先单仓库体验 | v0.3 |
| 实时 Git 监听 | 不是 daemon 进程 | v0.5 作为 watch 模式 |
| Mermaid → PNG 渲染 | 需要浏览器引擎或额外二进制 | 推荐用户使用 mermaid-cli |
| 用户认证/权限 | 单用户 CLI 工具 | serve 模式 v0.5 可考虑 |
| 插件系统 | 过早抽象 | v1.0 评估需求 |
| 非 Git 仓库 | 专注 Git 生态 | 无计划 |
| 二进制文件分析 | 文本工具，不处理二进制 | 无计划 |

### 6.3 Explicit Non-Goals

- **不替代 deepwiki-open**: 目标是互补 (CLI vs Web)，不是替代
- **不构建通用 RAG 框架**: RAG 是内部实现细节，不暴露为库
- **不构建 LLM 框架**: 使用 litellm，不重复造轮子
- **不追求完美文档**: Wiki 质量依赖 LLM 能力，工具只负责编排
