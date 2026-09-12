# Qoder Repo Wiki + Knowledge Cards 综合分析

本页综合三份 Qoder 官方资料，区分官方公开行为、合理推断和 CodeWiki 自己的设计选择。

## 产品闭环

```text
Git Repository + branch
  -> wiki_plan.yaml planning constraints
  -> code index / engineering awareness
  -> multi-Agent analysis and modeling
  -> Repo Wiki              (human-readable)
  -> Knowledge Cards        (Agent-dense)
  -> chat / coding tasks
  -> code or Git knowledge changes
  -> affected regeneration / sync
  -> protected human knowledge
  -> team service or Git sharing
```

官方资料可以支持这条行为链，但没有公开每一步的内部数据结构。因此这里不能断言 Qoder 使用特定图数据库、Claim 模型、向量库或编排框架。

## 三种资产的职责

| 资产 | 主要读者 | 内容密度 | 主要控制面 |
|---|---|---|---|
| Repo Wiki | 开发者，也供 Agent 查询 | 页面级、叙事性、适合导航 | `repowiki.template/notes/documents`、人工编辑 |
| Knowledge Cards | Agent | 卡片级、高密度、任务可消费 | `knowledgecard.notes`、`/knowledge` |
| `wiki_plan.yaml` | 生成系统与维护者 | 配置性 | 页面白名单、生成意图、include/exclude |

这支持 CodeWiki 的基本假设：人类页面和 Agent 知识不应完全相同，但应由一个共享知识过程维护。

## Qoder 最值得借鉴的机制

### 1. 双视图不是两个独立生成器

Wiki 与 Cards 同步生成，人工对 Wiki 的修订还会回到 Cards。其价值不只是输出两套文件，而是避免人类理解与 Agent 理解长期分叉。

### 2. 规划是受治理的输入

`wiki_plan.yaml` 把模板、关注点、页面结构和源文件范围变成可提交的配置。这比在一次对话里临时提示更稳定，也让团队能够 Review 知识生成意图。

### 3. 更新以受影响范围为单位

页面明确说明代码变化后只重新生成受影响部分，而不是每次全量重做。这是控制成本、延迟和人工修改风险的关键。

### 4. 人工知识不会被静默覆盖

Qoder 把人的修订视为新的知识资产，而不是生成物上的临时 patch。这是长期团队使用所需的能力，但实现需要字段级来源、冲突和锁定语义。

### 5. Git 是可选但重要的知识分发面

`.qoder/repowiki` 让知识跟随仓库和分支流转。即使有 Teams 服务，Git 仍是开放的共享路径。

## 对当前 CodeWiki 的具体映射

| Qoder 机制 | CodeWiki V0.1 选择 | 处理方式 |
|---|---|---|
| Repo Wiki + Cards | Wiki + Cards + Task Context | 采用并增加任务级预算化上下文 |
| 同步生成 | Canonical Knowledge IR 编译多视图 | 采用；明确 IR 为唯一事实知识存储 |
| `wiki_plan.yaml` | `.knowledge/plan.yaml` + tracked config | 适配；计划与运行状态分开 |
| 分支/提交相关 | repository snapshot + eligible-file baseline | 强化；默认读取前校验 snapshot/generation |
| 受影响部分更新 | ChangeSet + Evidence reverse index | 采用并要求 stale 传播可解释 |
| 人工编辑保护 | M6 human knowledge layer（2026-08-25 用户决策改判为采用） | 采用 IR 层 overlay：`.knowledge/human/` + `knowledge edit`，supplement/override 保护语义，冲突显式化；不引入编译产物反向合并 |
| Cards 面向 Agent | verified-only Cards / FTS | 强化；stale/conflicted 默认不进入 Agent 读取 |
| 团队自动共享 | 不在 V0.1 范围 | 延后到团队产品阶段 |
| Git 共享 | tracked `.knowledge/` 核心文件 | 采用；缓存和运行状态默认忽略 |
| 中文/英文目录 | 输出语言配置（2026-08-25 用户确认维持单构建单语言） | 方向一致；跨语言同源身份仍待设计 |
| Credits | 本地/外部模型成本报告 | 不照搬计费，但需要 Token/调用/失败成本统计 |

## CodeWiki 刻意比 Qoder 文档更严格的地方

### Claim 与 Evidence

Qoder 文档强调准确和随代码更新，但没有公开每个知识事实的证据合同。CodeWiki 规格要求事实字段由 Claim 支撑，Claim 绑定路径、符号、行范围、版本和内容哈希。

### 默认 fail closed

Qoder 页面描述提醒与更新；CodeWiki 则要求 Agent 默认读取同时检查当前仓库 snapshot、active generation 和 Agent view generation。不一致时返回 `knowledge_update_required`，而不是继续把旧卡片当成当前知识。

### 确定性 retirement

官方资料没有说明代码删除后如何删除知识。CodeWiki 不允许模型或 Planner omission 授权 retirement；必须完成当前快照上的来源消失、精确候选搜索、入边检查和查询完整性检查。

### 可恢复发布

CodeWiki 将 canonical objects、Cards、FTS、plan 和 manifest 纳入可恢复发布事务，并最后切换 manifest。Qoder 文档没有公开其原子性和失败恢复语义。

## 仍需实验验证的问题

1. `.qoder/repowiki` 的真实目录和 Card Schema 是什么？
2. Wiki 与 Card 的对应粒度是一页一张、一页多张还是图关系？
3. 人工编辑保护采用页面、段落、字段还是语义 diff？
4. 人工知识与新代码证据冲突时如何提示和裁决？
5. 增量更新如何确定受影响页面，是否跨依赖传播？
6. 同一知识在多个分支、语言和团队成员之间如何保持身份？
7. 部分生成、Credits 耗尽、模型失败时，哪些内容可见或可被 Agent 消费？
8. 删除、重命名和代码移动如何处理旧知识？
9. Cards 是否携带源码引用，Agent 使用前是否验证当前版本？
10. 导出能力包含哪些格式，是否保留证据与版本信息？

这些问题决定了“产品体验相似”和“可验证地复现知识系统”之间的差距。当前 CodeWiki 不需要等待所有问题有答案，但不得用 Qoder 的产品描述替代自己的合同与测试。

## 结论

Qoder 最重要的参考价值不是某个 UI，而是一个知识生命周期：以代码和分支为输入，规划人类与 Agent 的双视图，允许有治理的人工输入，按变更维护，再通过团队服务或 Git 分发。

CodeWiki 的差异化方向是把这个生命周期开放化和证据化：Evidence Provider 可替换、Canonical IR 独立、Claim 可追溯、Agent 读取默认安全、更新与发布可恢复，并用 Task Context 验证知识是否真正改善 Coding Agent 任务。
