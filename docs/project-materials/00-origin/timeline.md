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
