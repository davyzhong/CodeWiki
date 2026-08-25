# CodeWiki

CodeWiki（项目设计名：Knowledge Compiler）是一个面向 Coding Agent 的本地仓库知识编译器。

V0.1 的 Phase 0 已完成，Gate 结论为 `go`。M1.1—M1.5 已实现并通过规格与质量审查；M1.6 可恢复发布事务已实现但尚待独立审查；M1.7 尚未开始。当前执行已暂停并转为跨 Agent 接续，准确入口见完整 handoff To-do 和 2026-08-25 归档清单。

## 当前文档

- [V0.1 设计规格](docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md)
- [Phase 0 CodeWiki Adapter Spike 计划](docs/superpowers/plans/2026-08-24-codewiki-adapter-spike.md)
- [Phase 0 公共接口报告](docs/spikes/codewiki-public-surface.md)
- [Phase 1 Fake Provider 垂直切片计划](docs/superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md)
- [V0.1 总执行路线图与 To-do List](docs/superpowers/plans/2026-08-25-v0-1-execution-roadmap.md)
- [V0.1 完整跨 Agent 接续 To-do（M1–M7）](docs/superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md)
- [2026-08-25 项目接续归档清单](docs/project-materials/archives/2026-08-25-archive-manifest.md)
- [2026-08-25 M1 实施会话归档](docs/project-materials/archives/2026-08-25-m1-implementation-session.md)
- [项目起源与原始素材库](docs/project-materials/README.md)

后续实现必须以 Phase 0 捕获的真实公共 DTO 为依据，不能把外部 CodeWiki 的内部实现当成稳定合同。

## 项目边界

- 只通过外部 CodeWiki 的公开 CLI、MCP 或 HTTP 接口集成。
- 不导入外部 CodeWiki 的内部实现模块。
- 不读取外部 CodeWiki 的内部数据库。
- 不执行被分析仓库的源码、测试、构建或安装脚本。
