# 2026-08-25 V0.1 执行完成归档与交叉验证说明

> **本文档的目的**：完整记录从 M1 到 M7 CLI surface 的全部已完成工作，供另一位 Agent 进行交叉验证和检验。每一项声明都附有可执行的验证命令或精确的文件/提交引用。**过度声明会被审查发现**——本文档如实区分"已完成并通过审查"与"已实现但有记录的限制"。

---

## 1. 项目概述

**CodeWiki**（设计名 Knowledge Compiler）是面向 Coding Agent 的本地仓库知识编译器。将一个本地 Git 仓库编译为经过 Claim/Evidence 验证的结构化知识（5 种类型），以确定性方式输出 Repo Wiki（人类）、Knowledge Cards（Agent）、Task Context（预算化）。

**核心设计参考**：Qoder 的 Repo Wiki + Knowledge Cards（阿里），采用其双视图从同一 Canonical IR 编译的核心理念，并加强了 Claim/Evidence 可追溯性和 fail-closed 安全边界。

**设计修订（2026-08-25 用户决策）**：人工编辑保护进入 V0.1（新 M6 里程碑），多语言维持单构建单语言。

---

## 2. 权威文档体系

| 文档 | 位置 | 状态 |
|---|---|---|
| V0.1 设计规格 | `docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md` | 已修订（含 §5.10/§6.5 human overlay），三轮一致性审查 APPROVED |
| 执行路线图 | `docs/superpowers/plans/2026-08-25-v0-1-execution-roadmap.md` | M0-M8 编号已更新（M6=人工知识层，M7=视图，M8=基准） |
| 完整 handoff To-do | `docs/superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md` | 权威执行清单，每项完成状态已勾选并附提交号 |
| M1 exact plan | `docs/superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md` | 全部完成 |
| M2 exact plan | `docs/superpowers/plans/2026-08-25-codewiki-module-vertical-slice.md` | 审查 APPROVED，全部完成 |
| M3 exact plan | `docs/superpowers/plans/2026-08-25-five-knowledge-types.md` | 审查 APPROVED，门禁 PASS |
| M4 exact plan | `docs/superpowers/plans/2026-08-25-run-orchestrator.md` | 审查 APPROVED，门禁 PASS |
| M5 exact plan | `docs/superpowers/plans/2026-08-25-incremental-lifecycle.md` | 审查 APPROVED，门禁 APPROVED（含记录的 follow-up） |
| /knowledge-build Skill | `docs/project-materials/03-skills/knowledge-build/SKILL.md` + `src/knowledge_compiler/skills/knowledge_build/SKILL.md` | 字节一致（协议测试钉住） |

---

## 3. 里程碑完成状态

### 3.1 M1 — Fake Provider + Module 垂直切片 ✅ 完成

**范围**：一个 fixture-backed Module 对象从有界证据→抽取→独立验证→确定性编译→可恢复发布。

**关键交付**：
- 项目自有 RepositorySnapshot/PlanTarget/EvidenceBudget/EvidenceItem/EvidencePack 合同（`contracts/repository.py`, `contracts/evidence.py`）
- DraftModuleKnowledge 与 canonical ModuleKnowledge 分离（`contracts/knowledge.py`）
- FakeEvidenceProvider（`providers/fake.py`）：inspect/ensure_index/build_pack/get_evidence
- 字节级源完整性验证：descriptor-relative openat/O_NOFOLLOW、CRLF 保持、content_hash/excerpt_hash 独立计算（`validation/module.py`）
- 独立语义验证：摘要绑定的 VerificationRequest/Result 合同（`contracts/semantic.py`）
- 确定性 YAML/Card/Wiki 编译 + 5 个金色文件（`compiler/yaml.py`, `compiler/markdown.py`, `tests/golden/`）
- 可恢复发布事务：38 点故障注入矩阵、journal 恢复、manifest-last 提交协议（`storage/generation.py`）
- 端到端垂直切片 harness + CLI（`vertical_slice.py`）
- **测试**：329 全绿

