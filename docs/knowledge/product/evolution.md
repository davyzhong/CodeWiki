---
status: maintained
last-reviewed: 2026-10-11
sources:
  - docs/materials/origin/timeline.md
  - docs/materials/archives/
  - docs/superpowers/specs/
  - docs/superpowers/plans/
---

# 项目演进与当前状态

## 一句话脉络

ATLAS 与 Enterprise Intelligence 的资料治理实践暴露了“静态整理无法随代码演进”的问题；项目因此把来源治理、Canonical IR、证据锚点、失效语义和多视图编译组合成一个 local-first 代码知识编译器。

## 阶段地图

| 时段 | 阶段 | 可验证结果 | 状态 |
|---|---|---|---|
| 2026-08-22—24 | 来源实践与产品形成 | 跨项目方法提炼、竞品研究、V0.1 规格、Phase 0 Go/No-Go | completed |
| 2026-08-24 | 上游公共面 spike | 锁定 `codewiki 0.6.5` CLI/MCP/fixture 合同 | completed |
| 2026-08-25 | M1 垂直切片 | Evidence → Module Knowledge → validation → deterministic compile → publication | completed |
| 2026-08-25—26 | M2–M7 主链 | LocalGit、五知识类型、运行编排、增量生命周期、human overlay、Wiki/Card/Context、MCP | completed |
| 2026-08-26—09-02 | 设计符合性与生产门 | 精确快照、退役、恢复、脚本化验证、752×2 基线 | completed |
| 2026-09-02—16 | M8 与真实上游 | A/B harness/dry-run；上游中型仓库崩溃复现并报 issue | frozen-blocked |
| 2026-09-12 | 三层知识治理 | materials / knowledge / workflow 分层，静态知识库与决策日志 | completed |
| 2026-09-16—17 | 产品方向定稿 | Local Beta 单机设计、HTML 原型、M9–M14 总计划 | approved-not-started |
| 2026-09-25—10-11 | 封存审计 | 竞品刷新、依赖修复、浏览器实测、工程/端面/清理/知识/归档审查 | closing-audit |

## 两条不能混淆的产品线

### V0.1 Knowledge Compiler

代码已经实现，离线门禁 790 passed / 1 skipped。它是 CLI + MCP + 静态产物的开发者工具；产品假设仍缺真实 A/B 和 live smoke 证据，因此只能判定“有条件技术冻结”，不能宣称价值验证完成。

### Local Beta M9–M14

它把现有引擎包装成个人开发者可操作的本地产品：服务/API、可靠仓库解析、任务生命周期、阅读体验、Ask parity 与发布验收。六份计划按行首 checkbox 逐项重算共 251 个执行步骤（M9 48、M10 44、M11 43、M12 40、M13 41、M14 35），截至 2026-10-11 全部未完成；设计已批准不等于实现。每份文档说明中的 checkbox 示例不是执行步骤，不计入总数。

## 关键转折

1. 上游 CodeWiki 被降为可替换 Evidence Provider，而不是产品内核。
2. Claim 必须绑定 Evidence，Agent 默认读取 fail closed。
3. 人工判断通过 overlay 层保护，不能被自动重生成覆盖。
4. 本机是执行与权威数据所在地；云只可能是未来部署地点，不形成第二套知识。
5. 项目不追求竞品功能总和；所有差距必须回到既定目标和规格裁决。
6. 每次重大设计定稿必须同步 README 与正式文档；每次中期冻结/最终封存必须执行完整审计。

## 当前关闭条件

- V0.1 可在 CI 锁文件门、文档一致性和最终验证闭合后“技术冻结”；M8/Live 限制必须保留。
- 整个项目不能在 M9–M14 仍 active 的情况下标记完成。要么继续实施，要么由用户明确取消/延期并转为历史未交付计划。
- GitHub repository 的 `archived` 开关属于公开归档动作；只有关闭裁决完成并经用户明确要求后才能执行。

## Revision History

- 2026-09-25：从历史时间线提炼可维护的阶段状态与关闭条件。
- 2026-10-11：更新真实测试基线、浏览器审计结果与 M9–M14 精确执行步骤数。
