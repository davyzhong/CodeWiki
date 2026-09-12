---
status: maintained
last-reviewed: 2026-09-12
sources:
  - superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md §5–§6、§8–§12
  - src/knowledge_compiler/contracts/（合同源码为权威定义，本文是其语义导读）
---

# 核心概念词典（Domain Model）

按"仓库 → 证据 → 知识 → 生命周期 → 消费"的管线顺序定义核心概念。合同的机器级定义以 `src/knowledge_compiler/contracts/` 与规格为准，本文回答"每个概念是什么、为什么存在"。

## 仓库与快照

- **RepositorySnapshot**：一次分析看到的不可变仓库身份：`repository_id + snapshot_id + branch + commit + dirty + working_tree_hash + eligible_files`。`snapshot_id` 由这些字段确定性派生（SHA-256），在任何合同边界必须吻合——这是全系统防"知识与仓库错位"的锚点。
- **eligible files**：合格文件清单。永久排除 `.knowledge/`、`.codewiki/`、`.git/`、ignored、依赖目录、二进制、超限文件——生成物绝不污染自己的源快照。tracked 的 `baseline/eligible-files.json` 使增量比较在缓存删除、shallow clone、换机器后依然可用。
- **working_tree_hash**：仅对合格文件计算的过滤后工作树哈希。允许分析脏工作树，但脏状态下的知识被精确绑定到这棵脏树（快照门禁逐字节比对），不会伪装成某个 commit 的可共享知识。
- **ChangeSet**：两次合格文件清单的对比结果（added/modified/deleted/renamed，rename 需身份证明）。在任何证据引擎同步**之前**计算——外部索引的变更不能擦除比较基线。

## 证据层

- **EvidenceItem**：一条可验证的源码证据：相对路径 + 符号 + 闭区间行范围 + commit + `content_hash`（原始源码字节）+ `excerpt_hash`（脱敏后模型可见文本）。Evidence ID 是内容寻址的确定性派生（`sha256(repository_id, snapshot_id, path, symbol, range, content_hash)`）——同快照同源码永远同 ID，与提供方内部 ID 无关。
- **EvidencePack**：发给语义工作者的有界证据包：目标 + 预算 + 证据列表 + 图事实（graph facts）。三重预算（item/字符/token）硬约束，超限在进入语义阶段前拒绝。证据不足时工作者必须返回 `insufficient_evidence`，禁止按命名/注释/惯例猜测。
- **原字节与脱敏摘录分离**：结构验证本地比对原始字节哈希；语义验证只看脱敏摘录。验证摘要（digest）绑定"精确 Claim 文本 + 证据 ID + 摘录哈希"——脱敏输出变化即失效结果。

## 知识层

- **Canonical Knowledge IR**：唯一的事实知识存储（`objects/**/*.yaml`，tracked）。Wiki/Cards/Context/FTS 全部是它的编译视图，编译器不创造新事实。
- **Claim**：最小验证单元——一条陈述 + 证据引用 + 置信度（分数 + 依据）。所有事实字段（摘要、职责、接口、依赖、关系、步骤…）都必须引用 Claim；字段无 Claim 引用 = 无效草稿。
- **Draft 与 canonical 分离**：`DraftKnowledge`（无 Validity，不可发布）与 canonical 对象（要求全部必需 Claim 的验证为 `supported`）是不同类型；未验证草稿在类型层面就无法被序列化为 canonical。
- **稳定语义 ID**：`<type>.<domain>.<name>`（如 `module.shop.checkout`、`flow.order.create`），不用不透明数据库 ID——目录是阅读界面，ID 是机器身份。
- **五类型**：Architecture / Module / Flow / Rule / TechStack，各自有 Claim 支撑的类型化 payload（见规格 §6.3）。
- **Relation**：类型化谓词的对象间关系；目标缺失时显式 unresolved，不伪造占位对象。

## 状态与生命周期

- **Validity（canonical 对象仅有两态）**：`verified → stale`。没有 human-verified/human-locked 状态。
- **目标终态（run 记录，非 canonical 状态）**：`verified / invalid / conflicted / insufficient_evidence / retired / skipped`。invalid、conflicted、insufficient 的结果**永远不能**成为 canonical 对象，因此天然进不了任何 Agent 视图。
- **Generation 三戳**：`active_generation`（canonical 提交代）、`agent_views_generation`（verified-only Agent 面）、`wiki_generation`（人类视图，允许落后——落后时 `knowledge open` 全局告警）。manifest 是唯一提交标记，最后替换。
- **Human overlay**：对象级人工层（supplement/override），作用于编译/检索边界，不改 canonical；机器证据变更命中 override → `conflicted` 目标并保留前一代；对象退役时 overlay 字节级归档。
- **pending_targets**：manifest 中的未决必需目标——部分运行后即使无新 diff 也会重试。
- **Retirement proof**：四重确定性证明（来源消失 / 全仓精确搜索无候选 / 无幸存入边 / 查询完整）全部通过才允许删除；任何不完整 → 保持 stale 等待。

## 执行与编排

- **RunOrchestrator**：独占调度、租约、重试、修复计数、发布资格与最终 run 状态（complete/partial/failed）的持久化状态机：`queued → evidence_ready → extraction_leased → draft_submitted → structural_validated → semantic_pending → verification_leased → verified`，外加 `repair_pending` 与五个终态。
- **Lease / idempotency key**：Agent 领取工作凭租约（run/目标/操作/尝试/过期/幂等键）；同幂等键重复提交返回已记录结果而不重复计费/发布；过期租约回到原队列且不丢失已接受结果。
- **双执行模式**：内置 LiteLLM worker（进程内消费同一队列）与 Codex Skill（`/knowledge-build`、`/knowledge-update` 走 8 个隐藏队列 CLI 命令）——同一合同、同一编排器。
- **修复上限**：每目标初始提交后最多两次修复尝试；仍失败则记录终态、不发布，其他目标不受影响。

## 验证

- **结构验证（确定性）**：Pydantic 合同、ID/类型、证据存在性、路径/行范围/哈希、Claim 引用闭包、必需字段。字节级源码完整性（描述符相对 openat + O_NOFOLLOW 防 symlink 逃逸与 TOCTOU；保留 CRLF/尾行的精确字节哈希）。
- **语义验证（独立请求）**：只看"Claim + 其引用的脱敏摘录"，判定 `supported/partial/unsupported/conflicted`；与抽取是分离的请求/提示词/幂等域，即使同一模型也是两次独立调用。

## 消费层

- **Knowledge Cards**：verified-only 的高密度 Agent 单元；对象转 stale 时 Card 与 FTS 行在失效事务中移除，canonical YAML 留作诊断。
- **Task Context**：FTS5 检索 + 类型感知排序（Rule/Flow 优先）+ 关系一跳扩展（带归因）+ token 预算编译；源码正文默认不内嵌，按需指针。
- **检索门禁**：每次默认读取校验"当前过滤快照 == manifest 观测快照 ∧ 三代际戳一致"；不一致 → `knowledge_update_required`。这是 [decision-log](decision-log.md) D-009 的运行时体现。
- **七个只读 MCP 工具**：`knowledge_repo_overview / search / get_object / get_related / get_evidence / context_for_task / status`，stdio JSON-RPC（D-017），永不构建/变更/执行仓库代码。

## Revision History

- 2026-09-12 首次建卷（语义导读，合同以源码与规格为准）。
