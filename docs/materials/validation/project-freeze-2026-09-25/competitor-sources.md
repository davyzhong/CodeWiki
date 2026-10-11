---
status: frozen-evidence
last-reviewed: 2026-10-11
scope: representative-category-complete-competitive-review
sources:
  - official product documentation and first-party repositories listed below
---

# 竞品来源与能力核验

## 口径

“完整竞对”定义为覆盖本项目问题空间的全部主要类别，而不是声称穷尽全球每个工具：自动代码 Wiki、代码搜索/上下文、Agent 记忆、知识文档平台、local/self-hosted 实现、直接上游。只采用官方文档、官方博客或一方仓库；主要产品能力检索日期为 2026-09-25，上游 issue/release 状态于 2026-10-11 再核验。营销 benchmark 不作为本项目完成证据。

## 一方来源

| 产品 | 核验来源 | 当前可确认能力 |
|---|---|---|
| Qoder Repo Wiki | [官方文档](https://docs.qoder.com/user-guide/repo-wiki)、[CLI 文档](https://docs.qoder.com/cli/repo-wiki) | 结构化 Wiki、增量更新、Git 同步、人工修改保护、计划文件、双语、Agent 引用 |
| Qoder Knowledge Cards | [官方文档](https://docs.qoder.com/zh/user-guide/knowledge-engine/knowledge-cards) | 共享/个人卡片、项目知识沉淀、Agent 使用 |
| Qoder 方法叙事 | [官方博客](https://qoder.com/zh/blog/repo-wiki-surfacing-implicit-knowledge) | 从代码表面恢复隐性知识、多人共享与持续维护 |
| Google Code Wiki | [Google Developers Blog](https://developers.googleblog.com/introducing-code-wiki-accelerating-your-code-understanding/) | 持续再生成、源码/定义回链、集成 Chat、架构/类/时序图；本地 CLI 扩展仍写作 coming soon |
| Cognition DeepWiki | [官方仓库](https://github.com/CognitionAI/deepwiki)、[MCP endpoint](https://mcp.deepwiki.com/) | 公共仓库 Wiki、Ask、目录/正文读取、三工具 MCP；私库需 Devin 账户 |
| DeepWiki Open | [官方仓库](https://github.com/AsyncFuncAI/deepwiki-open)、[API README](https://github.com/AsyncFuncAI/deepwiki-open/blob/main/api/README.md) | self-hosted、多 Git host、RAG/embedding、图表、local storage、多模型 |
| GitHub Copilot Memory | [GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/copilot-memory) | 仓库事实/个人偏好、使用前验证、未使用 28 天淘汰 |
| GitHub Copilot Spaces | [GitHub Docs](https://docs.github.com/en/copilot/concepts/context/spaces) | 仓库、文件、PR、issue、文本组合为上下文；GitHub 来源自动更新，可经 MCP 进入 IDE |
| Sourcegraph | [官方文档](https://sourcegraph.com/docs)、[Cody FAQ](https://sourcegraph.com/docs/cody/faq)、[Deep Search](https://sourcegraph.com/docs/deep-search) | 精确/结构搜索、代码导航、多仓上下文、agentic search；Enterprise 以 Search 替代 embeddings 以降低安全/维护/规模成本 |
| Cursor | [Rules 文档](https://docs.cursor.com/context/rules-for-ai)、[Codebase Indexing](https://docs.cursor.com/context/codebase-indexing) | 自动索引、语义上下文、版本化 project rules / AGENTS.md |
| Augment Code | [Context Engine](https://www.augmentcode.com/product/context-engine) | 代码、历史、文档与团队知识的实时检索；本地索引器反映工作区变化 |
| Greptile | [官方文档](https://docs.greptile.com/) | 仓库图、PR review、custom context/rules、self-hosted 选项 |
| GitBook | [Git Sync](https://gitbook.com/docs/getting-started/git-sync)、[GitBook AI](https://gitbook.com/docs/guides/gitbook-ai) | docs-as-code 同步、面向读者的 AI 搜索/问答与文档分发 |
| Backstage TechDocs | [概览](https://backstage.io/docs/features/techdocs/)、[架构](https://backstage.io/docs/features/techdocs/architecture/) | docs-like-code、静态 HTML、集中发现；推荐 CI 生成/外部存储，Reader 对 JS 做安全处理 |
| PorunC/CodeWiki | [官方仓库](https://github.com/PorunC/CodeWiki)、[v0.6.3 release](https://github.com/PorunC/CodeWiki/releases/tag/v0.6.3)、[issue #2](https://github.com/PorunC/CodeWiki/issues/2) | AST/代码图/GraphRAG/Wiki/MCP/Skill；本项目使用的 0.6.5 高于最新 GitHub release tag，真实仓库崩溃问题仍开放 |

## 横向能力矩阵

符号：`●` 核心能力；`○` 部分/相邻能力；`—` 非公开核心；`?` 一方资料不足。

| 产品 | 本地/自托管 | 结构/图 | 源码证据 | 增量/失效 | 人工修订 | Wiki/UI | Ask | Agent/MCP | 可导出静态 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **CodeWiki 本项目 V0.1** | ● | ● | ● | ● | ● | ○ 静态 | ○ MCP 检索 | ● | ● |
| Qoder | ○ 本地客户端+服务 | ● | ○ | ● | ● | ● | ● | ● | ● Markdown |
| Google Code Wiki | ○ 本地未正式交付 | ● | ● | ● 全量再生 | ? | ● | ● | ○ | ? |
| Cognition DeepWiki | — 公共服务 | ● | ○ | ○ | ? | ● | ● | ● | ○ API读取 |
| DeepWiki Open | ● | ● | ○ | ○ 缓存 | ? | ● | ● | ○ | ○ |
| Copilot Memory/Spaces | — | ○ | ● 验证引用 | ● 记忆淘汰 | ● 文本上下文 | ○ | ● | ● | — |
| Sourcegraph | ○ self-hosted enterprise | ● | ● | ● 索引 | ○ 配置 | ○ | ● | ● | — |
| Cursor | ○ 本地索引器/云 embedding | ○ | ○ | ● | ● Rules | — | ● | ● | — |
| Augment | ○ 本地索引器+服务 | ○ | ○ | ● | ○ rules/context | — | ● | ● | — |
| Greptile | ○ | ● | ● review引用 | ● | ● rules/context | ○ | ● | ● | — |
| GitBook | — | — | ○ 文档来源 | ● Git sync | ● | ● | ● | ● | ● |
| Backstage TechDocs | ● | — | ○ docs-as-code | ● CI build | ● Git | ● | ○ 搜索 | ○ plugins | ● |
| PorunC/CodeWiki | ● | ● | ○ | ○ | — | ● | ● | ● | ○ |

## 对本项目真正有用的差距

| 差距 / 优化 | 竞品信号 | 处置 | 原范围依据 |
|---|---|---|---|
| 真实仓库解析稳定性与可诊断失败 | Sourcegraph、Qoder、DeepWiki Open 都把索引/排除/状态做成显式面 | **blocked evidence**；上游崩溃未修复，保留 fixture provider 与 issue 证据 | V0.1 Evidence Provider；M10 |
| 知识在使用前重新验证 | Copilot Memory | **retain current design**；本项目 snapshot+validity+evidence fail-closed 更严格 | D-009 / V0.1 |
| 人工知识不被自动更新覆盖 | Qoder | **retain current design**；human overlay 已实现 | D-013 / M6 |
| 生成计划/范围控制 | Qoder `wiki_plan.yaml` | **retain current design**；typed planner 已存在，Local Beta 可在现计划中暴露而不新增里程碑 | Planner / M10–M11 |
| 新用户一条路径完成生成→阅读→Ask | Qoder、Google、DeepWiki | **planned only**；M9–M13 已覆盖，不另开功能线 | Local Beta 既定目标 |
| 进度、错误、恢复、历史差异可见 | Qoder、Backstage、Greptile | **planned only**；M11/M12 已覆盖 | Local Beta 既定目标 |
| Agent 标准接入 | DeepWiki MCP、Sourcegraph MCP、GitHub MCP | **retain current design**；七个只读 MCP 工具已交付 | V0.1 MCP |
| 多仓、团队共享、云同步、RBAC | Sourcegraph、Qoder Teams、Backstage | **out of scope** | 单用户、单机、单仓决策 |
| 向量数据库作为权威知识源 | DeepWiki Open/Cursor | **reject**；向量只能是可重建索引，不取代 Canonical IR | local-first / canonical-first |
| PR 自动 review / 代码修改 | Greptile | **out of scope** | 本项目是知识编译器，不是 review agent |
| 文档托管/门户/插件生态 | GitBook、Backstage | **out of scope** | 不做团队文档平台 |
| 大规模拆分架构或改成云服务 | 多数商业产品 | **reject** | 当前个人开发者、无服务器约束 |

## 结论

竞品没有揭示 V0.1 中一个必须新增的大功能。它们反复验证的关键模式——代码回链、持续更新、人工修订、Agent 接入、Ask、生成状态——已经分别落在 V0.1 或获批的 M9–M14 中。真正的关闭风险不是“少一个竞品功能”，而是把尚未运行的 Live 路径和 251 个未实施 Local Beta 执行步骤误写成完成。

## Revision History

- 2026-09-25：以一方来源重做代表性全类别竞品核验与范围处置。
- 2026-10-11：复核 PorunC/CodeWiki issue #2 与 release，外部阻断未解除。
