# DeepWiki CLI 执行跟踪文档

> 最后更新: 2026-04-07
> 当前阶段: Phase 5（进行中）
> 执行策略: 先完成 Phase 0 基线对齐，再按 Phase 1 → Phase 5 推进。

---

## 1. 执行边界（强约束）

- 上游仓库 `vendor/deepwiki-open/` 只读，不直接修改（见 `docs/architecture/ADR-001-deepwiki-open-integration.md`）。
- 先交付可运行最小闭环，再扩展功能；禁止跨阶段提前引入高复杂度功能。
- 每阶段必须通过对应里程碑命令和 DoD 检查后再进入下一阶段。

---

## 2. 阶段总览

| Phase | 目标 | 状态 | 验收里程碑 |
|---|---|---|---|
| Phase 0 | 基线对齐（约束/范围/DoD） | 已完成 | 跟踪文档可执行、检查项明确 |
| Phase 1 | 最小可用 CLI（generate） | 已完成 | `deepwiki generate ./repo --provider ...` 可运行 |
| Phase 2 | RAG 问答（ask + 缓存） | 已完成 | `deepwiki ask ... --json` 返回结构化结果 |
| Phase 3 | Agent + Research + REPL + Config | 已完成 | Agent 复用生效，`research/repl/config` 可用 |
| Phase 4 | Remote/Export/Serve | 已完成 | 远程仓库、导出、HTTP 服务可用 |
| Phase 5 | 测试与发布 | 进行中 | 覆盖率与 CI 达标，可发布 |

---

## 3. Phase 0 基线检查清单

### 0.1 约束对齐

- [x] 明确上游集成红线（vendor 只读，优先适配层）
- [x] 明确默认技术栈（Typer + litellm + ChromaDB）
- [x] 明确输出协议（terminal/json/markdown）

### 0.2 范围确认

- [x] 本轮执行范围：**先完成 Phase 1 最小闭环**
- [x] 不提前实现 Phase 3+ 功能

### 0.3 DoD 初始化

- [x] 采用 `docs/PLAN.md` 中每阶段 DoD 作为验收基线
- [x] 在本文件持续记录每项达成证据（命令/文件）

---

## 4. Phase 1 执行清单（启动）

> 目标：先打通工程骨架与 `deepwiki generate` 的最小路径。

### 1.1 工程骨架

- [x] 创建 `pyproject.toml`（包元数据、依赖、入口）
- [x] 创建 `src/deepwiki/__init__.py`
- [x] 创建 `src/deepwiki/__main__.py`

### 1.2 配置与 provider 基础

- [x] 创建 `src/deepwiki/config/defaults.py`
- [x] 创建 `src/deepwiki/config/settings.py`（先支持 env + default）
- [x] 创建 `src/deepwiki/providers/base.py`
- [x] 创建 `src/deepwiki/providers/litellm_provider.py`（最小实现）

### 1.3 generate 最小链路

- [x] 创建 `src/deepwiki/data/repo_manager.py`（本地路径校验）
- [x] 创建 `src/deepwiki/data/document_reader.py`（最小文件读取）
- [x] 创建 `src/deepwiki/core/prompts.py`（最小模板）
- [x] 创建 `src/deepwiki/core/wiki_generator.py`（最小两阶段骨架）
- [x] 创建 `src/deepwiki/output/formatter.py`
- [x] 创建 `src/deepwiki/output/terminal.py`
- [x] 创建 `src/deepwiki/cli/callbacks.py`
- [x] 创建 `src/deepwiki/cli/app.py`
- [x] 创建 `src/deepwiki/cli/generate.py`

### 1.4 验证

- [x] `python -m deepwiki --help`
- [x] `deepwiki --help`
- [x] `deepwiki generate ./ --offline`（离线链路验证）
- [x] `deepwiki generate ./ --provider ollama --model ollama/qwen3.5:9b`（命令链路验证，WSL2 Ollama）

---

## 5. Phase 2 执行清单（完成）

> 目标：落地 `deepwiki ask`（RAG + 缓存 + JSON 输出）并完成最小验证闭环。

### 2.1 Provider 与配置扩展

- [x] 扩展 `BaseLLMProvider` 支持 embedding 抽象
- [x] 在 `LiteLLMProvider` 实现 `embed()`
- [x] 扩展 `build_runtime` 与 `Settings`，支持 embed/rag/cache 相关参数

### 2.2 数据与检索管线