**审查历史**：
| 审查 | 结论 | 修复 |
|---|---|---|
| M1.6 规格 | APPROVED + 2 Minor | 补测试 + cleanup 类型边界修复（`e873786`） |
| M1.6 质量（两轮） | CHANGES→修复→APPROVED | symlinked transactions root、堆叠事务、guard OSError 泄漏（`b2bfcdb`） |
| M1.7 规格 | APPROVED + 1 Minor | CLI provider-level 无效选项测试（`b2bfcdb`） |
| M1.7 质量（四轮） | CHANGES→修复→APPROVED | RecursionError 泄漏、提交探测假阳性→字节级验证、OSError 守卫（`2fbb3c3`/`c9e4d0a`/`9cc0f38`） |
| M1 整片终审 | **PASS** | 全部 7 项出口门禁逐项确认 |

**验证**：
```bash
git show 9c50176  # 门禁 PASS 记录
uv run --extra dev pytest tests/contracts/ tests/providers/ tests/validation/ tests/compiler/ tests/storage/ tests/integration/test_module_vertical_slice.py -q
# 预期：全部通过（M1 范围内的测试）
```

---

### 3.2 设计修订 ✅ 完成

**用户决策**：人工编辑保护进入 V0.1；多语言维持。

**交付**：
- 设计规格新增 §5.10（Human knowledge layer 组件）和 §6.5（overlay 合同：supplement/override 语义、conflicted 目标结果、退役归档、orphaned 渲染）
- 路线图和 handoff 插入新 M6，原 M6→M7、原 M7→M8
- §8 存储布局增加 `.knowledge/human/` 目录树（含 archive/）
- §15 错误表区分 malformed overlay 与 override 冲突
- Qoder 映射表更新

**审查**：三轮一致性审查，13+2+2 项发现全部修复，终审 APPROVED。

**验证**：
```bash
git show 5e1f677 --stat  # 设计修订提交
git show c865dc9 --stat  # 一致性修复
git show 1a01fb7 --stat  # 基线同步
grep -n "Section 6.5" docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md | head -5
```

---

### 3.3 M2 — 真实 CodeWiki 适配器 + LiteLLM ✅ 完成

**范围**：一个真实本地 Git 仓库通过 CodeWiki 公开接口和内置 LiteLLM worker 产生经验证的 Module 合同。

**关键交付**：
- `LocalGitRepositoryProvider`（`repository/local_git.py`）：eligible-file 清单（path/blob/hash/size/language）、归一化远程 URL 或 content-derived `local:<initial-commit>` 身份、filtered dirty 标记、gitlink/符号链接排除、git 超时
- `CodeWikiEvidenceProvider`（`providers/codewiki.py` + `codewiki_cli.py`）：版本门控（`>=0.6,<0.7`）、repos add + analyze only（update/graph_affected 保留为 M5 面）、凭据脱敏（build_pack 中 redact_credentials）、归一化夹具 runner
- `KnowledgeConfig` 合同（`config.py`）：完整字段集、secret 字段拒绝、scope limits
- `knowledge init --language zh|en`（`cli.py`）：幂等、不覆盖用户配置、.gitignore 管理
- 有序 preflight（`preflight.py`）：Git→commit→eligible→scope→config→CodeWiki 版本→模型 profile，全部在模型调用前
- 确定性一模块 Planner（`contracts/planning.py` + `planning/module.py`）：priority/requiredness、从 survey 派生、无 Claims
- `LiteLLMWorker`（`workers/litellm_worker.py`）：可注入 transport、独立 extract/verify 提示词、两次修复后类型化失败、凭据不出现在提示词中
- 集成 harness（`real_slice.py`）+ `knowledge-realslice` CLI
- mcp 依赖移至 dev extras
- **测试**：402 全绿

**审查**：
| 审查 | 结论 | 修复 |
|---|---|---|
| M2 计划 | CHANGES→修复→APPROVED | 凭据脱敏归属、版本探测机制、ensure_index 限定（`955eb44`） |
| M2.2 合并审查 | CHANGES→修复→APPROVED | gitlink dirty、rev-parse 超时、二进制过滤（`71528e2`） |
| M2.3 合并审查 | APPROVED + 跟进 | get_evidence 缓存、版本探测绑定 codewiki 环境（`44e6add`） |
| M2.4-2.7 合并审查 | CHANGES→修复→APPROVED | litellm 依赖、preflight 缺失停机点、死代码（`2b821bc`） |
| M2 门禁 | **PASS** | 全量×2 + 边界扫描干净 |

