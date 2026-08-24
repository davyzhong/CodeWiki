# Skill 资料索引

Skill 表达“Agent 应该如何工作”，Knowledge Card 表达“Agent 已经知道什么”。两者互补，但不应混成同一类资产。

## 已保存的第三方 Skill 单文件快照

`upstream-codewiki/` 保存 PorunC/CodeWiki 官方 Codex Skill 的固定提交快照：

- 上游提交：`7be8f702504cbd69aec6491a2e4e81f5311e0ba6`
- 原始路径：`backend/skills/codewiki/SKILL.md`
- 许可：MIT，许可文本与版权声明随快照保存
- 用途：研究紧凑 Evidence Pack、Wiki page queue、citation validation 和 HTML export 的 Agent 工作流

此快照只包含原始 `SKILL.md`；它引用的 `scripts/` 和 `references/` 没有复制。因此它是研究资料，不是完整可安装包，也不是本项目当前安装或自动执行的 Skill。

## 历史上拟议、但尚未生成的四个 Skill

早期完整会话归档提出过以下目录和职责，但并没有生成可执行文件：

| 名称 | 历史职责 | 当前状态 |
|---|---|---|
| `knowledge-planner` | 从结构和证据索引生成 `knowledge-plan.yaml`，不写最终知识 | proposal only |
| `knowledge-extractor` | 按计划收集证据并生成知识对象，不根据名称猜测 | proposal only |
| `knowledge-validator` | 判断 Claim 是否受 Evidence 支持，不重写知识 | proposal only |
| `knowledge-maintainer` | 根据变更维护对象，早期设想不得覆盖 `human_locked` | proposal only；V0.1 已改为 generated-only，不含 human lock |

后续批准的 V0.1 规格收敛成两个用户入口：`/knowledge-build` 与 `/knowledge-update`。它们通过同一个持久化 RunOrchestrator 调用 prepare/lease/evidence/submit/verify/finalize 协议，而不是四个彼此独立、各自持有状态的 Skill。

因此，本素材库不伪造四份 `SKILL.md`。如果未来进入 Agent executor 实现阶段，应基于当时的 CLI 合同重新设计，并将历史提案只作为设计输入。
