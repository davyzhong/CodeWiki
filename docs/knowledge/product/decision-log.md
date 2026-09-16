---
status: maintained
last-reviewed: 2026-09-12
sources:
  - materials/archives/knowledge-compiler-transfer-archive-public.md（第一编决策对话、第二编技术设计）
  - superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md（含 §5.10/§6.5/§11.1 修订）
  - materials/archives/2026-08-25-completion-archive.md §3.2（设计修订）
  - superpowers/plans/historical/2026-08-26-v0-1-mainline-recovery.md
  - superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md
---

# 决策日志（Decision Log）

按时间收录影响产品形态与架构的全部决策。每条含：决策、背景问题、被否方案、来源、状态（`effective` 生效中 / `superseded` 已被后续决策取代）。新决策追加编号，不修改旧条目。

---

## D-001 · Adapter 而非 Fork：上游 CodeWiki 只作证据引擎

- **日期**：2026-08-24
- **决策**：不整体 Fork PorunC/CodeWiki，通过版本化 `EvidenceProvider` 接口把它作为默认证据引擎；自建 Knowledge 层。
- **背景**：上游已覆盖 AST/代码图/GraphRAG/Wiki/MCP/Skill（MIT），但它是 Alpha 阶段的完整平台（FastAPI/React/双数据库），且核心模型是 code graph/chunks/wiki pages，不是我们要验证的 Claim 级知识 IR。
- **被否方案**：A. 整体 Fork（继承全部复杂度，容易变成"CodeWiki 功能分支"）；C. 完全独立实现（大量重复建设，最晚才能验证产品假设）。
- **来源**：转移归档第一编消息 013/039–040（用户批准方案 B）。
- **状态**：effective。

## D-002 · 只走公开接口，禁内部依赖

- **日期**：2026-08-24
- **决策**：只通过上游的公开 CLI/MCP/HTTP 集成；禁止导入其内部模块、读取其 SQLite/PostgreSQL 内部数据库。Phase 0 把公开接口验证设为阻塞性 Go/No-Go Gate。
- **背景**：上游内部 Schema 不稳定，绑定即锁死 Alpha 内部结构。
- **被否方案**：直接读上游数据库（快但把内部 Schema 当合同）。
- **来源**：规格 §4/§5.2；Phase 0 计划（结论 `go`，`codewiki 0.6.5` 实测）。
- **状态**：effective。

## D-003 · 双视图同源：Wiki 与 Cards 从同一 IR 编译

- **日期**：2026-08-24
- **决策**：Repo Wiki 与 Knowledge Cards 不允许各自生成事实，必须从同一 Canonical IR 编译；上游自带 Wiki 生成器只作参照基线，不作事实源。
- **背景**：两套独立生成器会表达不同结论（Qoder 的双视图给了正面参照）。
- **来源**：转移归档消息 014–016（用户确认 Qoder 式双视图）、规格 §4。
- **状态**：effective。

## D-004 · 五知识类型（而非 Qoder 三类）

- **日期**：2026-08-24
- **决策**：`Architecture / Module / Flow / Rule / TechStack` 五类；不采用 Qoder 的 `Architecture / Spec / TechStack`（`Spec` 会混合业务规则、流程和编码规范）。
- **来源**：转移归档消息 033–034（用户选 B）。
- **状态**：effective（V0.1 全部五类已实现）。

## D-005 · V0.1 输入 = 单个本地 Git 仓库（终局按多源规划）

- **日期**：2026-08-24
- **决策**：V0.1 只处理一个本地 Git 仓库；但 `RepositoryProvider` 接口与 `repo+branch+commit` 身份模型按"本地路径 + Git URL + 多仓库"的终局预留边界。Git URL 归 V0.1.x，多仓库归 V0.2。
- **背景**：用户指出这是"先做工具迭代"还是"终局设计讨论"的层级问题；结论是长期方向按 B 规划、首版按 A 交付。
- **来源**：转移归档消息 019–025。
- **状态**：effective。