**验证**：
```bash
git show 63ed7ba  # 门禁 PASS 记录
uv run --extra dev pytest tests/repository/ tests/providers/ tests/planning/ tests/workers/ tests/test_config.py tests/cli/test_init.py tests/cli/test_realslice.py tests/integration/test_real_provider_slice.py -q
rg -n "litellm" pyproject.toml  # 确认为生产依赖
rg -n '"mcp' pyproject.toml     # 确认移至 dev extras
```

---

### 3.4 M3 — 五种知识类型 ✅ 完成

**范围**：Architecture、Module、Flow、Rule、TechStack 共享稳定的 Claim/Evidence 语义，跨类型引用安全，确定性编译。

**关键交付**：
- 共享基座（`contracts/base.py`）：ContractModel、Confidence、Provenance、Scope、ClaimBacked、ClaimBackedText、Relation、Validity 提取
- 类型化语义信封：PlanTarget 五类型联合 + DraftKnowledge 判别联合
- ArchitectureKnowledge：Claim-backed 组件/边界/关系 + Mermaid 图 + 金色 YAML
- FlowKnowledge：Claim-backed trigger/steps/failure_paths + 时序图 + 金色 YAML
- RuleKnowledge：Claim-backed statement/severity/applicability/constraints/exceptions + Card + 金色 YAML
- TechStackKnowledge：Claim-backed entries（显式 unknown 版本）+ Card + 金色 YAML
- 跨类型关系（`contracts/relations.py`）：类型化谓词表、注册表、显式未解析
- 类型化验证应用（`validation/typed.py`）：目标相关性检查（`f15ffa8` 修复）
- 类型化发布（`storage/generation.py` 扩展）：per-type 目录、journal 中的 object_type
- 五类型集成测试（`tests/integration/test_typed_publication.py`）
- **测试**：466 全绿

**审查**：
| 审查 | 结论 | 修复 |
|---|---|---|
| M3 计划 | CHANGES→修复→APPROVED | 类型化信封无步骤、EvidenceRef/Conflict、CodeWiki 夹具路径（`b53f327`） |
| M3 里程碑 | CHANGES→修复→APPROVED | 目标相关性缺失、Card category 未转义、序列图非法行、severity 分类（`f15ffa8`） |
| M3 门禁 | **PASS** | 每类型金色文件 + 排列不变性 + 无类型绕过 |

**记录的限制**：每类型 CodeWiki 夹具提取 harness 未构建（记录为 M4.8b 延后项，在 handoff M3.8 节有明确说明）。

**验证**：
```bash
git show a443a4d  # 门禁 PASS 记录
ls tests/golden/  # 应有 6 个金色文件
uv run --extra dev pytest tests/contracts/ tests/relations/ tests/validation/test_typed_validation.py tests/integration/test_typed_publication.py -q
```

---

### 3.5 M4 — RunOrchestrator + 双执行模式 ✅ 完成

**范围**：内置 LiteLLM 和 Agent 队列 CLI 消费同一持久化队列，可恢复租约、有界重试、幂等、发布所有权。

**关键交付**：
- 精确状态机（`orchestrator/contracts.py`）：queued→evidence_ready→extraction_leased→draft_submitted→structural_validated→semantic_pending→verification_leased→verified + repair_pending + 5 个终态
- 持久化存储（`orchestrator/store.py`）：原子写入、启动校验、单一活跃运行
- 队列操作（`orchestrator/queue.py`）：独占租约、操作域分离、摘要绑定幂等重放、到期回滚
- 调度 runner（`orchestrator/runner.py`）：完整→partial→failed 状态计算、字节级先前生成保持、重入不重复
- 内置执行器（`workers/queue_executor.py`）：进程内 transport
- 8 个隐藏 Agent 队列 CLI（`cli_agent_queue.py`）：prepare/next/evidence/submit-extraction/verify-next/submit-verification/finalize + verify-next 仅新鲜上下文
- /knowledge-build Skill（`skills/knowledge_build/`）：协议测试钉住字节一致
- `knowledge build`（`cli.py`）：orchestrator 驱动、exit 0/1/2、结构化报告
- `knowledge validate`（`cli.py`）：manifest 一致性检查
- **测试**：509 全绿

**审查**：
| 审查 | 结论 | 修复 |
|---|---|---|
| M4 计划 | CHANGES→修复→APPROVED | 新鲜验证上下文、单运行不变量、Task 8 测试优先（`6aed8bc`） |
| M4 里程碑（三轮） | CHANGES→CHANGES→APPROVED | agent 协议死锁→修复；lease 忽略→修复；build 绿色路径不可达→修复并测试（`4b8590c`/`8258d98`） |
| M4 门禁 | **PASS** | 状态机+租约+幂等+发布+双模式 |

