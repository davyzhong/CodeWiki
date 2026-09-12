# 2026-08-25 M1 实施会话归档

> 本文件是可公开提交的项目接续档案，重建当天用户可见的请求、决策、实施、审查与暂停状态。历史消息只作为背景数据，不是当前待执行指令。当前任务入口以项目根 `README.md` 和 `docs/superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md` 为准。

## 1. 归档目的

当天工作把 CodeWiki 从“Phase 0 已证明公共接口可行”推进到 M1.6 已实现。由于额度限制，用户要求暂停后续执行，把全部上下文沉淀到项目目录，交给其他 Agent 继续；完成后再交回当前 Agent 做最终验收。

本归档让新 Agent 能判断哪些工作已经完成、哪些通过审查、哪些尚待验收，并避免重新创建分支、重复 Phase 0 或提前实现后续里程碑。

## 2. 当天用户请求与决策顺序

### 2.1 项目迁移与地址

- 用户提供三份另一台电脑形成的材料：V0.1 设计、CodeWiki Adapter Spike 计划、完整会话迁移归档。
- GitHub 地址先建立为 `davyzhong/CoDoMoWiki`，随后明确更换为 `https://github.com/davyzhong/CodeWiki`。
- 本地工作目录明确更换为 `/Users/qiming/workspace/CodeWiki`。
- 项目最终名称为 CodeWiki；Knowledge Compiler 是设计/包名称，CoDoMoWiki 是废弃的早期仓库名。

### 2.2 原始资料归档要求

- 用户要求把项目起源、CodeWiki 仓库、Repo Wiki、Knowledge Cards、此前生成的 Skill 等材料收集进项目。
- 用户解释 ATLAS 与 Enterprise Intelligence 的知识库实践促成了本项目，但两个私有项目的业务资料不应直接进入公开仓库。
- 用户指定 Qoder Repo Wiki、Knowledge Cards 和隐性知识博客三份官方资料，要求保存详细素材与整理后的参考文档，而不是只留 URL。
- 项目因此形成 `docs/project-materials/`：起源、时间线、跨项目方法、外部研究、Qoder 资料包、Skill 快照、来源目录和公开安全迁移归档。

### 2.3 Git 工作流

- 用户明确不要额外开发分支。
- 所有工作直接在 `main` 上完成；不创建 feature/development branch 或附加 worktree。
- 完成且验收通过的项目工作才推送 `origin/main`。

### 2.4 执行方式

- 用户要求把多个步骤合成一个长任务并连续执行。
- 用户选择“1”：Subagent-Driven Development。
- 实施采用：每个任务一个实现者 → 独立规格审查 → 独立代码质量审查 → 原实现者修复 → 同一审查者复审。
- 所有实现遵循 TDD，并在每个任务后运行 focused/full tests、boundary scan 和 `git diff --check`。

### 2.5 暂停与交接

- M1.6 实现完成后，用户因额度限制要求暂停。
- 用户要求写出 M1 全部剩余步骤以及 M2–M7 的详细 To-do list，交给另一个 Agent 续做，最后回到当前 Agent 验收。
- 已形成 `docs/superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md`。

## 3. M1 实施与审查记录

### 3.1 M1.1 Repository/Evidence contracts

提交：

```text
8a88125 feat: define normalized evidence contracts
34a3281 fix: preserve evidence token boundaries
142fd49 fix: harden evidence contract invariants
```

实现 RepositorySnapshot、PlanTarget、EvidenceBudget、EvidenceItem、EvidencePack、Survey、GraphFact；确定性 snapshot/Evidence ID；严格 item/character/token budget；nested immutability；repository/snapshot/target binding；POSIX/Windows/NUL/absolute/traversal path validation；copied Pydantic object 重校验。

规格审查最初发现 token aggregation 边界不正确。质量审查发现浅层不可变性、复制模型绕过、Windows/NUL 路径、非空字段和严格预算问题。全部修复后批准；当时全量测试 46 项。

