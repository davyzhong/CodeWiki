# CodeWiki 文档库总索引

本仓库文档采用三层治理模型（与产品自身的知识编译方法论一致）：

```
materials/（素材层）     ≈ Evidence   原始、不可变、保真优先：调研笔记、会话归档、上游快照
knowledge/（知识层）     ≈ Canonical IR  提炼后的静态权威知识：每条结论带来源指针，不带日期
superpowers/ 等（工作流层） ≈ Views    从知识库出发的工作产物：规格（specs）、计划（plans）、操作手册（runbooks）、实测报告（spikes）
```

规则：一个事实只在 `knowledge/` 权威定义一次，其他地方链接而非复制；知识文档用 `status + last-reviewed` 管理版本（不携带日期）；`materials/archives/` 为冻结历史，其中的路径引用保持冻结时状态（2026-09-12 重组后部分已失效，属预期）。

## 我要做什么 → 看哪里

| 意图 | 入口 |
|---|---|
| 了解产品是什么、为什么这样设计 | [knowledge/product/](knowledge/product/README.md)（产品定义、决策日志、概念词典） |
| 查行业格局 / 竞品 / 上游 CodeWiki | [knowledge/industry/](knowledge/industry/README.md) |
| 学习本项目的方法论 | [knowledge/methods/](knowledge/methods/README.md)（知识工程、证据优先设计、基准方法） |
| 查系统当前行为（CLI/退出码/MCP/门禁） | [knowledge/system/](knowledge/system/README.md) |
| 查看下一轮产品设计画布 | [design/](design/README.md)（决策过程、完整 HTML、静态预览） |
| 执行下一轮 Local Beta 计划 | [Local Beta 总计划](superpowers/plans/active/2026-09-17-local-beta-master-plan.md)（M9–M14 依赖、门禁和六份子计划） |
| 读权威设计规格（V0.1 合同） | [V0.1 设计规格](superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md) |
| 执行构建/更新/验证操作 | 根 [README 快速上手](../README.md) + [runbooks/](runbooks/) + `bash scripts/verify.sh` |
| 查某个里程碑怎么做的 | [plans/historical/](superpowers/plans/historical/) + [materials/archives/](materials/archives/) |
| 理解项目来龙去脉 | [materials/origin/](materials/origin/)（起源、时间线） |

## 全文档状态表

状态枚举：`active`（当前权威）/ `draft`（待决策）/ `historical`（已完成，供审计）/ `superseded`（已被取代）。

