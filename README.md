# CodeWiki

CodeWiki（项目设计名：Knowledge Compiler）是一个面向 Coding Agent 的本地仓库知识编译器。

V0.1 当前处于主链路恢复阶段。M0—M5 的合同、五种知识类型、真实主构建和增量生命周期已经实现；M6 human overlay 运行时语义以及 M7 Wiki/HTML/FTS/MCP 仍需完成端到端接线。2026-08-26 已修复旧 CLI 占位成功、单对象 generation、Module-only extraction union、不可恢复的 semantic context，以及未接线的失效/重试/确定性退役；`knowledge build --executor llm|agent` 与 `knowledge update --executor llm|agent` 现通过 LocalGit、公开 CodeWiki、五类 Planner、统一验证器和持久 Orchestrator 执行，Fake Provider 仅保留在测试/演示入口。当前离线基线为 603 项测试通过，另有 1 项显式 opt-in live 覆盖默认跳过；准确入口见恢复计划和完整 handoff To-do。

## 当前文档

- [V0.1 设计规格](docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md)
- [Phase 0 CodeWiki Adapter Spike 计划](docs/superpowers/plans/2026-08-24-codewiki-adapter-spike.md)
- [Phase 0 公共接口报告](docs/spikes/codewiki-public-surface.md)
- [Phase 1 Fake Provider 垂直切片计划](docs/superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md)
- [V0.1 总执行路线图与 To-do List](docs/superpowers/plans/2026-08-25-v0-1-execution-roadmap.md)
- [V0.1 完整跨 Agent 接续 To-do（M1–M8）](docs/superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md)
- [V0.1 主航道恢复计划](docs/superpowers/plans/2026-08-26-v0-1-mainline-recovery.md)
- [2026-08-25 项目接续归档清单](docs/project-materials/archives/2026-08-25-archive-manifest.md)
- [2026-08-25 M1 实施会话归档](docs/project-materials/archives/2026-08-25-m1-implementation-session.md)
- [2026-08-25 V0.1 执行完成归档与交叉验证说明](docs/project-materials/archives/2026-08-25-completion-archive.md)
- [项目起源与原始素材库](docs/project-materials/README.md)

后续实现必须以 Phase 0 捕获的真实公共 DTO 为依据，不能把外部 CodeWiki 的内部实现当成稳定合同。

## 项目边界

- 只通过外部 CodeWiki 的公开 CLI、MCP 或 HTTP 接口集成。
- 不导入外部 CodeWiki 的内部实现模块。
- 不读取外部 CodeWiki 的内部数据库。
- 不执行被分析仓库的源码、测试、构建或安装脚本。