- [x] 新增 `text_splitter`（chunk + overlap）
- [x] 新增 `vector_store`（Chroma 持久化/加载/查询）
- [x] 新增 `cache_manager`（cache key + metadata + 命中校验）
- [x] 新增 `rag_engine`（建索引、检索、回答编排）

### 2.3 CLI 与输出

- [x] 新增 `deepwiki ask` 命令并注册到 app
- [x] 新增 `JSONFormatter`，输出统一 envelope（`status/type/data/metadata`）
- [x] 支持 `--top-k` `--no-cache` `--json` 及 embed 参数覆盖

### 2.4 验证证据

- [x] `python -m deepwiki --help`（出现 ask 子命令）
- [x] `python -m deepwiki ask --help`
- [x] `python -m deepwiki ask <repo> <question> --json` 首次执行 `metadata.index_cached=false`
- [x] 同参数第二次执行 `metadata.index_cached=true`
- [x] `python -m deepwiki ask <repo> <question> --json --no-cache` 执行成功且 `metadata.index_cached=false`
- [x] `python -m deepwiki generate <repo> --offline`
- [x] `python -m deepwiki version`

---

## 6. Phase 3 执行清单（完成）

> 目标：在 Phase 2 基础上补齐 `config/research/repl/agent` 能力，形成可观测、可交互的 CLI 闭环。

### 3.1 配置分层与可观测输出

- [x] 实现配置优先级合并：CLI > Agent > ENV > Project > User > Default
- [x] 新增 `deepwiki config show`（文本 + `--json`）
- [x] `config show --json` 输出来源追踪（`source/origin`）

### 3.2 研究与交互能力

- [x] 新增 `deepwiki research <repo> <topic> -n <iterations>`
- [x] 新增 `type=research` JSON 输出协议
- [x] 新增 `deepwiki repl <repo>`，支持 `/help` `/clear` `/exit` `/quit`

### 3.3 Agent 联动与 Provider 展示

- [x] 新增 Agent 检测模块并接入 runtime 构建链路
- [x] 支持 agent 来源在 `config show --json` 可观测
- [x] 新增 `deepwiki config providers`（文本 + `--json`）
- [x] 补齐 `src/deepwiki/config/generator.json` 与 `embedder.json` 本地目录

### 3.4 配置管理补齐

- [x] 新增 `deepwiki config set <KEY> <VALUE>`
- [x] 新增 `deepwiki config init`
- [x] 新增 `deepwiki config path`

---

## 7. 进度日志

- **2026-04-02**
  - 已完成：仓库文档通读（README/PRD/Technical Spec/Architecture/Data Flow/Constraints/ADR/PLAN）。
  - 已完成：建立本跟踪文档并初始化 Phase 0 检查项。
  - 已完成：Phase 1 骨架、配置/provider 基础与 generate 最小链路代码落地。
  - 已验证：`python -m deepwiki --help`、`deepwiki --help`、`python -m deepwiki version`。
  - 已验证：`resolve_repo_path + read_repo_files` 最小数据链路可运行（读取 20 个文件）。
  - 阻塞：`deepwiki generate ... --provider ollama --model ollama/llama3` 调用失败，报 `ConnectionRefusedError: [WinError 1225]`（本机 Ollama 服务不可达）。
  - 诊断证据：`where.exe ollama` 未找到可执行文件；`netstat -ano | grep 11434` 无监听；当前环境未检测到 LLM API Key 相关变量。
  - 已新增：`generate --offline` 离线验证模式，可在无模型服务环境下完成命令链路验证。
  - 进一步诊断：`winget list --exact --id Ollama.Ollama` 未发现已安装 Ollama；`curl http://127.0.0.1:11434/api/tags` 连接失败。
  - 新结论：WSL2 Ubuntu 24.04 内 Ollama 0.18.0 运行正常，Windows 侧可直接访问 `127.0.0.1:11434`，已识别 `qwen3.5:9b` 模型并通过 `deepwiki generate ... --provider ollama --model ollama/qwen3.5:9b` 在线链路验证。
