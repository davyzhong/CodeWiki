# 项目演进时间线

| 日期 | 阶段 | 形成的认识或产物 |
|---|---|---|
| 2026-08-22—23 | ATLAS 知识库治理 | 建立规划资料的状态标签、证据分级、来源映射、稳定 ID、演进时间线和入库校验。 |
| 2026-08-23—24 | Enterprise Intelligence 重建 | 建立“来源证据 → 事实/代码对象 → 派生知识页与索引”的层级，落实源码锚点、确定性 ID、可重建 JSONL、覆盖与安全门禁。 |
| 2026-08-24 | 知识萃取产品研究 | 比较 Google Code Wiki、Qoder Repo Wiki/Knowledge Cards、GitHub Copilot Memory、PorunC/CodeWiki 和静态指令文件。 |
| 2026-08-24 | Knowledge Compiler 概念形成 | 确定 local-first、Canonical Knowledge IR、Repo Wiki + Knowledge Cards + Task Context 三种编译视图。 |
| 2026-08-24 | V0.1 规格冻结 | 明确 CodeWiki 只作为可替换 Evidence Provider；Claim 必须绑定 Evidence；默认 Agent 读取 fail closed。 |
| 2026-08-24 | Phase 0 计划 | 把上游公开接口验证设为 Go/No-Go Gate，禁止在真实契约未知时凭假设设计 Adapter DTO。 |
| 2026-08-24 | 仓库迁移与更名 | 项目远端最终使用 `davyzhong/CodeWiki`，本地工作区也统一更名为 `CodeWiki`。 |
| 2026-08-24 | Phase 0 完成 | 锁定并实测公开 `codewiki 0.6.5` 表面；CLI 足以覆盖 V0.1 所需最小契约，结论为 `go`。 |
| 2026-08-24 | Phase 1 计划 | 基于实测 DTO 设计 Fake Provider + Module Knowledge 的首个垂直切片。 |
| 2026-08-25 | M1.1—M1.5 完成 | Repository/Evidence、Module Knowledge、Fake Provider、验证/语义核验和确定性编译器全部实现并通过独立规格与质量审查。 |
| 2026-08-25 | M1.6 实现 | 完成可恢复 generation publication、38 个故障边界和幂等恢复测试；独立审查因额度/服务限制留待接续。 |
| 2026-08-25 | 跨 Agent 接续归档 | 冻结当前 main 状态，形成 M1–M7 完整 To-do、当天实施会话和项目归档清单，供其他 Agent 继续并最终回交验收。 |
| 2026-08-25 | M1 完成与整片终审 | M1.6/M1.7 规格与质量评审全部通过（多轮修复见完成归档 §5），M1 七项出口门禁 PASS（`9c50176`），329 项测试全绿并推送。 |
| 2026-08-25 | 设计修订：人工知识层入 V0.1 | 用户决策将人工编辑保护纳入 V0.1：规格新增 §5.10/§6.5（overlay 合同、conflicted 目标结果、退役字节归档），里程碑重排为 M6=人工层、M7=视图、M8=基准（`5e1f677`）。 |
| 2026-08-25 | M2–M7 CLI 面完成 | 真实 LocalGit + 公开 CodeWiki 适配器、五知识类型、持久化 RunOrchestrator、增量生命周期库、human overlay 合同与 `knowledge edit`、全部主 CLI 注册；551 项测试（`7892063`），完成归档供交叉验证（`8997529`）。 |
| 2026-08-26 | 主航道恢复计划 Gate 1–8 | 闭合完成归档记录的全部 gap：CLI 真实化、原子多对象发布、通用类型化编排器、真实主构建（LiteLLM/Agent 双执行）、增量生命周期全接线、human overlay 运行时语义、确定性 Wiki/HTML/FTS/ContextRetriever 与精确快照门禁、七个只读 MCP 工具与安全边界；最终技术门 653×2 一致（`c821674`→`6a1b2b3`）。 |
| 2026-08-26→09-02 | 设计符合性修复 | 审计出的 5 项设计差距全部闭合：调研驱动多目标规划、tracked plan/manifest 生命周期状态、clean/dirty 精确快照检索门禁、真实增量提示与完整退役证明、可达终态与两次修复尝试；三项刻意偏差记入规格 §11.1；752×2 离线套件一致（`e090283`→`ab259fa`）。M4.8b per-type 夹具延后项经核查由五类型 fixture worker、provider 公开面合同测试与 opt-in live 测试组合覆盖，正式关闭。 |
| 2026-09-02 | 生产验证闭环与 M8 准备 | pip-audit 无已知漏洞（扫描器离线匹配为模式级误报）；`scripts/verify.sh` 一键验证（双遍套件、compileall、diff-check、pip-audit、live 冒烟自动探测）成为每次更新的固定入口；M8 A/B 基准设计草案完成（预注册判定标准，待用户冻结任务集/harness/预算）；live 冒烟 runbook 就绪（`1ef6770`、`7fe5a90`）。 |

## 贯穿始终的决策链

```text
真实资料治理困难
  -> 需要来源、状态和演进
  -> 事实知识还需要代码锚点和确定性合同
  -> 一次性整理无法随仓库更新
  -> 人和 Agent 需要不同密度的知识视图
  -> 建立独立 Canonical Knowledge IR
  -> 借用上游 CodeWiki 的公开证据能力
  -> 先实测公共接口，再实现最小产品切片
```
