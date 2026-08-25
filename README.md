# CodeWiki

CodeWiki（项目设计名：Knowledge Compiler）是一个面向 Coding Agent 的本地仓库知识编译器。

V0.1 的 Phase 0 已完成，Gate 结论为 `go`。M1（Fake Provider + Module 垂直切片）M1.1—M1.7 已全部实现：M1.6 通过规格审查，当前基线 320 个测试全绿，剩余独立审查与 M1 出口门禁。2026-08-25 设计修订（用户决策）：人工编辑保护以 human overlay 层进入 V0.1（新 M6），多语言维持单构建单语言；原视图/基准里程碑顺延为 M7/M8。准确入口见完整 handoff To-do。

## 当前文档

- [V0.1 设计规格](docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md)
- [Phase 0 CodeWiki Adapter Spike 计划](docs/superpowers/plans/2026-08-24-codewiki-adapter-spike.md)
- [Phase 0 公共接口报告](docs/spikes/codewiki-public-surface.md)
- [Phase 1 Fake Provider 垂直切片计划](docs/superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md)
- [V0.1 总执行路线图与 To-do List](docs/superpowers/plans/2026-08-25-v0-1-execution-roadmap.md)
- [V0.1 完整跨 Agent 接续 To-do（M1–M8）](docs/superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md)
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