| 文档 | 类型 | 状态 | 说明 |
|---|---|---|---|
| [knowledge/product/](knowledge/product/README.md) | 知识 | active | 产品定义、决策日志（D-001…）、概念词典 |
| [knowledge/industry/](knowledge/industry/README.md) | 知识 | active | 行业格局、设计模式、Qoder 深度分析、上游 CodeWiki |
| [knowledge/methods/](knowledge/methods/README.md) | 知识 | active | 知识工程沉淀、证据优先设计、基准方法论 |
| [knowledge/system/](knowledge/system/README.md) | 知识 | active | as-built 架构、运行时行为参考、安全模型 |
| [design/](design/README.md) | 设计画布 | approved | 2026-09-17 下一轮方向决策、完整 HTML 与静态预览；已由 Local Beta 规格/计划承接 |
| [superpowers/specs/2026-09-17-local-beta-product-design.md](superpowers/specs/2026-09-17-local-beta-product-design.md) | 规格 | active | 已批准的个人开发者、本地单节点 Local Beta 产品与架构基线 |
| [superpowers/plans/active/2026-09-17-local-beta-master-plan.md](superpowers/plans/active/2026-09-17-local-beta-master-plan.md) | 总计划 | active | M9–M14 顺序、文件架构、统一契约、全局门禁和发布定义；链接六份详细子计划 |
| [superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md](superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md) | 规格 | active | V0.1 权威设计合同（含 §5.10/§6.5 人工层、§11.1 已记录偏差） |
| [superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md](superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md) | 计划 | draft | M8 A/B 基准设计，待用户冻结 §8 四项决策 |
| [runbooks/2026-09-02-live-smoke.md](runbooks/2026-09-02-live-smoke.md) | 手册 | active | live 冒烟操作（opt-in 验收项） |
| [spikes/codewiki-public-surface.md](spikes/codewiki-public-surface.md) | 实测 | historical | Phase 0 公开面实测，结论 `go`（固定 fixture 可复现） |
| [superpowers/plans/historical/2026-08-24-codewiki-adapter-spike.md](superpowers/plans/historical/2026-08-24-codewiki-adapter-spike.md) | 计划 | historical | Phase 0 spike 计划（已完成） |
| [superpowers/plans/historical/2026-08-24-fake-provider-module-vertical-slice.md](superpowers/plans/historical/2026-08-24-fake-provider-module-vertical-slice.md) | 计划 | historical | M1 计划（门禁 PASS `9c50176`） |
| [superpowers/plans/historical/2026-08-25-codewiki-module-vertical-slice.md](superpowers/plans/historical/2026-08-25-codewiki-module-vertical-slice.md) | 计划 | historical | M2 计划（门禁 PASS `63ed7ba`） |
| [superpowers/plans/historical/2026-08-25-five-knowledge-types.md](superpowers/plans/historical/2026-08-25-five-knowledge-types.md) | 计划 | historical | M3 计划（门禁 PASS `a443a4d`） |
| [superpowers/plans/historical/2026-08-25-run-orchestrator.md](superpowers/plans/historical/2026-08-25-run-orchestrator.md) | 计划 | historical | M4 计划（门禁 PASS `c8d5970`） |
| [superpowers/plans/historical/2026-08-25-incremental-lifecycle.md](superpowers/plans/historical/2026-08-25-incremental-lifecycle.md) | 计划 | historical | M5 计划（follow-up 由恢复计划 Gate 5 闭合） |
| [superpowers/plans/historical/2026-08-25-v0-1-execution-roadmap.md](superpowers/plans/historical/2026-08-25-v0-1-execution-roadmap.md) | 路线图 | historical | M0–M8 路线图快照（注意旧编号体系） |
| [superpowers/plans/historical/2026-08-25-v0-1-complete-handoff-todo.md](superpowers/plans/historical/2026-08-25-v0-1-complete-handoff-todo.md) | 清单 | superseded | 跨 Agent 交接清单，已被恢复计划取代（见其顶部状态覆盖） |
| [superpowers/plans/historical/2026-08-26-v0-1-mainline-recovery.md](superpowers/plans/historical/2026-08-26-v0-1-mainline-recovery.md) | 计划 | historical | 主航道恢复计划 Gate 1–8（全部通过） |
| [superpowers/plans/historical/2026-08-26-design-conformance-repair.md](superpowers/plans/historical/2026-08-26-design-conformance-repair.md) | 计划 | historical | 设计符合性修复 Task 1–5（全部完成） |
| [materials/origin/](materials/origin/) | 素材 | historical | 项目起源与演进时间线（叙事材料） |
| [materials/research/](materials/research/) | 素材 | historical | 原始调研笔记（Qoder 资料包、参考产品对照）；结论已提炼入 knowledge/industry/ |
| [materials/skills/](materials/skills/) | 素材 | active | 上游 CodeWiki Skill 快照（MIT）+ 本项目 Skill 的文档副本（权威源在 `src/knowledge_compiler/skills/`） |
| [materials/archives/](materials/archives/) | 归档 | historical | 会话归档、完成归档、实施记录（冻结历史，路径不再维护） |
| [materials/source-catalog.md](materials/source-catalog.md) | 治理 | active | 每份素材的来源、许可与处置记录 |

## 命名与状态规范（新增文档适用）

- 计划：`YYYY-MM-DD-<milestone>-<topic>.md`，放入 `plans/active/`；完成后移入 `plans/historical/` 并加状态行。
- 知识文档：无日期、kebab-case；页首 front-matter（`status` / `last-reviewed` / `sources`），文末 Revision History。
- runbook：`YYYY-MM-DD-<topic>.md`。
- 规格保持 `superpowers/specs/`；被批准后即为该版本权威合同。
- 任何文档被取代时：不删除，顶部加状态覆盖注记并在本表更新状态。