**记录的限制**：
- build 的 `exit 2`（partial）无 CLI 级测试（fixture 模式的单必需目标只能产生 complete 或 failed）
- 固定 run_id 意味着崩溃中的构建会阻塞重建直到清除（与单一活跃运行设计一致）
- live CodeWiki + LiteLLM worker 的环境驱动接线为 M4.8b 延后项

**验证**：
```bash
git show c8d5970  # 门禁 PASS 记录
uv run --extra dev pytest tests/orchestrator/ tests/cli/test_agent_queue.py tests/cli/test_knowledge_build_skill.py tests/cli/test_build.py tests/cli/test_build_green_path.py -q
# 手动验证 build 绿色路径：
cd $(mktemp -d) && git init -q -b main . && git config user.email t@e.com && git config user.name T
cp -r /path/to/CodeWiki/tests/fixtures/probe_repo/* .
git add -A && git commit -qm fixture
cd /path/to/CodeWiki && uv run --extra dev python -m knowledge_compiler.cli build --repository-root $(pwd)/$(basename $OLDPWD)
```

---

### 3.6 M5 — 增量生命周期 ✅ 完成（库级）

**范围**：显式更新检测本地仓库变更、原子移除过期知识、重试待定工作、仅通过确定性证明退役对象。

**关键交付**：
- 持久化 eligible-file 基线（`repository/inventory.py`）：path/blob/hash/size/language，永不存内容
- ChangeSet 计算（`repository/changes.py`）：added/modified/deleted/renamed 不交类别，rename 需身份证明
- 失效库（`incremental/invalidation.py`）：反向证据索引、provider 提示合并不替代、stale 标记
- 待定目标存储（`incremental/pending.py`）：跨运行持久化、无 diff 重试
- 确定性退役（`incremental/retirement.py`）：四项证明全部满足才授权
- `knowledge update` CLI
- **测试**：538 全绿

**审查**：APPROVED，附带 5 项已记录 follow-up。

**已记录的限制（M5.8 follow-up，handoff 有精确记录）**：
- /knowledge-update Skill 扩展在 commit 833c5b6 消息中被声称但**未实际交付**（审查发现，handoff 已更正记录）
- corrupt baseline 静默 no-op 而非触发全量刷新
- rename 证明仅用 content hash（blob_id 可用但未参与匹配）
- update CLI 总是 exit 0，exit 1/2 不可达
- 失效/待定/退役为纯库层，未接线为完整事务（Card 原子移除、manifest 绑定、retirement_pending 创建）

**验证**：
```bash
git show fdc54d8  # 门禁记录
uv run --extra dev pytest tests/repository/test_changes.py tests/incremental/ tests/cli/test_update.py -q
```

---

### 3.7 M6 — 人工知识层 ✅ 完成（合同+CLI）

**范围**（用户设计修订新增）：人工编辑保护。

**关键交付**：
- `HumanOverlay` 合同（`contracts/human.py`）：schema_version/object_id/timezone-explicit updated_at/sections(supplement|override)/notes
- 逐类型字段校验：module/architecture/flow/rule/tech-stack 各自允许的字段集合
- note 归属校验：note id 必须属于包含对象
- `knowledge edit <object-id>` CLI：创建/打开 overlay、--print-path、保存时校验
- **测试**：551 全绿

**已记录的限制**：
- M6.4（regeneration preservation）和 M6.5（retirement archiving）需要 M5.8 的 orchestrator 失效接线才能实现完整语义
- 冲突语义（override + changed evidence → conflicted 目标结果）为合同层设计，未接入 runner

**验证**：
```bash
uv run --extra dev pytest tests/contracts/test_human_overlays.py tests/cli/test_edit.py -q
uv run knowledge edit module.test.thing --print-path  # 打印路径
```

---

### 3.8 M7 CLI Surface ✅ 完成

**范围**：完整的主要 CLI 命令面。

**交付**：`knowledge status`、`compile`、`context`、`open`、`serve` 全部注册并可通过 `--help` 查看。