## D-006 · 双执行模式，一个编排器

- **日期**：2026-08-24
- **决策**：Codex Skill（Agent 队列协议）与内置 LiteLLM 两种执行模式共用同一 `RunOrchestrator`、同一版本化请求/结果合同；编排器独占调度/重试/发布权。
- **背景**：避免两套萃取逻辑。
- **被否方案**：V0.1 只做 Skill（快）或只做内置 LLM（简单）。
- **来源**：转移归档消息 027–029（用户选 C 两种都做）；M4 计划与实现。
- **状态**：effective。

## D-007 · V0.1 知识仅自动生成（后被 D-013 修订）

- **日期**：2026-08-24
- **决策**：首版不允许人工编辑知识（generated-only）。
- **背景**：先验证自动萃取的可信度，不引入人工覆盖/锁定/审批。
- **来源**：转移归档消息 016–018（用户选 A）。
- **状态**：superseded（2026-08-25 被 D-013 修订为受保护的人工 overlay 层）。

## D-008 · Claim 级证据验证

- **日期**：2026-08-24
- **决策**：验证发生在 Claim 粒度而非整卡：每个事实字段引用 Claim，每条 Claim 绑定 Evidence（路径/符号/行范围/内容哈希/脱敏摘录哈希）；结构验证与语义验证分离，语义验证用独立请求并绑定摘要（digest）。
- **背景**："不能只给整张卡挂几个源码链接"；代码变化时才能精准判断哪条 Claim 失效。
- **来源**：规格 §6/§7/§9.6；转移归档第二编 §12.18。
- **状态**：effective。

## D-009 · Agent 默认读取 fail closed

- **日期**：2026-08-24
- **决策**：默认读取前校验仓库快照（commit + 干净度 + 工作树哈希）与三个代际戳（active/agent_views/FTS）；任一不匹配返回 `knowledge_update_required`，不提供旧知识；stale/conflicted 永不进入默认上下文（`--include-stale` 仅为醒目标记的诊断模式）。
- **背景**：借鉴 Copilot Memory"使用前重新验证"；宁可拒绝服务也不给过期知识。
- **来源**：规格 §5.8/§10.3/§11；恢复计划 Gate 7（精确 dirty 快照门禁）。
- **状态**：effective。

## D-010 · 确定性 retirement：模型不得授权删除

- **日期**：2026-08-24（五轮规格审查第 2–3 轮强化）
- **决策**：对象退役只由四重确定性检查授权（原 Evidence 全部消失、全仓精确搜索无候选、无幸存入边、全部查询完整）；Planner 遗漏、模型 `insufficient_evidence` 或任何语义输出都不足以删除。
- **背景**：最初草案允许模型参与退役判断，审查判定这是不可接受的授权边界。
- **来源**：规格 §12.1；恢复计划 Gate 5（完整退役证明 DTO）。
- **状态**：effective。

## D-011 · 可恢复发布事务：manifest 最后替换

- **日期**：2026-08-24（M1 起实现，恢复计划 Gate 2 扩展为多对象）
- **决策**：canonical/Card/Wiki/manifest 的替换纳入单个 journal 事务：预编译全部字节 → 暂存并 fsync → journal 记录目的地与备份 → manifest 最后替换作为唯一提交标记 → 启动恢复用 journal 回滚未提交代；故障注入验证 N+1 失败时 generation N 字节不变。
- **来源**：规格 §5.6/§9.7；M1 的 38 点故障矩阵、Gate 2 批量事务。
- **状态**：effective。

## D-012 · Markdown Wiki + 单文件 HTML，不做 Web 服务

- **日期**：2026-08-24
- **决策**：人类视图 = Git 友好的 Markdown + 一个自包含交互 HTML（导航/搜索/Mermaid/折叠证据）；`knowledge serve` 仅为回环只读单文档服务。
- **被否方案**：复用/扩展上游 Web UI（需把 IR 接入其前后端）。
- **来源**：转移归档消息 030–031（用户选 B）。
- **状态**：effective。

