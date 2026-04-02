# DeepWiki CLI - Product Requirements Document (PRD)

> Version: 0.1.0 | Status: Draft | Updated: 2026-04-01

## 1. Overview

### 1.1 Product Vision

DeepWiki CLI 是一个 AI 驱动的命令行工具，能够自动分析任意 Git 仓库并生成结构化的 Wiki 文档、回答代码相关问题、进行深度研究。它将 [deepwiki-open](https://github.com/AsyncFuncAI/deepwiki-open) 的 Web 服务能力完全 CLI 化，借鉴 [CLI-Anything](https://github.com/HKUDS/CLI-Anything) 的 Agent-Native 设计理念，使其既可被人类直接使用，也可被 AI Agent 程序化调用。

### 1.2 Problem Statement

| 问题 | 现状 | 目标 |
|------|------|------|
| deepwiki-open 需要启动 Web 服务才能使用 | 需要 Docker + 前后端服务，使用门槛高 | 一条命令即可生成 Wiki |
| 无法在 CI/CD、脚本、Agent 中集成 | Web UI 无法程序化调用 | 支持 JSON 输出、退出码、管道操作 |
| 绑定云端 API，不支持离线使用 | 必须有外部 API Key | 完整支持 Ollama 本地模型 |
| AI Agent 无法自动发现和使用 | 无 Agent 协议支持 | SKILL.md + Agent 模型复用 |
| 部署环境受限 | 主要面向 Docker 部署 | 支持 Linux/macOS/Windows/CI/Server |

### 1.3 Target Users

| 用户角色 | 使用场景 | 关键需求 |
|----------|---------|---------|
| **开发者** | 快速了解新项目代码结构 | `deepwiki generate ./repo` 一键生成文档 |
| **技术主管** | 代码审查、架构评估 | 生成架构图、模块关系可视化 |
| **AI Agent** | Claude Code/Cursor 等自动调用 | `--json` 结构化输出、Agent 模型复用 |
| **DevOps 工程师** | CI/CD 流水线集成文档生成 | Headless 模式、退出码、无交互 |
| **安全研究员** | 离线环境分析私有代码 | Ollama 本地模型、无外部网络依赖 |
| **团队** | 私有化部署文档服务 | `deepwiki serve` API 模式、Docker 部署 |

## 2. Functional Requirements

### 2.1 Core Features (P0 - Must Have)

#### FR-01: Wiki 生成

- **描述**: 分析 Git 仓库，生成结构化的 Wiki 文档（标题、目录、分页、内容）
- **输入**: 本地仓库路径或远程仓库 URL
- **输出**: 终端渲染 / Markdown 文件 / JSON 结构
- **验收标准**:
  - 支持本地路径 `./my-repo` 和远程 URL `https://github.com/owner/repo`
  - 自动识别项目类型，生成相应的文档结构
  - 支持指定语言（中文/英文/日文等 10+ 语言）
  - 生成包含 Mermaid 语法的架构图
  - 支持 `--include-dirs` / `--exclude-dirs` 过滤
  - 支持 `--max-pages` 控制生成规模

#### FR-02: RAG 问答

- **描述**: 基于 RAG（检索增强生成）回答关于仓库代码的问题
- **输入**: 仓库 + 自然语言问题
- **输出**: 基于代码上下文的回答，附带引用来源
- **验收标准**:
  - 首次使用时自动建立向量索引
  - 后续问答复用缓存索引（除非 `--no-cache`）
  - 支持流式输出（逐字显示）
  - 支持多轮对话上下文（REPL 模式）
  - 回答中包含相关源文件路径引用

#### FR-03: 多 LLM 提供商支持

- **描述**: 统一接口支持多种 LLM 提供商
- **支持列表**:
  - OpenAI (GPT-4o, GPT-4o-mini, etc.)
  - Google (Gemini 2.5 Flash, Gemini 2.5 Pro)
  - Anthropic (Claude Sonnet, Claude Opus)
  - Ollama (本地模型: llama3, qwen2, etc.)
  - OpenRouter (聚合多模型)
  - Azure OpenAI
  - AWS Bedrock
  - 任意 OpenAI 兼容 API
- **验收标准**:
  - `--provider` + `--model` 标志切换提供商
  - 嵌入模型可独立于生成模型配置
  - API Key 通过环境变量或配置文件提供

#### FR-04: 配置管理

- **描述**: 分层配置系统，5 级优先级
- **验收标准**:
  - `deepwiki config init` 交互式引导配置
  - `deepwiki config show` 显示当前配置及来源
  - `deepwiki config set <key> <value>` 设置配置项
  - `deepwiki config providers` 列出可用提供商和模型
  - 配置文件格式: YAML

### 2.2 Enhanced Features (P1 - Should Have)

#### FR-05: Agent 模型复用

- **描述**: 自动检测父 AI Agent 环境，复用其 LLM 连接
- **验收标准**:
  - 检测 Claude Code、Cursor、Copilot、aider 等主流 Agent
  - 通过环境变量嗅探获取 API Key、Model、Provider
  - 支持通用的 `DEEPWIKI_AGENT_*` 环境变量传递
  - 可通过 `--provider` 显式覆盖 Agent 检测结果

#### FR-06: 深度研究

- **描述**: 多轮迭代研究某个主题，逐步深入
- **验收标准**:
  - 支持 `--iterations` 指定研究迭代次数
  - 每轮迭代基于前一轮结果提出新问题
  - 最终生成综合研究报告
  - 支持导出为 Markdown

#### FR-07: 交互式 REPL

- **描述**: 进入交互式会话，持续对仓库提问
- **验收标准**:
  - Tab 补全、历史记录
  - 多轮对话保持上下文
  - 支持 `/help`、`/clear`、`/export` 等 REPL 命令
  - Ctrl+C 优雅退出

#### FR-08: HTTP API 服务模式

- **描述**: 启动 HTTP 服务，提供 REST API
- **验收标准**:
  - `deepwiki serve --port 8001` 启动服务
  - 提供与 deepwiki-open 兼容的 API 端点
  - 支持 CORS 配置
  - 支持健康检查端点

### 2.3 Distribution Features (P2 - Nice to Have)

#### FR-09: SKILL.md Agent 清单

- **描述**: 遵循 CLI-Anything 规范，生成 Agent 可发现的能力清单
- **验收标准**:
  - 项目根目录包含 SKILL.md
  - 可提交至 CLI-Anything 注册表
  - 提供 Claude Code 插件配置

#### FR-10: 导出功能

- **描述**: 将生成的 Wiki 导出为文件
- **验收标准**:
  - 支持 Markdown 目录结构导出
  - 支持 JSON 单文件导出
  - 支持自定义输出目录

## 3. Non-Functional Requirements

### 3.1 Performance

| 指标 | 目标 |
|------|------|
| CLI 启动时间 | < 2s（不含 LLM 调用） |
| 小型仓库（< 100 文件）Wiki 生成 | < 3 min |
| 中型仓库（100-500 文件）Wiki 生成 | < 10 min |
| 向量索引建立（首次） | < 2 min（小型仓库） |
| 缓存命中的 RAG 问答 | < 10s（不含 LLM 响应时间） |
| 内存占用峰值 | < 2GB |

### 3.2 Compatibility

| 维度 | 要求 |
|------|------|
| Python | >= 3.10 |
| OS | Linux (Ubuntu 20.04+), macOS (12+), Windows (10/11) |
| Terminal | 支持 ANSI 色彩 + 不支持色彩的回退方案 |
| Git | >= 2.20 |
| 网络 | 在线（API 调用）+ 完全离线（Ollama） |

### 3.3 Security

- API Key 不写入日志、不出现在错误输出
- 私有仓库 Token 仅在内存中使用，不持久化
- 配置文件权限建议 `chmod 600`
- 不上传任何代码到第三方服务（除 LLM API 调用外）

### 3.4 Usability

- 所有命令支持 `--help` 自文档
- 错误信息包含修复建议（如 "Missing API key, run `deepwiki config init` to set up"）
- 长操作显示进度条（终端模式）或进度事件（JSON 模式）
- 支持 `Ctrl+C` 优雅中断

## 4. Constraints

### 4.1 Technical Constraints

- **不 fork deepwiki-open 代码**: 其后端与 adalflow/FastAPI 紧耦合，提取核心算法和 prompt 模板重新实现
- **litellm 依赖**: 作为唯一 LLM 客户端层，不再维护多个独立 provider 客户端
- **Python 生态**: 所有依赖必须支持 Python 3.10+ 且跨平台可安装
- **无浏览器依赖**: CLI 工具不应依赖 Chromium/Playwright 等浏览器引擎

### 4.2 Business Constraints

- 开源协议: MIT
- 不依赖任何付费服务的免费额度（必须能完全使用免费/本地模型运行）
- 不收集用户数据或遥测

## 5. Success Metrics

| 指标 | Phase 1 目标 | 最终目标 |
|------|-------------|---------|
| 支持的 LLM 提供商 | 3 (OpenAI, Ollama, Google) | 7+ |
| 命令数量 | 2 (generate, config) | 7 |
| 测试覆盖率 | 50% | 80% |
| 平台支持 | Linux + macOS | Linux + macOS + Windows + Docker |
| `pip install` 可用 | No | Yes (PyPI) |

## 6. Out of Scope (v0.1)

- Web UI / 图形界面
- 多用户认证/权限管理
- 实时协作编辑 Wiki
- Git hooks 自动触发
- 付费/SaaS 部署
- 多仓库同时分析