**未实现（M7.2-M7.8 为最大剩余项）**：
- 完整 Markdown Wiki 页面（index.md、architecture.md 等）
- 独立交互式 HTML Wiki
- SQLite FTS5 索引 + ContextRetriever
- 七个只读 MCP 工具
- 完整安全测试套件

**验证**：
```bash
uv run knowledge --help          # 查看完整命令面
uv run knowledge status --help   # status 子命令
```

---

## 4. 重大事件记录

### 4.1 工作区搬移事故

**时间**：2026-08-25 约 12:00

**事件**：另一会话中的"整理目录"Agent 将整个项目从 `/Users/qiming/workspace/CodeWiki` 移动到 `/Users/qiming/workspace/EnterpriseIntelligence/codewiki`。M1 审查期间的一个提交（原始 M1.6 修复）在移动过程中丢失。

**恢复**：
1. GitHub 远程有完整基线（`5b338ac`）
2. 会话转录（27MB JSONL）中提取了所有已读文件的精确字节
3. 在 EnterpriseIntelligence 目录中找到完整项目（含 .git 和 M1.7 WIP）
4. 项目完整归位，丢失的提交从会话转录逐字节复原为 `e873786`

**教训**：此后建立了"里程碑门禁通过后立即推送"的节奏。

---

## 5. 审查统计

| 里程碑 | 审查轮数 | 发现 Critical/Important | 修复提交 |
|---|---|---|---|
| M1.6 规格审查 | 1 | 0（2 Minor） | `e873786` |
| M1.6 质量审查 | 2 | 2 Critical + 5 Minor | `b2bfcdb` |
| M1.7 规格审查 | 1 | 0（1 Minor） | `b2bfcdb` |
| M1.7 质量审查 | 4 | 2 Important + 5 Minor | `2fbb3c3`/`c9e4d0a`/`9cc0f38` |
| M1 整片终审 | 1 | 0 | PASS |
| 设计修订一致性 | 3 | 1 Critical + 6 Important | `c865dc9`/`1a01fb7` |
| M2 计划审查 | 2 | 1 Critical + 8 | `955eb44` |
| M2.2-2.7 合并审查 | 4 | 1 Medium + 多项 | `71528e2`/`44e6add`/`2b821bc` |
| M3 计划审查 | 2 | 1 Critical + 2 Major | `b53f327` |
| M3 里程碑审查 | 2 | 2 Medium + 3 Low | `f15ffa8` |
| M4 计划审查 | 2 | 3 | `6aed8bc` |
| M4 里程碑审查 | 3 | 1 HIGH + 2 Medium | `4b8590c`/`8258d98` |
| M5 计划审查 | 2 | 5 | `c54f78a` |
| M5 里程碑审查 | 1 | 1 HIGH + 2 Medium | APPROVED with follow-ups |
| **合计** | **~31 轮** | **~8 Critical/HIGH** | 全部修复 |

---

## 6. 完整提交清单（M1 开始，`5b338ac..7892063`）