## D-013 · 人工知识层进入 V0.1（方向调整）

- **日期**：2026-08-25
- **决策**：新增受保护的人工 overlay：`supplement`（补充）/`override`（覆盖）作用于编译与检索边界，不改 canonical 对象；机器证据变更命中 override 时产生 `conflicted` 目标结果并保留前一代；退役对象的人工 overlay 字节级归档。提供 `knowledge edit` CLI。
- **背景**：D-007 的 generated-only 使 V0.1 无法容纳代码外的业务规则与架构意图；用户决策将人工编辑保护提前入 V0.1（多语言仍维持单构建单语言）。
- **来源**：完成归档 §3.2（提交 `5e1f677`/`c865dc9`）；规格 §5.10/§6.5；恢复计划 Gate 6。
- **状态**：effective（取代 D-007 的"完全不可编辑"部分）。

## D-014 · 知识检索用 FTS5，不用向量库

- **日期**：2026-08-24
- **决策**：自建知识检索 = SQLite FTS5 + 类型感知排序 + 显式关系一跳扩展；不建向量库（语义源码检索仍由证据引擎提供）。
- **背景**：保持简单、可解释、确定性。
- **来源**：规格 §5.8/§10.3。
- **状态**：effective。

## D-015 · 退出码语义 0/1/2

- **日期**：2026-08-24
- **决策**：构建/更新命令退出码：`0` complete、`1` failed（无可用结果）、`2` partial（存在未发布/stale 对象）。
- **来源**：规格 §13。
- **状态**：effective。

## D-016 · 证据有界预算 + 凭据脱敏

- **日期**：2026-08-24
- **决策**：每个目标的 Evidence Pack 受 item/字符/token 三重预算硬约束（超限在语义消费前拒绝）；原文与模型可见摘录分离哈希，摘录经凭据模式检测与脱敏。
- **背景**：禁止把整个 GraphRAG 上下文灌给模型；密钥永不进入提示词/报告/仓库。
- **来源**：规格 §7/§14。
- **状态**：effective。

## D-017 · MCP 用无依赖 stdio JSON-RPC（已记录偏差 #1）

- **日期**：2026-08-26（Gate 8 实现时定案）
- **决策**：七个只读 MCP 工具基于零运行时依赖的自研 stdio JSON-RPC 分帧（协议兼容 `2024-11-05`），不引入 MCP Python SDK。
- **背景**：生产安装倾向零依赖；工具语义/只读保证/诊断标志完全按规格 §11 执行，日后换 SDK 是纯传输层替换。
- **来源**：规格 §11.1 deviation 1；恢复计划 Gate 8。
- **状态**：effective。

## D-018 · FTS 发布时序偏差（已记录偏差 #2）

- **日期**：2026-08-26
- **决策**：FTS 索引不在发布事务内换库，而在 canonical 提交后由 `knowledge compile`/编排器视图步骤立即重建；每次默认读取校验"索引戳 == manifest 双戳 == 精确仓库身份"，缺失或过期即 fail closed。
- **背景**：比规格原文（事务内换库）严格更简单且安全性质不损失。
- **来源**：规格 §11.1 deviation 2。
- **状态**：effective。

## D-019 · 视图失败 = partial，不回滚 IR（已记录偏差 #3）

- **日期**：2026-08-26
- **决策**：canonical 提交后 Wiki/HTML/索引编译失败不回滚有效 IR：运行返回 `partial`，`wiki_generation` 落后于 `active_generation`，`knowledge compile` 幂等重试，`knowledge open` 对落后 Wiki 先全局告警。
- **来源**：规格 §11.1 deviation 3。
- **状态**：effective。

## D-020 · M8 预注册判定标准

- **日期**：2026-09-02
- **决策**：H1/H2 判据、任务集规则、臂位定义在实验前冻结预注册（防事后挑选）；任务污染、知识过期、小样本、harness 偏差各有对策；结论无论正负都如实报告。
- **来源**：M8 设计草案 §4/§6。
- **状态**：effective（执行待环境与用户冻结）。

