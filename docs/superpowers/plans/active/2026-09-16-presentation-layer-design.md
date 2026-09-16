---
status: active
created: 2026-09-16
updated: 2026-09-16
owner: knowledge-compiler
decides: 机器读取模式与人类阅读模式的交互层设计（v3，实施反馈迭代版）
supersedes: v2 调研综合版（同文件 git 历史，2026-09-16）；v1 口头方案
---

# 展示层设计：机器读取 × 人类阅读（v3）

> 目标：为 Canonical IR 之上的消费层定义两套交互模式——机器读取（Machine Access）与人类阅读（Human Presentation）。
> v3 = v2 的 Phase 1/2 已全部实施（提交 `3bdc657`，765 tests 绿）+ 实施反馈驱动的修正与下一阶段细化。本文 §1–§4 为已冻结的 as-built 基线，§5 起为待实施。

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

三条铁律（源自 [patterns](../../../knowledge/industry/patterns.md) P1/P2 与 D-023）：

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

---

# v3 增补（2026-09-16，实施反馈迭代）

## 5. as-built 基线冻结（v2 Phase 1/2 交付确认，提交 `3bdc657`）

已实现并固化为契约的能力：`web_url` config 与 evidence permalink（module/sources 页）、单文件 HTML 双主题/类型过滤/覆盖率条/Ask(evidence-only)、`exports/site/` 多页静态站点（目录表搜索/过滤/排序 + 详情页 + 相对路径可托管）、serve 从 site 目录服务（`.html` 白名单 + 穿越/symlink 防护 + 单文件回退）、MCP `structuredContent` 双返回 + 意图化描述 + `provenance` 头。**单源双渲染**（`_render_page_bodies`）与**确定性编译**（site 与单文件逐字节一致测试）是本层的两条不可回退红线。

## 6. 实施反馈驱动的修正（V3 Phase 2.5，小而真）

| # | 问题（实施中发现） | 修正 | 依据 |
| --- | --- | --- | --- |
| F1 | **typed 页零证据引用**：`compile_typed_wiki` 不接收 pack，flow/rule/architecture/tech-stack 页的 Verified claims 只有 id + statement，无 Evidence 行、无 permalink | typed 渲染器接收 pack，每条 claim 渲染 Evidence 行并附 permalink 链接（与 module 页同构），五类型证据体验一致 | 修复 v2 实施遗漏（P3 source-grounded 的前端化） |
| F2 | **Ask 是页面级而非 Claim 级**：INDEX 按页面 text 截断，命中返回整页 | INDEX 细化到 Claim 粒度（statement + evidence_ids + 所属对象 + 证据链接），命中显示 Claim 卡片并跳对象页锚点 | evidence-only 的本意；对位 DeepWiki Q&A 的答案锚定 |
| F3 | **诚实层看不见 insufficient**：覆盖率条只算 published/stale，`insufficient_evidence` 终态只在 build 报告里 | 目录页读取 `state/runs` 活跃 run 的 target_results，把"尝试过但证据不足"并入覆盖率条（灰红段）与目录表（insufficient 行，无链接），与"从未规划"区分 | 诚实覆盖的产品语义补全 |
| F4 | 目录表只有类型过滤 | 补 status 过滤 chips（verified / stale / insufficient） | Backstage catalog 过滤惯例 |
| F5 | 固定 270px 侧栏，窄屏破损 | `@media (max-width:900px)` 折叠为顶部抽屉；目录表横向滚动 | 可托管 ⇒ 手机访问是真实场景 |
| F6 | human overlay 在前端不可见 | 目录表与详情页加 "human notes" 徽章（来自 overlays 的 sections/notes 计数） | P7 人工治理的前端可见性 |

## 7. 下一阶段（V3 Phase 3，M8 优先级之后）

| # | 能力 | 设计 | 先例 |
| --- | --- | --- | --- |
| F7 | **世代时间线 + 知识 diff** | `site/history.html`：RunStore 遍历 runs，逐代列 published/retired/insufficient 计数；选两代 diff 出新增/退役/Claim 变更清单；数据编译时内嵌 | GitHub compare |
| F8 | **Related 卡 + 局部关系图** | 详情页复用 MCP `_relations_of` 的关系数据：Related 对象卡片列表（forward + inbound）+ 局部静态 SVG 图（对象→关联对象，CSS hover 高亮）。**明确不做全局力导向图** | Backstage EntityCatalogGraphCard（局部优先）；Quartz 教训（graph 全局视图是锦上添花） |
| F9 | **Task Context 预览** | `knowledge serve` 加只读 GET `/api/preview?task=` 端点：回环内调 `retrieve_task_context`（预算取 config 默认、上限封顶），返回 markdown + 命中对象清单。site 的 Ask 面板运行时探测该端点：可达则升级"真检索预览"（显示 Agent 将收到的上下文包与门禁判定），纯静态托管时回落 F2 的 Claim 级客户端检索 | Swagger "try-it-out" 的只读等价物；dbt serve 本地富交互 |
| F10 | **托管手册** | runbooks 新增"exports/site 静态托管"：GitHub Pages/内网流程、只发布 site 目录的边界说明（site 是公开视图 ≠ 公开 .knowledge 内部状态） | dbt 生产托管分离 |

## 8. 自主决策记录（依据用户 2026-09-16 授权：缺决策信息参考竞品）

- F9 走 serve 端点而非编译期预生成：任务描述是运行时输入；端点保持 GET/无状态/回环/预算封顶，不破坏"serve 只是 host"的只读语义。
- F8 不做全局图谱：对象数会随仓库增长，力导向布局的确定性与可维护性成本高；局部 Related 已覆盖"这个知识跟谁有关"的主问题。
- F3 的 insufficient 展示为"显示但不链接"行：这些对象没有 published 页面，链接会 404——诚实优于虚饰。

## 9. 验收标准

- F1–F6、F7–F8：全部产物纳入确定性测试（两次 compile 逐字节一致）；F1/F2 各带内容断言（typed 页含 blob 链接；INDEX 含 claim 语句）。
- F9：serve 端点测试（200/404/预算上限/仅回环）+ site 回落路径测试。
- 每 Phase 完成跑 `bash scripts/verify.sh` 全绿后提交推送（main-only）。

## Revision History

- 2026-09-16 v3：实施反馈迭代——冻结 as-built 基线（§5）、六项修正（§6）、Phase 3 细化（§7）、自主决策记录与验收标准（§8–9）。
- 2026-09-16 v2：三轮竞品调研综合方案（§0–4，Phase 1/2 已于同日实施）。
