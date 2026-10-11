---
status: maintained
last-reviewed: 2026-10-11
sources:
  - docs/materials/validation/project-freeze-2026-09-25/competitor-sources.md
  - docs/materials/research/qoder/
  - docs/materials/research/reference-products.md
---

# 行业格局与竞品对照

## 能力分层

| 层 | 回答的问题 | 代表产品 |
|---|---|---|
| L1 Code Index | 代码在哪 | Cursor、Sourcegraph Search、Augment |
| L2 Code Intelligence | 代码怎样连接 | Sourcegraph Code Navigation、PorunC/CodeWiki、Greptile |
| L3 Agentic Retrieval | 当前任务该读什么 | Sourcegraph Deep Search、Cursor、Augment、MCP 工具 |
| L4 Knowledge Distillation | 系统长期应知道什么 | Qoder Knowledge Cards、Copilot Memory、**本项目** |
| L5 Knowledge Representation | 如何让人和 Agent 消费知识 | Qoder Repo Wiki、Google Code Wiki、DeepWiki、GitBook、TechDocs |

本项目定位 L4，并从 L5 编译 Wiki / Cards / Task Context；它不试图替代 L1–L3 的实时搜索。Canonical IR 是权威层，FTS、embedding 或 Agent prompt 都只能是可重建索引/视图。

## 2026-09-25 代表性全类别对照

| 代表 | 最值得保留的行业信号 | 本项目状态 |
|---|---|---|
| Qoder | 增量 Wiki、生成范围控制、人工修改保护、Git 同步、Agent 引用 | planner、增量失效、overlay、静态产物和 MCP 已覆盖；可视化工作流属 M9–M13 |
| Google Code Wiki | 持续再生成、源码链接、图表、Wiki 内 Ask | 源码证据/图/静态 Wiki 已覆盖；Ask UI 未交付 |
| Copilot Memory/Spaces | 使用前验证、自然淘汰、可组合上下文 | snapshot+validity+evidence fail-closed 已覆盖且更明确 |
| DeepWiki / DeepWiki Open | Wiki、Ask、MCP、自托管 RAG | 本项目更重治理和确定性；不把 embedding 设为事实源 |
| Sourcegraph | 多机制检索、代码导航、agentic search；为安全和维护以 Search 替代 enterprise embeddings | 支持“知识 + 实时检索”组合；不自建通用搜索平台 |
| Cursor / Augment | 本地变更感知、版本化规则、实时上下文 | rules/skills 与 snapshot 生命周期已覆盖；不做 IDE |
| Greptile | 代码图、引用化 review、团队规则 | 图和规则可借鉴；PR review 越界 |
| GitBook / TechDocs | docs-as-code、静态发布、发现与反馈 | 静态生成与 Git 保存已覆盖；门户/团队运营越界 |
| PorunC/CodeWiki | 本地 AST/图/RAG/Wiki/MCP 全链 | 仅作为可替换 Evidence Provider；真实仓库稳定性仍是外部阻断 |

完整逐产品矩阵、官方来源和 gap disposition 见 [竞品来源与能力核验](../../materials/validation/project-freeze-2026-09-25/competitor-sources.md)。

## 范围裁决

- **封存前应关闭**：依赖安全、锁文件一致性、状态/路径/文档事实一致性。
- **保留当前设计**：证据优先、Canonical IR、人工 overlay、只读 MCP、静态可重建视图。
- **缺证据**：真实上游解析、Live smoke、真实 GUI 的可用性/无障碍证据。
- **按既定计划而非新增范围**：Local Beta 的生成进度、阅读、Ask、历史与恢复界面。
- **明确越界**：云托管、多租户、团队 RBAC、多仓门户、PR review、IDE、向量数据库权威化。

## Revision History

- 2026-09-12：从历史研究提炼初版行业格局。
- 2026-09-25：以一方来源刷新产品状态，新增分类完备矩阵和范围裁决。
- 2026-10-11：复核上游 CodeWiki 状态未变；不新增竞品功能范围。