- **2026-04-07**
  - 已完成：Phase 3 Step 1（配置分层 + `config show`）并验证 CLI/ENV 优先级与 JSON 来源追踪。
  - 已完成：Phase 3 Step 2（`research` 最小闭环）并验证 `type=research` 输出协议。
  - 已完成：Phase 3 Step 3（`repl` 交互命令）并完成 `/help` 与 `/quit` 交互烟测。
  - 已完成：Phase 3 Step 4（Agent 检测 + provider 解析联动），`config show --json` 可见 `source=agent`。
  - 已完成：Phase 3 Step 4.5（`config providers` 落地），支持文本与 JSON 展示、标注当前生效 provider/model。
  - 已确认：仓库尚未引入 `vendor/deepwiki-open` 子模块，当前为“文档有设计、代码未接入”状态。
  - 已完成：Phase 3 Step 4.6（配置管理收尾），新增 `config set/init/path` 并与配置分层兼容。
  - 已更新：版本号提升到 `0.2.0`（代码与包元数据），并同步 PLAN/TECHNICAL_SPEC 文档头信息。
  - 下一步建议：执行 deepwiki-open 最小接入（只读 submodule + 版本固定 + 一致性校验），然后进入 Phase 4 的 remote/export/serve。
  - 已完成：deepwiki-open 最小只读接入（submodule），路径 `vendor/deepwiki-open`，上游 URL 为 `https://github.com/AsyncFuncAI/deepwiki-open`。
  - 已完成：版本固定到 submodule commit `4c6a1f7899aea57e200359912cc7c1c83c6b8937`，并完成初始化同步。
  - 已验证：`git submodule status --recursive`、子模块 remote 与工作区状态校验通过（无本地改动）。
  - 已验证：`python -m deepwiki version` 输出 `0.2.1`；`config path/providers --json` 与 `generate --offline` 回归通过。
  - 已更新：版本号提升到 `0.2.1`（代码、包元数据、PLAN、TECHNICAL_SPEC）。

---

## 8. Phase 4 执行清单（完成）

> 目标：在已接入 deepwiki-open 子模块基础上，完成 remote/export/serve 最小可用链路。

### 4.1 远程仓库能力

- [x] `repo_manager` 支持远程 URL 识别与 clone（HTTPS）
- [x] `generate/ask/research/repl` 增加 `--token` 与 `--repo-type` 参数
- [x] 支持仓库类型识别（github/gitlab/bitbucket）与认证头注入
- [x] 支持远程仓库 clone 缓存目录复用

### 4.2 当前未完成项（Phase 4）

- [x] `deepwiki export`
- [x] `deepwiki serve`
- [x] 远程仓库 token 认证 e2e（认证头注入与失败路径验证）

---

- **2026-04-07（Phase 4）**
  - 已完成：`src/deepwiki/data/repo_manager.py` 远程仓库解析、clone、超时控制与错误处理。
  - 已完成：`generate/ask/research/repl` 四个命令接入 `--token`、`--repo-type` 并复用远程路径解析。
  - 已验证：`deepwiki generate https://github.com/AsyncFuncAI/deepwiki-open --offline` 可直接运行。
  - 已验证：本地路径模式回归通过（`deepwiki generate <local> --offline`）。
  - 已更新：版本号提升到 `0.2.2`（代码、包元数据、PLAN、TECHNICAL_SPEC）。
  - 已完成：新增 `deepwiki export` 命令并接入 app 注册，支持 `--format markdown|json`、`--output-dir`、`--language`、`--token`、`--repo-type`、`--offline`。
  - 已验证：`deepwiki export <repo> --format markdown -o <dir> --offline` 导出 `README.md`、编号页面、`diagrams/`、`metadata.json`。
  - 已验证：`deepwiki export <repo> --format json -o <dir> --offline` 导出 `wiki.json`。
  - 已更新：版本号提升到 `0.2.3`（代码、包元数据、PLAN、TECHNICAL_SPEC）。
  - 已完成：新增 `deepwiki serve` 命令与 `src/deepwiki/server/api.py`，支持 `/health`、`/api/generate`、`/api/ask`、`/api/research`、`/api/providers`、`/api/models/{provider}`。
  - 已完成：新增依赖 `fastapi` 与 `uvicorn`，支持 `--host`、`--port`、`--reload`、`--cors-origins`。
  - 已验证：`deepwiki serve --help` 参数可见；服务启动后 `/health` 与 `/api/providers` 可访问。
  - 已更新：版本号提升到 `0.2.4`（代码、包元数据、PLAN、TECHNICAL_SPEC）。
  - 已验证：token 认证链路 e2e（CLI）——`generate <repo>.git --token <fake> --repo-type github --offline` 返回认证失败，错误信息可读。
  - 已验证：token 认证头注入（repo_manager）——通过 mock `subprocess.run` 断言 clone 命令包含 `http.extraheader=AUTHORIZATION: basic ...`。
  - 已验证：服务链路（API）——`POST /api/generate` 可接收 `token/repo_type` 参数并正常走统一仓库解析链路。
  - 已更新：版本号提升到 `0.2.5`（代码、包元数据、PLAN、TECHNICAL_SPEC）。

