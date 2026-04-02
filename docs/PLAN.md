# DeepWiki CLI - Implementation Plan

> Version: 0.1.0 | Status: Draft | Updated: 2026-04-02

---

## 1. Document Map

```
docs/
├── PRD.md                          # 产品需求: 做什么、为谁做、验收标准
├── PLAN.md                         # 实施计划: 分阶段里程碑、依赖关系 (本文件)
├── specs/
│   └── TECHNICAL_SPEC.md           # 技术规格: CLI 接口契约、API 定义、数据模型
└── architecture/
    ├── ARCHITECTURE.md             # 逻辑架构: 分层职责、模块划分、设计决策
    ├── DATA_FLOW.md                # 数据流: 各命令的完整数据流转、缓存、流式传输
    └── CONSTRAINTS.md              # 约束条件: 技术/平台/网络/性能/范围边界
```

**文档间关系**:
```
PRD (What & Why)
 │
 ├──► ARCHITECTURE (How - 逻辑结构)
 │     └──► DATA_FLOW (How - 运行时行为)
 │
 ├──► TECHNICAL_SPEC (Contract - 精确接口定义)
 │
 ├──► CONSTRAINTS (Boundaries - 不做什么、限制条件)
 │
 └──► PLAN (When & Order - 实施路线) ← 你在这里
```

---

## 2. Technology Stack Summary

| Layer | Choice | Package |
|-------|--------|---------|
| CLI Framework | Typer | `typer[all]>=0.12.0` |
| LLM Interface | litellm | `litellm>=1.40.0` |
| Vector Store | ChromaDB | `chromadb>=0.5.0` |
| Token Count | tiktoken | `tiktoken>=0.7.0` |
| Config Model | Pydantic | `pydantic>=2.0` |
| Config File | YAML | `pyyaml>=6.0` |
| HTTP Client | httpx | `httpx>=0.27.0` |
| REPL | prompt-toolkit | `prompt-toolkit>=3.0` |
| Env Loading | dotenv | `python-dotenv>=1.0` |
| Git | gitpython | `gitpython>=3.1` |
| Terminal UI | Rich | *(included via typer[all])* |

---

## 3. Implementation Phases

### Phase 1: Foundation — 最小可用 CLI

**目标**: 一条命令从本地仓库生成 Wiki，终端输出。

**交付物**:

| # | File | Description | Depends On |
|---|------|-------------|------------|
| 0 | `vendor/deepwiki-open/` (git submodule) | `git submodule add https://github.com/AsyncFuncAI/deepwiki-open`；**只读引用，不得修改 `vendor/` 内任何文件**；治理政策见 [ADR-001](architecture/ADR-001-deepwiki-open-integration.md) | — |
| 1 | `pyproject.toml` | 包配置、依赖声明、entry_points；新增 `[upstream]` 可选依赖组 | — |
| 2 | `src/deepwiki/__init__.py` | 包根、版本号 | — |
| 3 | `src/deepwiki/__main__.py` | `python -m deepwiki` 入口 | 2 |
| 4 | `src/deepwiki/config/defaults.py` | 内置默认配置值 | — |
| 5 | `src/deepwiki/config/settings.py` | Pydantic 配置模型 + ConfigLoader (仅支持 Level 2 + Level 5) | 4 |
| 6 | `src/deepwiki/config/generator.json` |  LLM 模型预设 symlink → `vendor/deepwiki-open/api/config/generator.json` | 0 |
| 7 | `src/deepwiki/config/embedder.json` | Embedding 模型预设 symlink → `vendor/deepwiki-open/api/config/embedder.json` | 0 |
| 8 | `src/deepwiki/config/repo.json` | 文件过滤规则 symlink → `vendor/deepwiki-open/api/config/repo.json` | 0 |
| 9 | `src/deepwiki/providers/base.py` | BaseLLMProvider 抽象 + Request/Response dataclass | — |
| 10 | `src/deepwiki/providers/litellm_provider.py` | litellm 统一实现 (complete + stream) | 9 |
| 11 | `src/deepwiki/data/repo_manager.py` | 本地仓库解析 (无 clone，仅路径验证) | — |
| 12 | `src/deepwiki/data/document_reader.py` | 文件遍历 + 读取 + Document 构建 | 8 |
| 13 | `src/deepwiki/core/prompts.py` | Wiki 结构规划 + 页面生成的 prompt 模板 从 `vendor/deepwiki-open/api/prompts.py` 直接 import + 补充 wiki-generate 专用模板 | 0 |
| 14 | `src/deepwiki/core/wiki_generator.py` | 两阶段 Wiki 生成 (结构规划 + 内容生成) | 9, 12, 13 |
| 15 | `src/deepwiki/output/formatter.py` | OutputFormatter 协议 + 工厂函数 | — |
| 16 | `src/deepwiki/output/terminal.py` | Rich 终端渲染 | 15 |
| 17 | `src/deepwiki/cli/callbacks.py` | 全局选项解析、provider 初始化 | 5, 10 |
| 18 | `src/deepwiki/cli/app.py` | Typer 根应用 + generate 子命令注册 | 17 |
| 19 | `src/deepwiki/cli/generate.py` | `deepwiki generate` 命令实现 | 14, 16, 18 |

