---
status: maintained
last-reviewed: 2026-09-12
sources:
  - materials/archives/knowledge-compiler-transfer-archive-public.md 第二编 §8.9–§8.16、§4.6–§4.7
  - materials/research/qoder/qoder-knowledge-system-analysis.md
  - materials/research/reference-products.md
---

# 跨产品设计模式（Patterns）

从竞品调研中提炼的、可复用于知识类产品的设计模式。每条含：模式、出处、在本项目的应用（→ 决策号见 [decision-log](../product/decision-log.md)）。

## P1 · 三分原则：Evidence ≠ Knowledge ≠ Context

```
Evidence：代码到底是什么（路径/符号/行/哈希）
Knowledge：这些代码意味着什么（语义陈述 + 置信度）
Context：当前任务需要知道哪些（预算化选编）
```

三层绝不合并。知识是证据的语义投影，**证据才是事实**；上下文是知识面向现场的再编译。→ 本项目全部架构的第一原则（D-008/D-014）。

## P2 · 双视图同源

人类视图（叙事 Wiki）与 Agent 视图（高密度 Cards）由同一知识源编译，只做密度与组织方式分化。两个独立生成器必然漂移出矛盾事实（Qoder 的教训与价值均在此）。→ D-003。

## P3 · Source-grounded 生成

生成知识的工作者只允许依据有界证据包；证据不足必须明说（`insufficient_evidence`），禁止按命名/注释/惯例猜测（"PaymentManager probably manages payments" 是反例）；每个结论带 file:line 级引用（deep-wiki Skill、上游 CodeWiki Skill 共同强调）。→ D-008/D-016。

## P4 · 使用前重验证（fail closed）

预编译知识在使用时校验自身新鲜度：Copilot Memory 检查引用在当前分支是否仍有效；本项目把这一点做成硬门禁（快照 + 三代际戳，不匹配拒绝服务）。过期知识比没有知识更危险。→ D-009。

## P5 · 受影响范围的增量更新

代码变化后只重生受影响部分（Qoder 明示此行为；本项目细化为：本地 ChangeSet 先行 → 反向证据索引定位受影响 Claim/对象 → stale 标记 → 选择性重建；提供方 affected 提示只增强不替代本地检测）。控制成本与人工修改风险的关键。→ 规格 §12。

## P6 · 知识规划前置

先生成"应该存在哪些知识"的计划（Qoder `wiki_plan.yaml` 可提交、可评审），再逐目标萃取；Planner 只决定调查什么，不决定结论。规划置信度与知识置信度分离。→ 规格 §5.3。

## P7 · 人工知识治理

人工修订是受保护的一等资产而非生成物上的临时 patch：不被静默覆盖，冲突显式呈现（Qoder 反向同步回 Cards；本项目细化为 supplement/override 边界层 + conflicted 目标 + 退役归档）。→ D-013。

## P8 · 编排器独占生命周期

语义工作者（LLM/Agent）只做"请求→结果"的转换；调度、重试、修复计数、发布资格、终态判定全部归确定性编排器。模型不能决定事实或删除（retirement 是确定性证明授权的）。→ D-006/D-010。

## P9 · 知识随版本走

知识身份绑定 `(repository, branch, commit[, dirty+tree-hash])`，不是"当前状态"的全局快照；跨分支/脏树的知识不互相冒充（Qoder 团队共享要求同仓库同分支亦是佐证）。→ domain-model 快照概念。

## P10 · 分阶段多 Agent 建模

Qoder 官方叙事中的多 Agent 分阶段分析（规划→分域建模→综合→验证）；开源等价物 = 一个持久化队列 + 可替换的语义工作者（内置 LLM 或 Skill），关键在合同与验证而非 Agent 数量。→ D-006。

## Revision History

- 2026-09-12 从归档 §8 与 Qoder 分析提炼建卷。