---

## 9. Phase 5 执行清单（进行中）

> 目标：建立测试与 CI 基线，形成可持续发布前检查路径。

### 5.1 测试与工程基线

- [x] 新增 `tests/unit` 最小单元测试（settings/document_reader/text_splitter/json_output）
- [x] 新增 `tests/e2e` 离线冒烟测试（generate）
- [x] 在 `pyproject.toml` 增加 `dev` 测试依赖与 `pytest` 配置
- [x] 补齐 `.gitignore` 的测试产物忽略规则

### 5.2 CI 基线

- [x] 新增 `.github/workflows/ci.yml`
- [x] CI 覆盖 Python 3.10/3.11/3.12
- [x] CI 执行 `pytest + coverage` 并设置最低覆盖率门槛

### 5.3 当前未完成项（Phase 5）

- [x] 扩展覆盖率到 80% 目标（当前本地覆盖率 83%，52 passed）
- [x] 新增发布工作流 `release.yml`（tag 构建与发布）
- [ ] 执行 `pip install deepwiki-cli` 发布后安装验证

---

- **2026-04-07（Phase 5）**
  - 已完成：新增测试文件 `tests/unit/test_settings.py`、`test_document_reader.py`、`test_text_splitter.py`、`test_json_output.py`、`tests/e2e/test_generate_offline.py`。
  - 已完成：新增 `.github/workflows/ci.yml`，执行 `python -m pip install -e .[dev]` 与 `pytest --cov=src/deepwiki --cov-fail-under=40`。
  - 已验证：本地执行 `pytest --cov=src/deepwiki --cov-fail-under=40` 通过（8 passed，coverage 47.09%）。
  - 已更新：版本号提升到 `0.2.6`（代码、包元数据、PLAN、TECHNICAL_SPEC）。
  - 已完成：扩展单测覆盖至 `repo_manager`、`providers_catalog`、`export` helper、`server api`，新增 `tests/unit/test_repo_manager.py`、`test_providers_catalog.py`、`test_export_helpers.py`、`test_server_api.py`。
  - 已完成：新增 `.github/workflows/release.yml`，支持 tag 触发构建与 PyPI 发布流程。
  - 已验证：本地执行 `pytest --cov=src/deepwiki --cov-fail-under=40` 通过（21 passed，coverage 56.45%）。
  - 已更新：CI 覆盖率门槛提升为 `50%`。
  - 已更新：版本号提升到 `0.2.7`（代码、包元数据、PLAN、TECHNICAL_SPEC）。
  - 已完成：优先模块测试补齐，新增 `tests/unit/test_research.py` 并扩展 `test_config_cmd.py`、`test_rag_engine.py`、`test_vector_store.py`。
  - 已完成：新增 `test_cache_manager.py`、`test_ask.py`、`test_repl.py`、`test_misc_modules.py`，覆盖 CLI 与核心模块关键分支。
  - 已验证：本地执行 `py -3.14 -m pytest --cov=src/deepwiki --cov-report=term-missing` 通过（52 passed，coverage 83%）。
  - 已验证：`py -3.14 -m pytest --cov=src/deepwiki --cov-fail-under=80` 通过，覆盖率门槛 80% 达标。
  - 已验证：在隔离环境执行 `pip install deepwiki-cli` 失败（No matching distribution found），当前 PyPI 尚无可安装发布包，安装验收保持未完成。
  - 已更新：版本号提升到 `0.2.8`（代码、包元数据、PLAN、TECHNICAL_SPEC）。
  - 已完成：执行本地发布前验收，构建 `sdist + wheel` 并在隔离环境通过 wheel 安装与命令冒烟验证。
  - 已完成：新增验收脚本 `scripts/verify_post_release.ps1`，支持 `-Mode pypi|wheel`。
  - 已验证：`python -m deepwiki --help`、`python -m deepwiki version`、`python -m deepwiki generate <repo> --offline` 在安装环境可运行。
  - 已更新：版本号提升到 `0.2.9`（代码、包元数据、PLAN、TECHNICAL_SPEC）。
