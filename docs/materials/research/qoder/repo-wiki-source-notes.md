# Qoder Repo Wiki 官方文档内容记录

- 来源：[Qoder Repo Wiki 中文官方文档](https://docs.qoder.com/zh/user-guide/repo-wiki)
- 抓取日期：2026-08-24
- 来源 ID：`qoder-repo-wiki-zh`
- 抓取哈希：`f20a737cd3bec5d333cfe12037187b6427c1b75ffbf68cecb1e64fff0b35d560`

## 页面定位

Repo Wiki 被描述为与代码共同演进的结构化项目文档。它不只服务浏览：在知识查询、代码解释、功能开发和缺陷修复中，Agent 会把预生成 Wiki 与实时上下文结合，以减少重复探索并获得更完整的仓库理解。

## 页面结构

官方页面的主体由以下部分组成：

1. 使用场景；
2. Repo Wiki 生成与更新；
3. 人工干预；
4. `/knowledge` 命令；
5. `wiki_plan.yaml` 前置配置；
6. 团队与 Git 共享；
7. 多语言；
8. 计费。

## 使用场景

### 架构与实现查询

预构建的架构知识用于回答模块实现方式、服务依赖关系等问题。Qoder 的产品主张是：当答案已经存在于 Repo Wiki 时，Agent 可以减少为同一类问题重复调用代码搜索工具。

### Agent 驱动的开发

在上下文窗口有限时，Wiki 用于加速定位与理解，官方明确列出新增功能和修复缺陷两类任务。这里的 Wiki 不是最终答案；它与当前任务上下文一起使用。

## 生成和更新状态

官方页面列出三类内容同步路径：

| 触发 | 输入状态 | 系统行为 |
|---|---|---|
| 初次生成 | 项目还没有 Wiki | 从仓库建立首份 Wiki |
| 代码变更 | 函数签名、类、API 等已记录对象发生变化 | 检测不一致，只重新生成受影响部分 |
| Git 文档变更 | `.qoder/repowiki` 中的 Markdown 被直接编辑 | 检测 Git 内容与产品视图差异，通过同步吸收修改 |

这形成了两个变化方向：`code -> generated knowledge` 与 `Git knowledge edits -> product knowledge`。文档没有公开具体的差异算法、依赖传播规则或事务边界。

## 输入约束

- 只支持 Git 仓库。
- 仓库至少要有一次提交。
- 单项目最多 10,000 个文件；更大的项目应通过索引排除配置缩小范围。

这些限制说明 Qoder 以“可识别的 Git 版本 + 有界索引范围”作为知识生成前提，而不是把任意目录当作无版本文本集合。

## 人工干预模型

### `/knowledge`

对话命令支持四类动作：

| 动作 | 语义 |
|---|---|
| 生成 | 首次创建 Wiki 或 Cards |
| 修改 | 局部改变已有知识 |
| 补充 | 向已有知识追加内容 |
| 重写 | 重做一个页面或卡片 |

命令可同时接收文字意图和本地设计/API 文档。官方页面称人工修改会被识别并保护，在后续自动更新中不被直接覆盖，并会反向同步到相应 Knowledge Cards。

文档没有公开“人工片段”如何标识、代码与人工知识冲突如何裁决、保护粒度是页面/段落/字段还是 Claim，以及删除代码后人工知识如何退休。这些是复现该能力前必须实测的问题。

### `wiki_plan.yaml`

文件位置：

```text
<repository>/.qoder/repowiki/wiki_plan.yaml
```

该文件可随 Git 共享，用于生成前控制方向和范围。功能性结构可归纳为：

```yaml
version: 1
repowiki:
  template: architecture | product_requirement
  notes: [{text, author}]
  documents: [{title, goal, parent, hints}]
knowledgecard:
  notes: [{text}]
scope:
  include: []
  exclude: []
```

字段语义：

| 字段 | 作用 |
|---|---|
| `repowiki.template` | 选择技术架构或产品需求导向的预制模板 |
| `repowiki.notes` | 在规划阶段注入关注点和写作意图 |
| `repowiki.documents` | 页面白名单；给出后按指定标题、目标和层级规划页面 |
| `knowledgecard.notes` | 引导知识卡的规划和模块划分 |
| `scope.include/exclude` | 用 `.gitignore` 风格模式限定可见文件 |

配置修改不会自动重建已有知识，需要人工触发生成或重新生成。

## 共享模型

Qoder 提供两条共享路径：

1. Teams 版本可在 Web 控制台开启知识中心，使同一仓库、同一分支的团队成员自动获得团队知识更新。
2. 其他场景可把 `.qoder/repowiki` 提交到 Git，团队成员通过常规 `git pull` 获取 Wiki。

**推断：** 因为团队共享要求成员打开同一 repository 和 branch，知识身份或检索作用域很可能至少包含这两个维度。官方页面没有公开身份合同，也没有说明跨分支合并、重命名、cherry-pick 或非线性历史下的处理策略。

## 多语言与存储

- 当前页面列出中文与 English。
- 不同语言保存到独立目录，例如 `repowiki/zh/`、`repowiki/en/`。
- Wiki 和 Knowledge Cards 都位于 `.qoder/repowiki` 范围内，但官方页面没有公开完整文件 Schema。

## 计费

生成和更新会消耗 Qoder Credits。官方页面把成本暴露在用量页面，但没有给出按文件、Token、页面或变更范围的计算公式。

## 页面图片清单

| 图片 | 官方地址 | 表达内容 |
|---|---|---|
| Repo Wiki 主界面 | `https://docs.qoder.com/images/repo-wiki.png` | Wiki 产品界面 |
| `/knowledge-plan` | `https://docs.qoder.com/images/knowledge-plan-command.png` | 创建或编辑前置计划 |
| Wiki 共享 | `https://docs.qoder.com/images/wiki-sharing.png` | 团队/Git 共享界面 |

图片未复制进仓库，避免未经许可再分发；地址保留用于回到官方原始素材。

## 可确认事实与未知实现

| 可由官方页面确认 | 页面没有公开 |
|---|---|
| Git 仓库和至少一次提交是前提 | 代码索引、依赖图和检索的内部实现 |
| 支持受影响部分更新 | 受影响范围算法与 stale 传播规则 |
| 人工修改受到保护并同步到 Cards | 锁定粒度、冲突解决、审计数据结构 |
| 有可版本化的 `wiki_plan.yaml` | Wiki/Card 的完整 Canonical Schema |
| 支持团队服务和 Git 两种共享 | 发布事务、并发修改和失败恢复 |
| 支持中文/英文独立目录 | 多语言内容的同源身份与漂移检测 |
