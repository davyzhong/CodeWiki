# CodeWiki

CodeWiki（项目设计名：Knowledge Compiler）是一个面向 Coding Agent 的本地仓库知识编译器。

V0.1 主链路已全线贯通（恢复计划 Gate 1–8 全部完成），设计符合性修复计划 Task 1–5 全部落地：LocalGit + 公开 CodeWiki 证据、调研驱动的多目标规划、统一结构/语义验证（含两次修复尝试与 insufficient_evidence/invalid/conflicted/retired/skipped 终态）、持久化 Orchestrator、原子多对象发布与崩溃恢复、增量失效/重试/确定性退役（退出码 0/1/2，增量面 `codewiki update`/`graph affected` 仅在本地 diff 后调用且失败可隔离）、受保护的人类 overlay（只读校验、Markdown 边界合并、override 冲突判定、退役字节级归档）、确定性 Wiki/聚合页/源索引/独立 HTML（`wiki_generation` 落后语义）、verified-only SQLite FTS5 索引与预算化 ContextRetriever（快照/代际/工作树哈希精确门禁）、`compile/context/open/serve/status/validate` 全部真实行为（validate 按清单驱动），以及七个只读 MCP 工具（`knowledge-mcp`，stdio JSON-RPC）。当前离线基线为 750 项测试通过（连续两遍结果一致），另有 1 项显式 opt-in live 覆盖默认跳过；`knowledge build --executor llm|agent` 与 `knowledge update --executor llm|agent` 为生产入口，Fake Provider 仅保留在测试/演示。M8 基准工作在全部技术门通过后启动。

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

## 快速上手

```bash
knowledge build --executor llm        # 主构建（LLM 走 LiteLLM，Agent 走队列协议）
knowledge compile                     # 重试确定性 Wiki/HTML + 重建 FTS 索引
knowledge context "任务描述"           # 预算化任务上下文（verified-only，门禁 fail closed）
knowledge open                        # 打开 HTML Wiki（落后时警告）
knowledge serve                       # 仅回环只读 Wiki 服务
knowledge status                      # 对象状态 + 最新 run 的 target 结果
knowledge update --executor llm      # 增量更新（0 complete / 1 failed / 2 partial）
knowledge edit <object-id>           # 编辑受保护的人类 overlay
knowledge-mcp <repository-root>      # 七个只读 MCP 工具（stdio JSON-RPC）
```

后续实现必须以 Phase 0 捕获的真实公共 DTO 为依据，不能把外部 CodeWiki 的内部实现当成稳定合同。

## 项目边界

- 只通过外部 CodeWiki 的公开 CLI、MCP 或 HTTP 接口集成。
- 不导入外部 CodeWiki 的内部实现模块。
- 不读取外部 CodeWiki 的内部数据库。
- 不执行被分析仓库的源码、测试、构建或安装脚本。