```text
# M1 垂直切片（15 个实现提交 + 审查修复）
8a88125 feat: define normalized evidence contracts
34a3281 fix: preserve evidence token boundaries
142fd49 fix: harden evidence contract invariants
368af4f feat: define claim-backed module knowledge
5624e8e fix: harden module knowledge invariants
fdc5318 test: add fake evidence provider contract
915319f fix: honor fake provider budget bounds
f53fa75 feat: validate module evidence and semantic support
ff090e2 fix: require semantic identity and repository binding
6ac4d64 fix: harden semantic validation boundaries
b0efbb5 feat: compile deterministic module outputs
82c5f6b fix: golden-test canonical module yaml
9be6ef6 fix: harden compiler trust boundaries
d376859 fix: neutralize markdown block openers
5f26aea feat: publish recoverable module generation
458d59a docs: add complete v0.1 handoff todo
4606722 docs: archive m1 implementation handoff
e873786 fix: wrap publication cleanup failures as typed errors    # 事故复原
0cadcb2 fix: reject generation id reuse with differing content
397fda5 feat: prove fake provider module vertical slice
2fbb3c3 fix: harden vertical slice failure boundary
c9e4d0a fix: verify committed trees byte-exactly
9cc0f38 fix: guard committed-tree probe reads against OSError
9c50176 docs: record M1 exit gate pass

# 设计修订
5e1f677 docs: add human knowledge layer to v0.1 scope
c865dc9 docs: reconcile human-layer revision findings
1a01fb7 docs: sync status baselines to 320 tests

# M2 真实适配器（约 20 个提交）
955eb44 docs: approve m2 plan after independent review
454857d feat: resolve local git repository snapshots
3b3290e fix: keep boundary scan clean in exclusion list
3fde815 fix: bound git plumbing calls with a timeout
66b9ab4 docs: record m2.1 approval and m2.2 status
0740d64 docs: track m2.2 independent review debt
1a21ca1 feat: adapt codewiki public interfaces
71528e2 fix: keep gitlinks and index symlinks out of dirty state
3264e01 docs: record m2.2 review approval
44e6add feat: add preflight configuration and init
0652b14 docs: record m2.3 approval and m2.4 status
d6141a3 feat: plan one module from survey facts
27e9d6a feat: add litellm semantic worker
d679a98 docs: record m2.5 and m2.6 status
859e529 feat: prove the real provider module slice
af13e8c fix: keep boundary scan clean in slice test
2b821bc fix: complete m2 preflight stops and declare litellm
63ed7ba docs: record m2 exit gate pass

# M3 五类型（约 25 个提交）
b53f327 docs: approve m3 plan after independent review
b3b8e53 feat: extract shared canonical knowledge base
3ea0a03 feat: generalize semantic envelopes across types
6158acc feat: add architecture knowledge
bb01a87 feat: compile architecture outputs deterministically
f996818 feat: add flow knowledge
e6d0e0c feat: compile flow outputs deterministically
4349267 feat: add rule knowledge
（多个测试修复提交）
5aedab6 feat: add tech-stack knowledge
68a1ab1 fix: reject duplicate technology aliases by name
60e01ba feat: add cross-type relations
2894f8d feat: add typed drafts to the semantic union
abe8840 feat: canonicalize typed drafts from supported verification
3a5cbe8 feat: publish typed objects per type directory
8e7036b feat: prove five-type publication integration
f15ffa8 fix: correlate typed verification with its target
a443a4d docs: record m3 exit gate pass

# M4 RunOrchestrator（约 25 个提交）
6aed8bc docs: approve m4 plan after independent review
d6283de feat: persist orchestrator run state
44b3fb9 feat: lease orchestrator work idempotently
129e604 feat: orchestrate runs end to end
d58c276 feat: run the built-in executor over the queue
0a271d7 feat: add the agent queue cli
90dc32d feat: add the knowledge-build skill
0846fc3 feat: add build and validate commands
4b8590c fix: complete the agent protocol and wire build
8258d98 fix: reach and test the build green path
c8d5970 docs: record m4 exit gate pass

# M5 增量生命周期（约 10 个提交）
c54f78a docs: approve m5 plan after independent review
2cbc119 feat: track eligible-file changes
433a96a feat: invalidate affected knowledge atomically
708d098 feat: retry pending knowledge targets
9f8a758 feat: retire knowledge deterministically
833c5b6 feat: add knowledge update
fdc54d8 docs: record m5 exit gate pass with follow-ups

# M6 人工知识层
004529e feat: define human overlay contracts
7dfb1ee feat: add knowledge edit command
cb4cfd7 docs: record m6 progress with follow-up scope

# M7 CLI surface
f6df5c4 feat: add knowledge status compile context open and serve
7892063 docs: record m7 cli surface completion
```

---

## 7. 测试与代码统计

| 指标 | 数值 |
|---|---|
| 总提交数（M1 起） | 104 |
| 产品代码行数（不含 spikes） | 8,389 |
| 测试代码行数 | 8,310 |
| 测试通过数 | **551** |
| 金色文件数 | 6 |
| 独立审查轮数 | ~31 |
| 边界扫描违规 | 0 |

---

## 8. 交叉验证指令

### 8.1 基线验证

```bash
cd /Users/qiming/workspace/CodeWiki

# 1. 全量测试
uv run --extra dev pytest -q
# 预期：551 passed

# 2. 全量测试（第二次，暴露顺序/时间依赖）
uv run --extra dev pytest -q
# 预期：551 passed

# 3. 边界扫描
rg -n 'from (backend|codewiki)\.|import (backend|codewiki)|sqlite3|aiosqlite|SELECT .*code_(node|edge|chunk)' src tests
# 预期：无匹配（exit code 1）

# 4. diff 检查
git diff --check
# 预期：干净

# 5. Git 状态
git status --short --branch
# 预期：clean, main...origin/main 无 ahead/behind

# 6. 分支策略
git branch --all
# 预期：仅 main
```