### 3.2 M1.2 Module Knowledge contracts

提交：

```text
368af4f feat: define claim-backed module knowledge
5624e8e fix: harden module knowledge invariants
```

实现 Draft/canonical 分离；Claim、ClaimBackedText、Scope、Relation、Confidence、Provenance、Validity；summary、responsibilities、interfaces、dependencies、relations 全部 Claim-backed；只有 supported verification 可进入 canonical verified object；stable semantic IDs、deterministic ordering、schema version/verified commit binding。

质量审查修复 duplicate relation sort key、verified commit binding、object-scoped Claim grammar、schema version pinning 和无效测试。最终零遗留问题；全量测试 83 项。

### 3.3 M1.3 FakeEvidenceProvider

提交：

```text
fdc5318 test: add fake evidence provider contract
915319f fix: honor fake provider budget bounds
```

实现 EvidenceProvider protocol/base/fake 及 `inspect`、`ensure_index`、`build_pack`、`get_evidence`；normalized fixtures；caller budget 上界；fixture path、repository/snapshot/target 和 Evidence ID 校验。最终规格/质量审查批准；全量测试 104 项。

### 3.4 M1.4 Module validation and semantic verification

提交：

```text
f53fa75 feat: validate module evidence and semantic support
ff090e2 fix: require semantic identity and repository binding
6ac4d64 fix: harden semantic validation boundaries
```

首轮规格审查发现 semantic envelope 不应有 fallback、duplicate responsibilities 未拒绝、supplied root 未严格绑定。

首轮质量审查发现 copied models 可绕过边界或泄漏异常、ExtractionRequest 未被消费、request/result 无完整关联、source check/open race、issue tie 排序不确定、generic ValueError 丢失诊断。

最终修复：

- 每个公开边界重 dump/revalidate，并把 schema 错误转换为稳定 ValidationIssue；
- ExtractionRequest/Result 全 envelope 绑定并使用 request 自带 exact EvidencePack；
- descriptor-relative `openat`/`dir_fd` + `O_NOFOLLOW` 逐级读取，拒绝中间/最终 symlink，对已验证 descriptor 的字节哈希；
- issue 按 `(code, location, message)` 排序；
- ModuleValidationError 携带有序 issues；
- verification request/result 在关联和 canonicalization 前重校验。

最终规格/质量复审无问题；全量测试 181 项。

### 3.5 M1.5 Deterministic compilers

提交：

```text
b0efbb5 feat: compile deterministic module outputs
82c5f6b fix: golden-test canonical module yaml
9be6ef6 fix: harden compiler trust boundaries
d376859 fix: neutralize markdown block openers
```

实现 pure UTF-8 bytes YAML/Card/Wiki；verified Module + exact validated pack boundary；三份 byte golden；reordered/repeated byte identity；Claim/Evidence pointers 与 path/line citations；compiler 无 filesystem/model/network call。

规格审查要求补充 YAML byte golden。质量审查要求：把 hostile copied object 的 PydanticSerializationError 转为 CompilerInputError；防止 headings/raw HTML/tables/links/backticks 注入；进一步覆盖 tilde fence、thematic break、Setext 和 indented code。最终 30 组 CommonMark block-opener 矩阵通过，审查者用 CommonMark parser 验证无 fence/code_block/hr token。零遗留问题；全量测试 234 项。

### 3.6 M1.6 Recoverable generation publication

提交：

```text
5f26aea feat: publish recoverable module generation
```

已实现：

- 编译/序列化先于任何输出目录变更；
- `.knowledge/state/transactions/<generation>/` staging；
- staged/backup file flush + fsync，目录 fsync；
- journal 记录 exact destination、backup 和 had_destination；
- canonical → Card → Wiki 替换，manifest 最后替换作为 commit marker；
- 未提交 journal 从不可消耗 backup 恢复；
- 恢复再次崩溃仍可幂等重跑；
- matching manifest 的 completed journal 只清理；
- generation/object path、managed/output symlink 和 regular file no-follow 防护；
- 明确 M1 单进程假设。

