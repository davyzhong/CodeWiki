---
status: draft
created: 2026-09-16
owner: knowledge-compiler
decides: 机器读取模式与人类阅读模式的交互层设计（v2，竞品调研综合版）
supersedes: 会话内 v1 口头方案（2026-09-16，未落档）
---

# 展示层设计：机器读取 × 人类阅读（v2）

> 目标：为 Canonical IR 之上的消费层定义两套交互模式——机器读取（Machine Access）与人类阅读（Human Presentation）。
> 本文是 2026-09-16 三轮调研（本地知识库 landscape/patterns/upstream + 外部 DeepWiki/dbt docs/Quartz/TiddlyWiki/coverage.py/OpenAPI/MCP 官方/Backstage）综合后的 v2 方案，取代同日 v1 口头方案。

## 0. 调研输入与设计裁决总表

| 来源 | 观察到的做法 | 采纳 | 不采纳的理由 |
| --- | --- | --- | --- |
| [DeepWiki](https://docs.devin.ai/work-with-devin/deepwiki)（Cognition） | wiki.json 显式页面规划（title/purpose/**parent 树状层级**，"no more, no less"）；自动架构图 + 源码链接；Ask Devin 生成式 Q&A | 页面树、覆盖率诚实展示 | 生成式 Q&A 无证据合同；托管形态 |
| [dbt docs](https://docs.getdbt.com/docs/build/documentation) | `generate` 产**静态站点目录**；`serve` 仅本地预览；生产=托管静态目录；交互 lineage DAG | 三段式交付形态 | 无 provenance/证据语义可学 |
| [Quartz](https://quartz.jzhao.xyz/) | Markdown→静态站；wikilinks/backlinks；graph view 为社区插件 | 双向链接、图谱后置为增强件 | SPA 路由与构建链 |
| [TiddlyWiki](https://tiddlywiki.com/static/SingleFileApplication.html) | 单文件自包含应用极限（数据内嵌、客户端搜索/标签/自保存） | 单文件交付的信心上限 | 自编辑架构超出报告件需求 |
| [coverage.py](https://coverage.readthedocs.io/) / [pytest-html](https://pytest-html.readthedocs.io/en/latest/user_guide.html) | 自包含单文件报告：内联 CSS/JS、**列头点击排序**、折叠行、过滤、离线可用 | 单文件交互清单 | — |
| [OpenAPI/Swagger](https://swagger.io/specification/v3/) | spec-as-single-source-of-truth：机器合同 + 渲染器（交互型 Swagger UI / 阅读型 Redoc）分离 | IR=合同、前端=可替换渲染器 | try-it-out 的执行语义（我们只读） |
| [MCP 官方](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) | structuredContent + TextContent 双返回；工具按意图设计、token-efficient | 机器模式合规基线 | — |
| [Backstage catalog](https://backstage.io/docs/features/software-catalog/) | **目录表(搜索/过滤) / 实体详情页(可组合卡片) / 关系图卡** 三件套；标准化关系语义 | Cards 视图的组织范式 | 平台级重量 |

## 1. 总架构：一份 IR，三段交付，两种消费者

```
                      Canonical IR（唯一真相源：objects/** + manifest.yaml）
                          │ 确定性编译（compile，幂等逐字节一致）
        ┌─────────────────┼──────────────────────┐
   机器读取模式                人类阅读模式（三段交付）
   ─────────────              ─────────────────────────────────
   knowledge-mcp    ──────▶   exports/repo-wiki.html   单文件归档件（内联交互）
     （行为接口）              exports/site/             静态站点目录（多页）
   SQLite FTS5      ◀───┐     knowledge serve            本地只读服务器（从 site/ 起）
     （检索引擎）      │
   Markdown+YAML  ───┘      三段共享同一渲染器代码；serve 只是 host，不是第二后端
     （逃生舱口）
```

三条铁律（源自 [patterns](../../knowledge/industry/patterns.md) P1/P2 与 D-023）：

1. **前端是渲染器，不是真相源**（OpenAPI 教训）：IR 是合同，HTML 是视图；换渲染器不换事实，任何视图字段 IR 里必须存在。
2. **渐进增强**：站点无 JS 也能完整阅读（纯 HTML+CSS 锚点导航），JS 只增强搜索/过滤/折叠/图谱——保 grep、保降级、保确定性。
3. **双视图同源在检索层同样成立**：人类 Ask 与机器 context_for_task 调用同一个检索引擎（FTS5+门禁），只是包装不同。

## 2. 机器读取模式 v2（补强而非重构）

三介质分工与契约见 v1（MCP=行为 / FTS5=检索 / 文件=逃生舱口），v2 增加三个合规动作：

| # | 动作 | 依据 |
| --- | --- | --- |
| M1 | 七个工具的返回检查 `structuredContent` + TextContent 序列化双返回 | MCP 规范 SHOULD |
| M2 | 工具描述重写为意图导向（"当 Agent 需要 X 时调用"），参数 schema 收紧 | MCP 官方/社区共识 |
| M3 | 每个返回体必带 provenance 头（generation/commit/working_tree_hash + 对象计数），消费方可校验新鲜度 | P4 fail-closed 的接口化 |

不做的：向量数据库（决策过的方向：FTS5 可解释可复现；语义检索若加，只作为 retrieval 层的补充信号，不换底座）；不做写接口（七工具保持只读）。

## 3. 人类阅读模式 v2

### 3.1 交付三段（dbt 形态，修正 v1 的"serve 为主交互面"）

| 形态 | 内容 | 用途 |
| --- | --- | --- |
| `exports/repo-wiki.html` | 单文件、内联 CSS/JS、coverage.py 式交互 | 归档/邮件分享/`knowledge open` |
| `exports/site/` | 多页静态目录（每对象一页 + 索引页 + assets） | 拷走即可托管（GitHub Pages 等） |
| `knowledge serve` | 从 site/ 目录起的回环只读服务器 | 本地交互预览（保持现状语义） |

### 3.2 信息架构（Backstage 三件套 + DeepWiki 页面树）

- **目录层（Catalog）**：`site/index.html` = 可搜索/过滤的知识目录表（列：类型、状态、模块、Claim 数、证据数、更新代），列头点击排序、类型/状态过滤——coverage.py 交互范式。
- **详情层（Entity page）**：每对象一页，锚点分区 = 可组合卡片：
  - Scope 卡（三代际戳表）
  - Claims 卡（每条 Claim 可折叠证据摘录 + **evidence permalink**：`(path, lines, commit)` 编译为 GitHub/GitLab 永久链接）
  - Related 卡（关联对象，先卡片列表后图谱）
  - Human overlay 卡（`knowledge edit` 的受保护人工注记，来源标注清楚）
- **导航层**：侧栏目录从平面 per-type 升级为 **parent 树**（architecture 为根 → 域分组 → module/flow 页），DeepWiki `parent` 字段同构，数据来源是 planner 的目标规划。
- **诚实层（差异化）**：首页覆盖率条（五类型 × verified/insufficient/retired 红黄绿），缺口是特性不是缺陷——DeepWiki 不展示缺口，我们展示。

### 3.3 交互清单（按阶段）

| 交互 | 阶段 | 先例 |
| --- | --- | --- |
| 暗色模式（prefers-color-scheme）、类型过滤、列头排序、证据折叠 | P1 | coverage.py / pytest-html |
| evidence permalink 跳源码行 | P1 | DeepWiki 源码链接 |
| 多页站点 + serve 路由 + 目录表 | P2 | dbt docs |
| Task Context 预览（输入任务→显示 Agent 将收到的上下文与门禁判定） | P2 | Swagger "try-it-out" 的只读等价物 |
| 世代时间线 + 两代知识 diff（新增/退役/Claim 变更） | P3 | GitHub compare |
| 关系图谱（先详情页局部 Related 图，静态 SVG；全局力导向后置） | P3 | Backstage EntityCatalogGraphCard / Quartz |

### 3.4 Ask：evidence-only 应答（对位 DeepWiki Q&A）

DeepWiki 卖点是 "talk to your wiki"（生成式、信不信由你）。我们的对位物**不生成**：`Ask` = 同一个 FTS5+门禁引擎的检索式应答——返回命中 Claim 列表 + 证据锚点 + 未覆盖时的诚实空态（"知识库未覆盖此问题"）。它是 Task Context 预览的自然延伸（人机共用检索层），也把 fail-closed 哲学贯穿到人类前端。放在 P2 尾或 P3。

## 4. 落地路线

1. **Phase 1（最小收益最大）**：单文件 HTML 增强——暗色、类型过滤、证据折叠美化、evidence permalink（需 config 增加 repo web URL 字段）、首页覆盖率条。
2. **Phase 2**：编译器拆双产物（单文件 + site/ 目录）+ serve 从目录服务 + 目录表/详情页模板 + Task Context 预览；机器侧同步 M1–M3 合规动作。
3. **Phase 3（M8 后）**：世代时间线与知识 diff、关系图谱、Ask(evidence-only)。

约束提醒：所有视图产物必须保持确定性（同输入逐字节一致，暗色模式用环境媒体查询不影响字节）；无构建链、无外部 CDN、无前端框架依赖；serve 仅回环只读白名单路由不变。

## 5. 待用户决策

1. evidence permalink 的 repo web URL 来源：`knowledge init` 时配置（推荐，随仓库版本控制）vs 每次 compile 参数。
2. Phase 1 是否现在实施，还是排到 M8 之后（当前两大阻塞仍优先）。
3. Ask(evidence-only) 是否保留在路线图（若用户更想要生成式 Q&A，需重新评估与 fail-closed 哲学的一致性）。
