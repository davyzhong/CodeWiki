---
status: maintained
last-reviewed: 2026-09-12
sources:
  - materials/research/qoder/（三页官方资料的内容记录 + 抓取哈希 + 综合分析，核验 2026-08-24）
  - materials/archives/knowledge-compiler-transfer-archive-public.md 第二编 §2–§4
---

# Qoder 知识系统深度分析（Qoder Deep Dive）

Qoder 是本项目最直接的产品参照（阿里系 IDE 内知识引擎）。原始逐页笔记见 [materials/research/qoder/](../../materials/research/qoder/)；本文是提炼后的结构性认识。

## 产品闭环

```
Git Repository + branch
  → wiki_plan.yaml（可提交的规划约束）
  → 代码索引 / 多 Agent 分阶段分析建模
  → Repo Wiki（人类叙事视图）
  → Knowledge Cards（Agent 高密度视图）
  → 编码任务消费
  → 代码变更 → 受影响部分重生 / 同步
  → 受保护的人工知识 → 团队服务或 Git 共享（.qoder/repowiki）
```

## 三种资产的职责

| 资产 | 读者 | 密度 | 控制面 |
|---|---|---|---|
| Repo Wiki | 开发者（Agent 亦可查询） | 页面级、叙事性 | `wiki_plan.yaml`、人工编辑 |
| Knowledge Cards（Architecture/Spec/Tech Stack） | Agent | 卡片级、任务可消费 | `/knowledge` 命令 |
| wiki_plan.yaml | 生成系统与维护者 | 配置 | 页面白名单、生成意图、include/exclude |

## 最值得借鉴的五个机制

1. **双视图不是两个生成器**——Wiki 与 Cards 同步生成，人工对 Wiki 的修订回流 Cards；价值在防止人类理解与 Agent 理解分叉。
2. **规划是受治理的输入**——模板/关注点/页面结构/文件范围都是可提交配置，比会话内临时提示稳定且可评审。
3. **更新以受影响范围为单位**——只重生变化命中的部分。
4. **人工知识不被静默覆盖**——修订是新知识资产；但锁定粒度、冲突裁决、审计结构未公开。
5. **Git 是开放分发面**——`.qoder/repowiki` 随仓库流转，即使有 Teams 服务。

## 本项目刻意更严格之处（差异化所在）

| Qoder 文档所述 | 本项目 |
|---|---|
| 强调准确与随代码更新，未公开事实级证据合同 | 每个事实字段 → Claim → Evidence（路径/符号/行范围/双哈希），验证在 Claim 级 |
| 提醒更新 Wiki | 默认读取 fail closed（快照+代际不匹配即拒绝服务，D-009） |
| 未说明代码删除后知识如何退役 | 四重确定性证明才允许退役，模型永无删除权（D-010） |
| 未公开发布原子性与恢复语义 | journal 事务 + manifest 最后替换 + 故障注入验证（D-011） |
| 输入上限 10k 文件、IDE 内 | 本地 CLI/MCP，仓库边界由 scope limits 显式管理 |

## Qoder 官方资料未回答的十个问题（当时的调研清单，复现其能力前必须实测）

目录/Schema 结构、页面↔卡片映射粒度、人工保护粒度与冲突裁决、受影响范围算法、跨分支/语言/成员的知识身份、部分生成失败时的一致性、删除/重命名处理、Cards 是否携带源码引用并预验证、导出格式保真度。→ 这些正是本项目用公开合同 + 测试钉死的部分。

## Revision History

- 2026-09-12 从 qoder 资料包与归档 §2–§4 提炼建卷。