## D-021 · 单构建单语言（zh|en）

- **日期**：2026-08-24
- **决策**：一次构建只输出一种语言；不同语言各自构建，不做同步翻译。
- **来源**：规格 §2.2；完成归档 §3.2（设计修订时重申）。
- **状态**：effective。

## D-022 · 一键生产验证闭环 verify.sh

- **日期**：2026-09-02
- **决策**：`bash scripts/verify.sh` 成为每次更新的固定入口：双遍离线套件（计数级确定性检查）+ src-only compileall + diff-check + pip-audit + live 冒烟自动探测（条件齐备自动执行，否则报告缺失项；`REQUIRE_LIVE=1` 强制失败闭合）。
- **背景**：把"更新后要跑什么验证"从纪律问题变成一条命令。
- **来源**：提交 `7fe5a90`；README 验证闭环节。
- **状态**：effective。

## D-023 · 文档库三层治理（materials / knowledge / 工作流）

- **日期**：2026-09-12
- **决策**：文档库按产品自身方法论分三层治理——素材层（原始不可变）、知识层（提炼后带来源指针的静态权威知识，设计报告的事实基础）、工作流层（规格/计划/手册/实测）；统一状态体系（active/draft/historical/superseded）与总索引；单一权威副本，被取代文档保留加注不删除。
- **背景**：多次方向调整后计划/归档/知识混杂，"为什么"散落在 7400 行会话归档中不可复用；项目需要不依赖外部动态上下文的静态知识库。
- **来源**：本次文档重组（2026-09-12）。
- **状态**：effective。

## D-024 · 展示层三段交付（单文件 / 静态站点 / 本地只读服务）

- **日期**：2026-09-16
- **决策**：人类视图由同一份页面渲染（`_render_page_bodies` 单源双渲染）编译出三段交付物：`repo-wiki.html` 单文件归档件（零依赖可分享）、`exports/site/` 多页静态站点（相对路径可托管、数据编译时内嵌）、`knowledge serve` 回环只读服务（含 `/api/preview` 端点）。Ask 一律 evidence-only 检索式（serve 环境升级 server-backed，静态托管回落内嵌 Claim 索引），不做生成式回答；全部产物确定性（同输入逐字节一致）且无构建链、无前端框架依赖。
- **背景**：三轮竞品调研（DeepWiki/dbt docs/coverage.py/OpenAPI/Backstage 等）+ 用户四项决策（2026-09-16）。框架引入被否决的依据是产品约束（确定性/单文件交付/阅读密集组件面），而非沉没成本；若未来做交互密集的管理 UI，应单独立前端项目。
- **来源**：设计文档 v3（plans/historical/2026-09-16-presentation-layer-design.md）；提交 `3bdc657`…`ed8ece7`。
- **状态**：effective。

## D-025 · M8 基准四项决策冻结（授权自主定稿）

- **日期**：2026-09-16
- **决策**：按用户授权（"缺决策信息参考竞对与同行惯例自主决策"）冻结 M8 四项：任务池 click→flask→requests（15 任务 × 3 仓库，按 §2 标准逐条核对）；harness 为 Claude Code headless（后端接口可替换）；token 低档 60k/次 ≈5.4M 总量；v0 两臂（MCP 臂仅当 Treatment-A 出正效应后追加）。预注册判据不因决策方式而放松。
- **背景**：用户不提供输入时的实验效率路径；修改任一项须走设计文档 Revision History。
- **来源**：M8 设计文档 v1.0 §8（`5ac851e`）；harness 实现 `f41adc7`。
- **状态**：effective（实验执行待 API key 与上游修复）。

## Revision History

- 2026-09-16 追加 D-024/D-025（展示层三段交付、M8 冻结）。
- 2026-09-12 首次建卷：从规格、转移归档、完成归档、恢复计划、M8 设计中全量提炼 23 条。
