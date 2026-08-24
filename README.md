# CodeWiki

CodeWiki（项目设计名：Knowledge Compiler）是一个面向 Coding Agent 的本地仓库知识编译器。

V0.1 的 Phase 0 已完成：公开 `codewiki 0.6.5` CLI 能在不依赖内部模块和数据库的前提下提供最小 Evidence Provider 合同，Gate 结论为 `go`。项目正在进入 Fake Provider + Module Knowledge 的首个垂直切片。

## 当前文档

- [V0.1 设计规格](docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md)
- [Phase 0 CodeWiki Adapter Spike 计划](docs/superpowers/plans/2026-08-24-codewiki-adapter-spike.md)
- [Phase 0 公共接口报告](docs/spikes/codewiki-public-surface.md)
- [Phase 1 Fake Provider 垂直切片计划](docs/superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md)
- [V0.1 总执行路线图与 To-do List](docs/superpowers/plans/2026-08-25-v0-1-execution-roadmap.md)
- [项目起源与原始素材库](docs/project-materials/README.md)

后续实现必须以 Phase 0 捕获的真实公共 DTO 为依据，不能把外部 CodeWiki 的内部实现当成稳定合同。

## 项目边界

- 只通过外部 CodeWiki 的公开 CLI、MCP 或 HTTP 接口集成。
- 不导入外部 CodeWiki 的内部实现模块。
- 不读取外部 CodeWiki 的内部数据库。
- 不执行被分析仓库的源码、测试、构建或安装脚本。
