---
status: no-migration-proposed
last-reviewed: 2026-10-11
scope: freeze-cleanup
sources:
  - git ls-files
  - docs/README.md
---

# 路径迁移图

本轮没有发现必须通过重命名才能关闭的路径问题，因此不提出 `git mv` 批次。历史计划、归档、素材、知识和工作流已经按三层模型分区；为“看起来更整齐”再次移动会破坏大量稳定链接和历史追溯。

| 观察 | 当前路径 | 处置 |
|---|---|---|
| 已完成 Phase 0 计划 | `docs/superpowers/plans/historical/` | 保留；修正文档中仍指向旧 active 路径的引用 |
| 设计原型 | `docs/design/` | 保留为 approved design evidence，不宣称已交付 |
| 项目来源材料 | `docs/materials/` | 保留为 evidence/archive 层 |
| 维护知识 | `docs/knowledge/` | 保留为静态知识库 |
| 当前封存计划 | `docs/superpowers/plans/active/` | 审计完成后再转 completed；本轮不提前移动 |

任何未来移动必须先更新本表为 `old → new → redirect/index update → link check`，并取得用户对重命名的明确批准。

## Revision History

- 2026-09-25：完成路径审计；无必要迁移。
- 2026-10-11：续审确认仍无删除或重命名批次，因此没有需要用户批准的文件迁移动作。