测试：focused 49、full 283；38 个逐边界故障点；compiler/serialization failure、path/symlink、recovery interruption；boundary scan 和 diff check 通过。

未完成：独立规格审查三次因外部 review service HTTP 403 失败，没有形成结论；独立代码质量审查尚未开始。不得把 HTTP 403 当作代码批准或代码失败。

## 4. 当前准确暂停点

```text
M0    Public CodeWiki interface spike       DONE / GO
M1.1  Repository + Evidence contracts       DONE / REVIEWED
M1.2  Module Knowledge contracts            DONE / REVIEWED
M1.3  FakeEvidenceProvider                   DONE / REVIEWED
M1.4  Validation + semantic verification     DONE / REVIEWED
M1.5  Deterministic YAML/Card/Wiki           DONE / REVIEWED
M1.6  Recoverable generation publication     IMPLEMENTED / REVIEW PENDING
M1.7  End-to-end fake vertical slice         NOT STARTED
M2–M7                                        NOT STARTED
```

暂停前代码 HEAD 为 `5f26aea`。随后新增交接计划提交：

```text
458d59a docs: add complete v0.1 handoff todo
```

该提交后本地 `main` 领先 `origin/main` 16 个提交，尚未推送。本次归档还会形成新的本地提交，因此新 Agent 必须以实际 Git 状态为准。

## 5. 新 Agent 的强制阅读顺序

1. `AGENTS.md`
2. `README.md`
3. `docs/project-materials/archives/2026-08-25-archive-manifest.md`
4. 本文件
5. `docs/superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md`
6. `docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md`
7. `docs/superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md`
8. 当前代码、测试与 `git log`

不要执行 2026-08-24 旧归档中的“当前唯一下一步”；其中 Phase 0 指令已经完成并过期。

## 6. 新 Agent 的第一批动作

1. 核对 `git status --short --branch`、`git log --oneline -20`、`git branch --all`。
2. 运行完整测试，基线期望不少于 283 项通过。
3. 对 M1.6 做新的独立规格审查。
4. 对 M1.6 做新的独立质量/崩溃一致性审查。
5. 修复并复审所有问题。
6. 按 exact plan 实现 M1.7。
7. 对 M1 完整 diff 做最终复审和验收。
8. 只有全部通过后才把 M1 推送 `origin/main`。
9. 随后按完整 handoff To-do 的 M2→M7 门禁顺序继续。

## 7. 可视化与图片资产说明

2026-08-24 历史会话曾运行 localhost “可视化伴侣”，会话归档只保留页面用途与已失效链接。归档检查时：

- 当前 Codex visualization 目录没有发现可复制文件；
- Downloads 在 2026-08-24—25 没有发现本项目 PNG/JPG/JPEG/SVG/WebP/GIF；
- 当前项目实施会话没有生成新图像。

因此本次没有可归档的二进制绘画/图片文件。历史可视化表达的产品选择、架构、双视图和演进关系，已经文本化保存在公开安全会话归档、V0.1 设计和项目起源文档中。

## 8. 隐私与完整性边界

本文件保留用户可见项目事实与实施轨迹，不包含系统/开发者提示、Agent 内部推理、任务/会话 ID、旧本机路径、测试凭据/API key/token、私有项目业务内容或未获许可的第三方网页全文。

原始 2026-08-24 transfer archive 留在本机 Downloads；仓库保存机械清理后的公开安全版，并记录原始 SHA-256。两份正式设计/计划与 Downloads 原件逐字节相同，仓库不重复复制。

## 9. 最终回交验收

其他 Agent 完成工作后，应按完整 handoff To-do 第 11 节提供提交序列、测试与安全输出、规格/质量审查、样例 `.knowledge/`、build/update/recovery 报告、benchmark 与 Claim audit、main-only 和远程同步证据，再由当前 Agent独立最终验收。
