# Qoder Knowledge Cards 官方文档内容记录

- 来源：[Qoder Knowledge Cards 中文官方文档](https://docs.qoder.com/zh/user-guide/knowledge-engine/knowledge-cards)
- 抓取日期：2026-08-24
- 来源 ID：`qoder-knowledge-cards-zh`
- 抓取哈希：`16d0992a18a0262505141f828736044c1a96c59e898aabf472042ff3f9f467a2`

## 页面定位

Knowledge Cards 与 Repo Wiki 同步生成，是面向 Agent 直接消费的高密度知识单元。官方页面把它们定位为代码萃取后的稳定知识，而不是每次任务都重新搜索出来的临时上下文。

Cards 会持续跟踪提交中的代码变化。页面强调实时性和准确性，但没有公开 freshness 算法、证据引用格式或验证状态机。

## 页面结构

1. 使用场景；
2. 卡片类型；
3. 生成建议；
4. 修改已有知识；
5. 团队共享、Git 共享与多语言；
6. 计费。

## 三类知识卡

| 类型 | 主要内容 | Agent 使用场景 |
|---|---|---|
| Architecture | 模块设计、服务依赖、关键决策 | 理解系统边界和模块协作，回答架构问题 |
| Spec | 编码标准、命名、接口约定、业务约束 | 新功能对齐规范、Review、漏洞修复时检查违例 |
| Tech Stack | 框架、库和版本 | 评估依赖兼容性、生成符合项目技术环境的代码 |

这三类分别对应“系统是什么”“工作必须遵守什么”“实现环境是什么”。相比完整 Wiki，它们更像紧凑、可检索的约束与背景单元。

## 生成策略

- 官方建议在主分支和核心开发分支生成，以覆盖最重要的业务逻辑与代码结构。
- 生成过程中已完成的卡片可以预览，不必等整个批次结束。
- 页面没有说明部分完成的卡片能否立即被 Agent 使用，也没有公开批次失败时的一致性策略。

分支建议意味着 Cards 不是脱离版本的全局知识；同一仓库的不同分支可能具有不同内容。官方团队共享也要求成员打开相同仓库的相同分支。

## Agent 使用场景

### Architecture

Agent 可直接利用预构建架构信息回答模块设计和服务依赖问题，从而减少对整库的重复探索。

### Spec

规范知识直接参与编码判断，例如命名、接口设计、业务逻辑约束、Review 检查和风险识别。这类知识不一定能从 AST 确定性提取，可能同时来自代码惯例、人工输入和项目文档。

### Tech Stack

技术栈卡用于回答框架/版本问题、评估新依赖和生成风格一致的代码。版本准确性依赖 package manifest、lockfile、构建配置和当前分支状态。

## 修改已有知识

用户可以通过 `/knowledge` 描述变更，或上传本地文件作为参考。修改结果进入同一知识体系，而不是另建一个脱离 Cards 的备注区。

页面没有提供 Card 字段 Schema、人工内容标记、Evidence、confidence、validity、冲突或审核字段，因此不能仅凭文档判断其内部治理能力。

## 共享和多语言

| 方式 | 行为 |
|---|---|
| Teams 自动共享 | 管理员启用知识中心；相同仓库和分支的成员生成时获取团队最新知识，成员修改同步给团队 |
| Git 共享 | `.qoder/repowiki` 提交到远端，其他成员通过 `git pull` 获取 |
| 多语言 | 生成时选择中文或 English，每种语言使用独立子目录，如 `zh/`、`en/` |

自动团队共享只在 Teams 版本提供，Git 是不依赖该版本的替代路径。

## 与 Repo Wiki 的关系

官方两页共同确认：

- Wiki 和 Cards 同步生成；
- 人工修改 Wiki 可以反向同步到 Cards；
- `wiki_plan.yaml` 分别提供 `repowiki` 与 `knowledgecard` 的规划提示；
- 两者都可放入 `.qoder/repowiki` 并通过 Git 分享；
- 两者都支持中文/英文。

这说明两种视图共享生成与维护管线，但页面没有说明谁是 Canonical Source、两者如何映射、Card 是否独立存储，以及冲突时由哪一侧获胜。

## 计费

生成和更新 Cards 会消耗 Credits。官方页面只提供用量查询入口，没有公开成本模型。

## 页面图片清单

| 图片 | 官方地址 | 表达内容 |
|---|---|---|
| Knowledge Cards | `https://g-adoc.alcasset.com/sync/maas_docs/qoder/master/global/media/images/knowledge-cards_705510f804bc.png` | 卡片界面 |
| 修改知识 | `https://g-adoc.alcasset.com/sync/maas_docs/qoder/master/global/media/images/knowledge-edit_705510f804bc.png` | `/knowledge` 修改入口 |

## 可确认事实与未知实现

| 可由官方页面确认 | 页面没有公开 |
|---|---|
| 三类 Card：Architecture、Spec、Tech Stack | Card Schema、ID 和对象关系 |
| 与 Repo Wiki 同步生成 | Canonical 数据源及双向编译机制 |
| 持续跟踪 commit 变化 | freshness、stale、影响分析和删除策略 |
| 支持 `/knowledge` 人工修改 | 人工字段的锁定、冲突和审计模型 |
| 支持 Teams/Git 共享和多语言 | 合并、并发、跨分支与语言漂移策略 |
| 面向 Agent 高密度消费 | Context budget、检索排名、Evidence 展开方式 |