### 8.2 分里程碑验证

```bash
# M1 合同+提供方+验证+编译+存储
uv run --extra dev pytest tests/contracts/ tests/providers/ tests/validation/ tests/compiler/ tests/storage/ -q

# M1 垂直切片
uv run --extra dev pytest tests/integration/test_module_vertical_slice.py -q

# M2 仓库+适配器+preflight+init+planner+worker
uv run --extra dev pytest tests/repository/ tests/planning/ tests/workers/ tests/test_config.py tests/cli/test_init.py tests/cli/test_realslice.py tests/integration/test_real_provider_slice.py -q

# M3 五类型
uv run --extra dev pytest tests/relations/ tests/integration/test_typed_publication.py -q

# M4 编排器+队列+CLI+Skill
uv run --extra dev pytest tests/orchestrator/ tests/cli/test_agent_queue.py tests/cli/test_knowledge_build_skill.py tests/cli/test_build.py tests/cli/test_build_green_path.py -q

# M5 增量
uv run --extra dev pytest tests/incremental/ tests/cli/test_update.py -q

# M6 人工知识层
uv run --extra dev pytest tests/contracts/test_human_overlays.py tests/cli/test_edit.py -q
```

### 8.3 关键声明抽查

| 声明 | 验证方法 |
|---|---|
| 金色文件字节确定性 | `uv run --extra dev pytest tests/compiler/ -v` 中的 permutation/repetition 测试 |
| 发布恢复 | `uv run --extra dev pytest tests/storage/ -v` 中的 38 点故障注入矩阵 |
| 凭据脱敏 | `rg -n "REDACTED" src/knowledge_compiler/providers/codewiki.py` |
| verify-next 仅新鲜上下文 | `rg -n "fresh" src/knowledge_compiler/cli_agent_queue.py` |
| Skill 字节一致 | `cmp docs/project-materials/03-skills/knowledge-build/SKILL.md src/knowledge_compiler/skills/knowledge_build/SKILL.md` |
| build 绿色路径可达 | 运行 `tests/cli/test_build_green_path.py::test_build_green_path_publishes_generation` |
| 五类型金色 | `ls tests/golden/` 应有 6 个文件 |
| 设计修订已入 spec | `grep -c "Section 6.5" docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md` ≥ 3 |
| overlay 合同有 per-type 校验 | `rg -n "_TYPE_FIELDS" src/knowledge_compiler/contracts/human.py` |

### 8.4 已知限制检查（必须如实报告）

| 限制 | 验证方法 | 预期结果 |
|---|---|---|
| M5.8: Skill 扩展未交付 | `rg -n "knowledge-update" docs/project-materials/03-skills/knowledge-build/SKILL.md` | 无匹配（确认未交付） |
| M5.8: update exit 1/2 不可达 | 检查 `cli.py` update 命令代码 | 无 exit 1/2 路径 |
| M5.8: rename 仅 content hash | 检查 `changes.py` 的 rename 逻辑 | blob_id 未参与匹配 |
| M4.8b: 每类型 CodeWiki 夹具缺失 | `ls tests/fixtures/codewiki/0.6/normalized/` | 仅 8 个命令文件，无 per-type 提取夹具 |
| M7.2-M7.8: Wiki/HTML/FTS/MCP 未实现 | `rg -n "index.md\|architecture.md" src/` | 无完整 Wiki 编译 |
| M6.4-M6.5: 冲突/归档未接线 | `rg -n "conflicted" src/knowledge_compiler/orchestrator/runner.py` | 无 override 冲突检测 |

---

## 9. 下一位 Agent 的入口

1. **读 handoff To-do**（`docs/superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md`）— 权威执行清单
2. **跑 §8.1 基线验证** — 确认 551 测试全绿
3. **检查 §8.4 已知限制** — 确认声明与实际一致
4. **最大剩余项**：M7.2-M7.8（Wiki/HTML/FTS/MCP/安全套件）和 M8（基准协议）
5. **follow-up 清单**：M4.8b 和 M5.8（handoff 中有精确描述）

---

*归档日期：2026-08-25*
*归档时 HEAD：`7892063`*
*归档时 origin/main：`7892063`（同步）*
