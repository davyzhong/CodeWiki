---
status: maintained
last-reviewed: 2026-09-12
sources:
  - materials/research/reference-products.md（核验日期 2026-08-24）
  - materials/archives/knowledge-compiler-transfer-archive-public.md 第二编 §8（竞品调研）
  - 各产品官方文档链接见 materials/research/
---

# 行业格局与竞品对照（Landscape）

## 五层能力模型

2026-08 调研形成的行业分层（归档 §8 导语）：

| 层 | 回答的问题 | 代表 |
|---|---|---|
| L1 Code Index | 代码在哪 | Cursor / embedding / search |
| L2 Code Intelligence | 代码怎么连接 | Sourcegraph Code Graph / AST |
| L3 Agentic Retrieval | 此任务该读什么 | Codex / Claude Code / Cody |
| L4 Knowledge Distillation | 系统长期该知道什么 | **Qoder Knowledge Cards / GitHub Copilot Memory / 本项目** |
| L5 Knowledge Representation | 知识如何组织成 Wiki/Card/Graph | Qoder Repo Wiki / PorunC/CodeWiki / DeepWiki |

本项目定位 L4（吸收 L5 的组织方式），并明确：**预编译知识不替代 L3 的实时检索，两者组合使用**（Sourcegraph 调研的核心结论）。

## 竞品对照矩阵

| 产品 | 核心价值 | 对本项目的启发 | 未照搬的部分 |
|---|---|---|---|
| Qoder Repo Wiki + Knowledge Cards | 双视图（人/Agent）同步生成、受影响部分增量更新、人工修订保护 | 双视图同源、增量失效、人工 overlay（D-013） | IDE 封闭实现、无证据合同 |
| Google Code Wiki | 自动结构化 Wiki + 图表 + 源码链接 | 人类视图需要可导航、可回链源码 | 托管形态、模型绑定 |
| GitHub Copilot Memory | 带代码引用的仓库记忆，使用前重新验证 | fail-closed 默认读取（D-009）、Evidence-backed 事实 | 零散 memory 而非完整 IR |
| PorunC/CodeWiki | 本地 AST/代码图/GraphRAG/Wiki/MCP/Skill 全链 | Evidence Provider 底座与公开面合同（D-001/D-002） | Fork 平台、内部数据库 |
| Sourcegraph | 代码智能基础设施 + agentic 检索循环 | 知识与实时检索组合而非替代 | 通用代码搜索平台化 |
| Cursor | Index + Rules + Memory 轻知识模式 | 静态指令表达"如何工作"的价值 | 不承担可验证 IR |
| DeepWiki | Outline/Page Agent 逐页取证生成 Wiki | 沿 imports/callers 追踪取证的工作流 | 无独立治理 IR |
| Qwen CodeScope | 结构图 + 演进图 + embedding | 代码结构与 Git 演进结合的视角 | 作为概念参考，非运行时依赖 |

行业共识信号（当次调研提炼）：**代码图谱 + commit 演进 + embedding 正在合流；source-grounded 生成（禁止按命名猜测、结论带 file:line）成为方向**（Microsoft deep-wiki Skill 明文禁止 "This probably handles..." 类表述）。

## 我们的位置

差异化 = 把这条链路**开放化 + 证据化**：证据引擎可替换、Canonical IR 独立、Claim 可追溯、Agent 读取默认安全、更新与发布可恢复、用 Task Context 验证知识是否真正改善 Agent 任务（M8）。参见 [qoder-deep-dive](qoder-deep-dive.md) 的逐项对比。

## Revision History

- 2026-09-12 从 reference-products 与归档 §8 提炼建卷；第三方能力会变化，引用前先回 materials/research/ 核对官方链接。