**依赖图**:
```
pyproject.toml ─────────────────────────────────────┐
__init__.py ──► __main__.py                         │
                                                     │
defaults.py ──► settings.py ──► callbacks.py ──► app.py ──► generate.py
                                     │                          │
generator.json                       │                          │
embedder.json                        │                          │
                                     │                          │
base.py ──► litellm_provider.py ─────┘                          │
                                                                │
repo.json ──► document_reader.py ──┐                            │
                                    ├──► wiki_generator.py ─────┘
repo_manager.py ───────────────────┘         │
                                              │
prompts.py ──────────────────────────────────┘
                                              
formatter.py ──► terminal.py ─────────────────────► generate.py
```

**里程碑**:
```bash
pip install -e .
deepwiki generate ./my-repo --provider openai
# → 终端输出 Wiki (Rich Panel + Tree + Markdown)
```

**验证**:
```bash
# 基础功能验证
deepwiki --help                              # 显示帮助
deepwiki --version                           # 显示版本
deepwiki generate ./my-repo --provider openai # 生成 Wiki
deepwiki generate ./my-repo --provider ollama --model llama3  # 本地模型
```

---

### Phase 2: RAG + Q&A — 向量检索问答

**目标**: 完整 RAG 流水线，支持向量索引缓存，JSON 输出。

**交付物**:

| # | File | Description | Depends On |
|---|------|-------------|------------|
| 20 | `src/deepwiki/data/text_splitter.py` | 文本分块 (word-based) | — |
| 21 | `src/deepwiki/data/vector_store.py` | BaseVectorStore + ChromaVectorStore | — |
| 22 | `src/deepwiki/data/cache_manager.py` | 缓存键计算、索引缓存验证、存取 | 21 |
| 23 | `src/deepwiki/providers/embedder.py` | Embedding 抽象 (复用 litellm) | 10 |
| 24 | `src/deepwiki/core/rag_engine.py` | 完整 RAG 流水线: index + query + answer | 20, 21, 23 |
| 25 | `src/deepwiki/output/json_output.py` | JSON 格式化输出 (stdout/stderr 分离) | 15 |
| 26 | `src/deepwiki/output/markdown_output.py` | Markdown 文件输出 | 15 |
| 27 | `src/deepwiki/cli/ask.py` | `deepwiki ask` 命令 | 24, 25 |
| 28 | 更新 `settings.py` | 添加 Level 3/4 配置文件支持 | 5 |
| 29 | 更新 `app.py` | 注册 ask 子命令 | 18 |

**里程碑**:
```bash
deepwiki ask ./my-repo "How does authentication work?" --json
# → JSON 结构化回答 + sources 引用

deepwiki ask ./my-repo "Explain the data model" 
# → 终端流式输出回答
# → 第二次调用命中缓存索引，跳过嵌入步骤
```

---

### Phase 3: Agent + Multi-Provider — Agent 集成与多平台

**目标**: Agent 模型复用、REPL 交互、深度研究、完整配置管理。

**交付物**:

| # | File | Description | Depends On |
|---|------|-------------|------------|
| 30 | `src/deepwiki/adapters/upstream_rag.py` | `UpstreamRAGAdapter`：将 `vendor/.../rag.py::RAG` 映射到 deepwiki-cli 接口；类型转换 adalflow.Document ↔ deepwiki.Document | 0 |
| 30b | `src/deepwiki/adapters/upstream_data.py` | `data_pipeline.py` 函数适配层（参数格式 + 类型转换） | 0 |
| 30c | `tests/unit/test_adapters.py` | 适配层契约测试（防止上游 API 变化静默破坏适配） | 30, 30b |
| 31 | `src/deepwiki/agent/detector.py` | AgentDetector: 6 种 Agent 检测策略 | — |
| 31 | `src/deepwiki/agent/protocol.py` | Agent JSON 通信协议定义 | — |
| 32 | `src/deepwiki/agent/skill.py` | SKILL.md 生成辅助 | — |
| 33 | `src/deepwiki/agent/proxy.py` | Agent 模型直通 Provider | 30, 10 |
| 34 | `src/deepwiki/core/research_engine.py` | 多轮迭代研究引擎 | 24 |
| 35 | `src/deepwiki/core/diagram_generator.py` | Mermaid 图表生成 | 9 |
| 36 | `src/deepwiki/output/mermaid_renderer.py` | Mermaid 代码输出 | 15 |
| 37 | `src/deepwiki/cli/repl.py` | REPL 交互模式 (prompt-toolkit) | 24 |
| 38 | `src/deepwiki/cli/config_cmd.py` | `deepwiki config` 子命令组 | 5 |
| 39 | `src/deepwiki/cli/research.py` | `deepwiki research` 命令 | 34 |
| 40 | `SKILL.md` | Agent 可发现清单 | — |
| 41 | 更新 `callbacks.py` | 集成 AgentDetector 到 provider 解析 | 30, 17 |
| 42 | 更新 `app.py` | 注册 repl/config/research 子命令 | 18 |

**里程碑**:
```bash
# Agent 模型复用 (在 Claude Code 中执行)
CLAUDE_CODE=1 ANTHROPIC_API_KEY=sk-... \
  deepwiki ask ./repo "Explain this" --json
# → 自动检测 Claude Code，使用 Anthropic provider

# REPL 交互
deepwiki repl ./my-repo
# → 进入交互式会话，多轮对话

# 深度研究
deepwiki research ./my-repo "Error handling patterns" -n 3
# → 3 轮迭代研究报告

# 配置管理
deepwiki config init
deepwiki config show
deepwiki config providers
```

---

### Phase 4: Remote Repos + Export + Serve — 完整功能

**目标**: 远程仓库支持、导出功能、HTTP 服务模式、Docker 部署。

**交付物**:

| # | File | Description | Depends On |
|---|------|-------------|------------|
| 43 | 更新 `repo_manager.py` | 远程仓库 clone: GitHub/GitLab/Bitbucket + token auth | 11 |
| 44 | `src/deepwiki/cli/export.py` | `deepwiki export` 命令 | 14, 26 |
| 45 | `src/deepwiki/server/api.py` | FastAPI REST API 服务 | 14, 24 |
| 46 | `src/deepwiki/cli/serve.py` | `deepwiki serve` 命令 | 45 |
| 47 | `Dockerfile` | Docker 镜像定义 | 1 |
| 48 | `docker-compose.yml` | Docker Compose 编排 | 47 |
| 49 | 更新 `app.py` | 注册 export/serve 子命令 | 18 |
| 50 | `.github/workflows/ci.yml` | CI 流水线: lint + test | — |

**里程碑**:
```bash
# 远程仓库
deepwiki generate https://github.com/fastapi/fastapi --token ghp_xxx

# 导出
deepwiki export ./my-repo --format markdown -o ./docs/

# HTTP 服务
deepwiki serve --port 8001
curl -X POST http://localhost:8001/api/ask -d '{"repo": "...", "question": "..."}'

# Docker
docker-compose up
```

---

### Phase 5: Testing + Distribution — 测试与发布

**目标**: 完整测试套件、PyPI 发布、生态集成。

**交付物**:

| # | File | Description |
|---|------|-------------|
| 51 | `tests/conftest.py` | 共享 fixtures |
| 52 | `tests/unit/test_config.py` | 配置系统测试 (5 级优先级) |
| 53 | `tests/unit/test_document_reader.py` | 文件读取 + 过滤测试 |
| 54 | `tests/unit/test_text_splitter.py` | 分块策略测试 |
| 55 | `tests/unit/test_vector_store.py` | ChromaDB 增删查改测试 |
| 56 | `tests/unit/test_agent_detector.py` | Agent 检测测试 (mock 环境变量) |
| 57 | `tests/unit/test_output_formatter.py` | 各格式输出测试 |
| 58 | `tests/e2e/test_generate.py` | 端到端 generate 命令测试 |
| 59 | `tests/e2e/test_ask.py` | 端到端 ask 命令测试 |
| 60 | `.github/workflows/release.yml` | PyPI 自动发布流水线 |
| 61 | 提交 CLI-Anything registry | registry.json PR |
| 62 | Claude Code plugin config | `.claude/` 配置 |

---

## 4. Phase Dependency Graph

```
Phase 1: Foundation
  │ pyproject.toml, config, providers/base, providers/litellm,
  │ data/repo_manager, data/document_reader, core/prompts,
  │ core/wiki_generator, output/terminal, cli/app, cli/generate
  │
  │ Milestone: deepwiki generate ./repo --provider openai
  │
  ▼
Phase 2: RAG + Q&A
  │ data/text_splitter, data/vector_store, data/cache_manager,
  │ providers/embedder, core/rag_engine, output/json,
  │ output/markdown, cli/ask
  │
  │ Milestone: deepwiki ask ./repo "question" --json
  │
  ▼
Phase 3: Agent + Multi-Provider
  │ agent/detector, agent/protocol, agent/proxy,
  │ core/research_engine, core/diagram_generator,
  │ cli/repl, cli/config, cli/research, SKILL.md
  │
  │ Milestone: Agent reuse verified, REPL working
  │
  ▼
Phase 4: Remote + Export + Serve
  │ repo_manager (remote), cli/export, server/api,
  │ cli/serve, Dockerfile, docker-compose.yml
  │
  │ Milestone: Full feature set, Docker deployed
  │
  ▼
Phase 5: Testing + Distribution
    tests/*, CI/CD, PyPI, CLI-Anything registry, Claude Code plugin

    Milestone: pip install deepwiki-cli works from PyPI
```

---

## 5. Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| litellm 不支持某个 provider 的特定功能 | Medium | Low | litellm 已覆盖 100+ provider；可通过 `extra_kwargs` 传递 provider 特有参数 |
| ChromaDB 在 Windows 上 SQLite 锁冲突 | Medium | Medium | 提供 FAISS 备选；文档说明 Windows 下避免并发访问 |
| Ollama 嵌入模型质量不如 OpenAI | Low | High | 已知 trade-off；文档说明质量差异；用户可选择混合模式 (Ollama 生成 + OpenAI 嵌入) |
| Agent 环境变量检测误判 | Low | Medium | 通用检测 (`DEEPWIKI_AGENT_*`) 优先级最高，用户可显式控制；`--provider` 始终覆盖 |
| 大型仓库 (10K+ 文件) 性能问题 | Medium | Medium | 默认排除规则过滤大量文件；`--include-dirs` 限制扫描范围；批量嵌入 + 进度条 |
| Python 依赖冲突 (chromadb + litellm) | Medium | Low | 锁定最小版本范围；推荐 pipx 隔离安装 |

---

## 6. Definition of Done (per Phase)

每个 Phase 完成的判定标准:

- [ ] 所有交付物文件已创建且可运行
- [ ] `pip install -e .` 无报错
- [ ] 里程碑命令可成功执行
- [ ] 无已知的 crash-level bug
- [ ] `deepwiki --help` 准确反映当前支持的命令
- [ ] 错误场景 (缺 API key、无效仓库路径) 有友好提示

Phase 5 额外标准:
- [ ] 单元测试覆盖率 >= 80%
- [ ] E2E 测试通过
- [ ] PyPI 可安装
- [ ] CI 流水线绿色
