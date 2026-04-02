# ADR-001: deepwiki-open 集成策略

> Type: Architecture Decision Record  
> Status: Proposed  
> Date: 2026-04-02  
> Context: deepwiki-cli 应如何利用 deepwiki-open 的源码

---

## ⚠️ 上游源码治理政策（Upstream Source Policy）

> **这是本项目最重要的边界约定，所有贡献者在触碰 `vendor/` 目录前必须阅读。**

### 默认立场：只读，不修改

`vendor/deepwiki-open/` 是对 [AsyncFuncAI/deepwiki-open](https://github.com/AsyncFuncAI/deepwiki-open) 的**只读引用**。

- ✅ 允许：读取文件、import 模块、symlink 配置文件
- ✅ 允许：`git submodule update --remote` 拉取上游更新
- ❌ 禁止：在 `vendor/deepwiki-open/` 内直接修改任何文件
- ❌ 禁止：向 `vendor/deepwiki-open/` 提交 commit
- ❌ 禁止：在未评估替代方案的情况下以"临时修复"为由修改上游文件

**原因**：对上游的任何修改都会导致：
1. `git submodule update` 时产生冲突，破坏同步机制
2. 与上游的 diff 随时间累积，最终无法合并
3. 修改内容在上游迭代后需要反复 rebase，维护成本指数增长

### 侵入式修改的决策门槛

当且仅当满足以下**全部**条件时，才可讨论对上游文件的侵入式修改：

1. **技术必要性已证明**：已穷举所有非侵入方案（适配层、shim、subprocess 隔离），确认均不可行
2. **影响范围已评估**：明确修改哪些文件、改动行数、对上游未来 PR 的影响
3. **获得授权**：在 Issue 或 PR 中明确记录决策，取得项目维护者认可
4. **已规划上游贡献路径**：侵入式修改应当以 PR 回馈 deepwiki-open 上游，而非仅在本地维护 patch

### Fork 策略（备用，非默认）

如果侵入式修改不可避免且无法合入上游，可以将 deepwiki-open fork 到自己的组织仓库进行管理：

```
vendor/deepwiki-open  →  git submodule 指向 <your-org>/deepwiki-open（fork）
                         而非 AsyncFuncAI/deepwiki-open（原始）
```

**Fork 的代价与前提**：
- Fork 并非底线，只是当其他方案均不可行时的**最后手段**
- Fork 引入额外维护负担：需要定期从原始仓库 `git fetch upstream && git merge` 同步
- Fork 之前必须评估：这个修改是否真的无法通过适配层解决？
- Fork 之后必须建立：定期同步原始仓库的 CI 任务（建议每周或每个 release 触发）

```bash
# Fork 后的同步工作流（必须建立）
git remote add upstream https://github.com/AsyncFuncAI/deepwiki-open
git fetch upstream
git merge upstream/main
# 解决冲突，推送到 fork
```

### 优先级顺序（从优到劣）

```
1. 适配层（Adapter）         ← 首选：在 src/deepwiki/adapters/ 写类型转换
2. Subprocess 隔离           ← 次选：进程边界完全隔离
3. 向上游提 PR               ← 主动贡献：让改进进入官方版本
4. Fork + 维护 patch         ← 备用：确有必要时使用，但要建立同步机制
5. 直接修改 vendor/ 文件     ← 禁止：此路不通
```

---

## 背景与问题

deepwiki-open 的 Python 后端包含多个有价值的模块：

| 模块 | 内容 | 耦合度 |
|------|------|--------|
| `api/prompts.py` | 5 个 LLM prompt 模板（RAG、研究、对话） | **零耦合** — 纯字符串常量 |
| `api/config/*.json` | 模型预设、文件过滤规则 | **零耦合** — 纯配置文件 |
| `api/data_pipeline.py` | 仓库读取、文档处理、embedding 流水线 | **低耦合** — 纯函数为主，仅依赖 `adalflow.Document` 类型 |
| `api/rag.py` | `RAG` 类：向量检索 + 问答 | **中耦合** — 依赖 adalflow 框架类型，但**无 FastAPI/WebSocket 耦合**，可独立调用 |
| `api/api.py` | FastAPI 路由层 | **高耦合** — HTTP request context，不可复用 |
| `api/openai_client.py` 等 | 7 个 provider 客户端 | **中耦合** — 被 litellm 替代，无复用价值 |

**问题核心**：
- 当前方案（Plan.md §3.4）决定"重新实现，不 fork"，导致无法自动同步 deepwiki-open 的改进
- 侵入式修改是否不可避免？
- 有没有既能复用代码、又能持续同步上游的方案？

---

## 候选策略

### Strategy A: 纯重新实现（当前方案）

```
deepwiki-cli
└── src/deepwiki/           ← 全部自研
    ├── core/prompts.py     ← 手工移植 prompts.py
    ├── core/rag_engine.py  ← 自研 RAG，不依赖 adalflow
    └── data/...            ← 自研数据层
```

**同步机制**: 无。上游改进需人工发现、手工移植。

| 维度 | 评估 |
|------|------|
| 侵入性 | ✅ 零（无依赖） |
| 上游同步 | ❌ 无自动机制 |
| 维护成本 | 高（重复造轮子） |
| 依赖体积 | 最小（无 adalflow） |
| 适用阶段 | Phase 1 快速验证 |

---

### Strategy B: Git Submodule + 仅导入静态资产

```
deepwiki-cli/
├── vendor/deepwiki-open/           ← git submodule (只读)
│   └── api/
│       ├── prompts.py              ← 直接 import，零修改
│       └── config/*.json           ← 构建时 symlink 或 copy
└── src/deepwiki/
    ├── core/rag_engine.py          ← 自研
    └── data/...                    ← 自研
```

**同步机制**: 
```bash
git submodule update --remote vendor/deepwiki-open
# prompts.py 和 config/*.json 的所有改进立即可用
```

**使用示例**:
```python
# src/deepwiki/core/prompts.py
# 直接导入，无任何适配
from vendor.deepwiki_open.api.prompts import (
    RAG_SYSTEM_PROMPT,
    RAG_TEMPLATE,
    DEEP_RESEARCH_FIRST_ITERATION_PROMPT,
    DEEP_RESEARCH_INTERMEDIATE_ITERATION_PROMPT,
    DEEP_RESEARCH_FINAL_ITERATION_PROMPT,
)
```

| 维度 | 评估 |
|------|------|
| 侵入性 | ✅ 零（只读引用） |
| 上游同步 | ✅ prompts + configs 自动同步 |
| 维护成本 | 低（只需关注 prompts.py API 变更） |
| 依赖体积 | 小（无 adalflow） |
| 覆盖范围 | 仅 prompts + configs（约 20% 的上游价值） |
| 适用阶段 | Phase 1-2 起即可使用 |

---

### Strategy C: Git Submodule + 适配层（推荐）

```
deepwiki-cli/
├── vendor/deepwiki-open/           ← git submodule (只读)
│   └── api/
│       ├── prompts.py              ← 直接 import
│       ├── config/*.json           ← 直接读取
│       ├── data_pipeline.py        ← 通过适配层调用
│       └── rag.py                  ← 通过适配层调用
└── src/deepwiki/
    ├── adapters/
    │   ├── upstream_rag.py         ← RAG 适配层（类型转换）
    │   └── upstream_data.py        ← data_pipeline 适配层
    ├── providers/
    │   └── litellm_provider.py     ← 仍使用 litellm（替代 provider clients）
    └── cli/                        ← CLI 层不变
```

**适配层负责什么**:

```python
# src/deepwiki/adapters/upstream_rag.py
"""
适配层：将 deepwiki-open 的 RAG 类映射到 deepwiki-cli 的接口。
唯一职责：类型转换 + 配置注入。不含业务逻辑。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../vendor/deepwiki-open'))

from api.rag import RAG as _UpstreamRAG
from deepwiki.providers.base import BaseLLMProvider
from deepwiki.data.vector_store import Document


class UpstreamRAGAdapter:
    """
    包装 deepwiki-open 的 RAG 类，暴露 deepwiki-cli 内部接口。
    
    关键适配点:
      - adalflow.Document  ←→  deepwiki.data.vector_store.Document
      - deepwiki-open provider 字符串  ←→  litellm provider 字符串
      - 同步调用  ←→  async/await 封装
    """
    
    def __init__(self, llm_provider: BaseLLMProvider):
        # 将 litellm provider 映射到 deepwiki-open 期望的 provider 字符串
        upstream_provider = self._map_provider(llm_provider.provider)
        self._rag = _UpstreamRAG(
            provider=upstream_provider,
            model=llm_provider.model,
        )
    
    async def index(self, repo_path: str, **kwargs) -> int:
        """调用上游 prepare_retriever，返回索引文档数。"""
        await asyncio.to_thread(
            self._rag.prepare_retriever, repo_path, **kwargs
        )
        return self._rag.retriever.transformed_docs.__len__()
    
    async def ask(self, question: str, language: str = "en") -> tuple[str, list[Document]]:
        """调用上游 RAG.call，转换返回类型。"""
        retrieved_docs, answer = await asyncio.to_thread(
            self._rag.call, question, language
        )
        # adalflow Document → deepwiki Document
        sources = [self._convert_doc(d) for d in retrieved_docs]
        return answer, sources
    
    @staticmethod
    def _map_provider(litellm_provider: str) -> str:
        return {
            "openai": "openai", "google": "google",
            "ollama": "ollama", "openrouter": "openrouter",
        }.get(litellm_provider, "openai")
    
    @staticmethod
    def _convert_doc(adalflow_doc) -> Document:
        return Document(
            text=adalflow_doc.text,
            metadata={"file_path": getattr(adalflow_doc, "meta_data", {}).get("file_path", "")},
        )
```

**同步机制**:
```bash
# 拉取上游改进
git submodule update --remote vendor/deepwiki-open

# 运行适配层测试，确认接口未破坏
pytest tests/unit/test_adapters.py -v

# 如果上游 API 签名变化，仅修改适配层（不修改 deepwiki-open 本身）
```

**adalflow 依赖处理**:
```toml
# pyproject.toml — adalflow 作为可选依赖
[project.optional-dependencies]
upstream = ["adalflow>=0.2.0"]  # 使用上游 RAG 引擎时需要
# 默认使用自研 RAG 引擎（chromadb），无需 adalflow
```

| 维度 | 评估 |
|------|------|
| 侵入性 | ✅ 零（deepwiki-open 只读，不修改任何文件） |
| 上游同步 | ✅ 所有模块自动同步（prompts + config + RAG 算法） |
| 维护成本 | 中（适配层 ~200 行，只在上游接口变化时需更新） |
| 依赖体积 | 中（新增 adalflow 为可选依赖） |
| 覆盖范围 | ~80% 的上游价值 |
| 适用阶段 | Phase 2+ |

---

### Strategy D: 进程隔离（HTTP Proxy）

```
deepwiki-cli (HTTP Client)
    │
    │ HTTP requests (httpx)
    │
    ▼
deepwiki-open backend (subprocess)
    ├── uvicorn
    └── FastAPI → rag.py → data_pipeline.py
```

**启动流程**:
```python
# src/deepwiki/adapters/process_proxy.py
import subprocess, httpx, asyncio

class DeepWikiProxy:
    """启动 deepwiki-open backend，通过 HTTP 通信。"""
    
    async def start(self):
        self._proc = subprocess.Popen([
            "python", "-m", "uvicorn", "api.main:app",
            "--port", str(self._port), "--host", "127.0.0.1"
        ], cwd="vendor/deepwiki-open")
        await self._wait_ready()   # 轮询 /health
    
    async def ask(self, repo, question, **kwargs) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://127.0.0.1:{self._port}/api/ask",
                json={"repo_url": repo, "question": question, **kwargs},
                timeout=300,
            )
            return resp.json()
    
    async def stop(self):
        self._proc.terminate()
```

| 维度 | 评估 |
|------|------|
| 侵入性 | ✅ 零（完全黑盒） |
| 上游同步 | ✅ 完全自动（无需任何适配） |
| 维护成本 | 最低（无适配代码） |
| 依赖体积 | 最大（需要完整 deepwiki-open 环境） |
| 启动延迟 | ❌ 2–5s（uvicorn 启动） |
| 流式输出 | 需要 SSE/WebSocket 代理 |
| 端口管理 | 需要随机端口分配、端口冲突处理 |
| 适用阶段 | 不推荐作为主方案；可作为 serve 模式的后端 |

---

## 对比矩阵

| 策略 | 侵入性 | 自动同步范围 | 维护成本 | 依赖新增 | 启动性能 | 推荐指数 |
|------|--------|------------|---------|---------|---------|---------|
| A: 纯重新实现 | ✅ 零 | ❌ 无 | 高 | 无 | 最优 | Phase 1 ★★★☆☆ |
| B: Submodule + 静态资产 | ✅ 零 | ✅ prompts + configs | 低 | 无 | 最优 | ★★★★☆ |
| C: Submodule + 适配层 | ✅ 零 | ✅ 全部核心逻辑 | 中 | adalflow (可选) | 最优 | **★★★★★** |
| D: 进程隔离 | ✅ 零 | ✅ 全部 | 最低 | deepwiki-open env | 差 | ★★☆☆☆ |

---

## 推荐方案：渐进式 B → C

### 阶段一（Phase 1-2）：Strategy B

立即获益，零风险：
```bash
git submodule add https://github.com/AsyncFuncAI/deepwiki-open vendor/deepwiki-open
git submodule update --init
```

- 直接 `import` `prompts.py` — 立即同步 prompt 改进
- symlink `vendor/deepwiki-open/api/config/*.json` → `src/deepwiki/config/`
- 自研 RAG + data 层（使用 litellm + chromadb）

### 阶段二（Phase 3+）：Strategy C

当上游 RAG 算法有重大改进时迁移：
- 编写 `UpstreamRAGAdapter`（~200 行）
- `adalflow` 作为可选依赖（`pip install deepwiki-cli[upstream]`）
- 添加适配层测试，覆盖接口契约

### 长期

自研引擎和上游引擎作为**可选后端**并存：
```bash
deepwiki ask ./repo "question" --engine upstream   # 使用 deepwiki-open RAG
deepwiki ask ./repo "question" --engine native      # 使用自研 RAG (默认)
```
用户可根据需求选择；新功能在上游出现时可立即使用。

---

## 为什么侵入式修改不是必须的

> **结论：完全不需要修改 deepwiki-open 的任何文件。**

三个关键发现支持这个结论：

1. **`prompts.py` 是纯字符串** — 直接 `import` 即可，无需任何修改
2. **`RAG` 类无 FastAPI 耦合** — 可独立实例化和调用：`rag = RAG(...); rag.call(query)`
3. **所有 provider client 被 litellm 替代** — 无需引入 deepwiki-open 的 provider 层

适配层存在的唯一原因是**类型系统差异**（`adalflow.Document` ↔ `deepwiki.Document`），而这个转换是单向的、无副作用的。

---

## 同步工作流（Submodule）

```bash
# 日常同步
git submodule update --remote vendor/deepwiki-open
git add vendor/deepwiki-open
git commit -m "chore: sync deepwiki-open to upstream <commit-sha>"

# 查看上游变化
git -C vendor/deepwiki-open log --oneline HEAD..origin/main

# 检查关键文件是否有 breaking change
git -C vendor/deepwiki-open diff HEAD origin/main -- api/prompts.py api/rag.py

# 运行适配层测试
pytest tests/unit/test_adapters.py -v
```

**建议在 CI 中加入**:
```yaml
# .github/workflows/sync-check.yml
- name: Check upstream divergence
  run: |
    git submodule update --remote --dry-run vendor/deepwiki-open
    # 如果有更新，创建自动 PR
```

---

## 需要更新的文档

此 ADR 与以下文档存在冲突，需同步修订：

| 文档 | 位置 | 当前描述 | 应改为 |
|------|------|---------|--------|
| `ARCHITECTURE.md` | §3.4 | "重新实现（vendor concepts, not code）" | 见本 ADR 推荐策略 |
| `CONSTRAINTS.md` | §1.3 | "不直接 fork 或 vendor deepwiki-open 代码" | 改为：不侵入修改；通过只读 submodule + 适配层集成 |
| `PLAN.md` | Phase 1 交付物 | 无 submodule 相关任务 | 在 Phase 1 添加：配置 git submodule |

---

## 决策

**采用 Strategy B（立即）+ Strategy C（Phase 3+）的渐进路径。**

理由：
- 对 deepwiki-open **零侵入**，可随时 `git submodule update` 同步上游
- prompt 模板和配置文件**立即同步**，这是价值最高、最常更新的部分
- RAG 适配层**延迟引入**，等上游算法稳定后再接入，降低早期风险
- 两套引擎并存为用户提供灵活性，不强迫迁移
