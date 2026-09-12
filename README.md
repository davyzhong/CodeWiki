# CodeWiki

CodeWiki（项目设计名：Knowledge Compiler）是一个面向 Coding Agent 的本地仓库知识编译器。

V0.1 主链路已全线贯通（恢复计划 Gate 1–8 全部完成），设计符合性修复计划 Task 1–5 全部落地：LocalGit + 公开 CodeWiki 证据、调研驱动的多目标规划、统一结构/语义验证（含两次修复尝试与 insufficient_evidence/invalid/conflicted/retired/skipped 终态）、持久化 Orchestrator、原子多对象发布与崩溃恢复、增量失效/重试/确定性退役（退出码 0/1/2，增量面 `codewiki update`/`graph affected` 仅在本地 diff 后调用且失败可隔离）、受保护的人类 overlay（只读校验、Markdown 边界合并、override 冲突判定、退役字节级归档）、确定性 Wiki/聚合页/源索引/独立 HTML（`wiki_generation` 落后语义）、verified-only SQLite FTS5 索引与预算化 ContextRetriever（快照/代际/工作树哈希精确门禁）、`compile/context/open/serve/status/validate` 全部真实行为（validate 按清单驱动），以及七个只读 MCP 工具（`knowledge-mcp`，stdio JSON-RPC）。当前离线基线为 752 项测试通过（连续两遍结果一致），另有 1 项显式 opt-in live 覆盖默认跳过；`knowledge build --executor llm|agent` 与 `knowledge update --executor llm|agent` 为生产入口，Fake Provider 仅保留在测试/演示。M8 基准工作在全部技术门通过后启动。

## 当前文档

文档库采用三层治理（素材 → 静态知识库 → 工作流产物），完整导航与全文档状态表见 [docs/README.md](docs/README.md)。

- [静态知识库](docs/knowledge/README.md)：产品定义与决策日志（D-001…）、行业格局与上游 CodeWiki、方法论、as-built 系统参考——设计工作的事实基础
- [V0.1 设计规格](docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md)（active，权威合同）
- [M8 A/B 基准设计草案](docs/superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md)（draft，待冻结任务集/harness/预算）
- [Live 冒烟手册](docs/runbooks/2026-09-02-live-smoke.md)
- 历史计划（M1–M5、恢复计划、符合性修复等）与归档见 [docs/README.md 状态表](docs/README.md#全文档状态表)

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

## 验证闭环

每次更新后运行一条命令完成生产验证：

```bash
bash scripts/verify.sh        # 双遍套件一致性 + compileall + diff-check + pip-audit + live 冒烟自动探测
```

live 阶段在 `codewiki` 0.6.x 与 `KNOWLEDGE_EXTRACTION_MODEL`/`KNOWLEDGE_LIVE_REPOSITORY` 齐备时自动执行真实端到端冒烟，否则明确报告缺失项跳过；`REQUIRE_LIVE=1` 强制失败闭合，`VERIFY_FAST=1` 跳过第二遍。Mimosa 深度扫描是发布前的 IDE 工具步骤，不在脚本内。

## 项目边界

- 只通过外部 CodeWiki 的公开 CLI、MCP 或 HTTP 接口集成。
- 不导入外部 CodeWiki 的内部实现模块。
- 不读取外部 CodeWiki 的内部数据库。
- 不执行被分析仓库的源码、测试、构建或安装脚本。
