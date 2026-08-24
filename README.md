# CodeWiki

CodeWiki（项目设计名：Knowledge Compiler）是一个面向 Coding Agent 的本地仓库知识编译器。

项目当前处于 V0.1 的 Phase 0：验证外部 CodeWiki 公开 CLI、MCP 或 HTTP 接口能否在不依赖其内部模块和数据库的前提下，提供 Knowledge Compiler 所需的代码事实与源码证据。

## 当前文档

- [V0.1 设计规格](docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md)
- [Phase 0 CodeWiki Adapter Spike 计划](docs/superpowers/plans/2026-08-24-codewiki-adapter-spike.md)

只有 Phase 0 得出可复现的 `go` 结论后，才会开始 Knowledge IR、编译器和 Agent Context 等产品功能实现。

## 项目边界

- 只通过外部 CodeWiki 的公开 CLI、MCP 或 HTTP 接口集成。
- 不导入外部 CodeWiki 的内部实现模块。
- 不读取外部 CodeWiki 的内部数据库。
- 不执行被分析仓库的源码、测试、构建或安装脚本。

