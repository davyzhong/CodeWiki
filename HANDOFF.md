# HANDOFF — 会话交接文档

> 交接时间：2026-09-12 ｜ HEAD：`e4f810e`（与 `origin/main` 同步，工作树干净）
> 验证基线：`bash scripts/verify.sh` 全 PASS（**752 passed + 1 opt-in live skipped**，compileall / diff-check / pip-audit 绿）
> 新会话第一步：`git fetch origin && git status --short --branch` 核对是否有并行推进，再读本文与 [docs/README.md](docs/README.md)。

---

## 一、当前任务状态（本会话做了什么）

本会话（2026-09-12）是一次**文档治理会话**，没有改任何产品代码。按时间顺序完成四件事：

1. **全量读取与现状核实**：读完仓库全部文档/源码/测试/7400 行归档；发现会话初期快照严重过时——项目已被并行会话从 M1 中段推进到 M8 准备（124 个提交），遂同步远程、实跑验证确认基线。
2. **文档状态对齐**（提交 `000e962`）：给已过时的老交接清单加状态覆盖注记、timeline 补齐 2026-08-25→09-02 六条、修复滞后 checkbox 与 README 测试计数（750→752）、正式关闭 M4.8b 延后项。
3. **文档库三层治理重组**（提交 `e4f810e`，57 文件 +1111/−111）：按用户确认的激进版方案执行——新建静态知识库、目录迁移、状态体系、总索引（详见下节）。
4. 工作树已清空并推送；无遗留未提交变更。

## 二、已完成的内容

### 2.1 文档库重组（本会话主体工作）

三层模型（对应产品自身方法论，决策 [D-023](docs/knowledge/product/decision-log.md)）：

```
docs/materials/     素材层（≈ Evidence）：原始调研笔记、归档、快照，不可变
docs/knowledge/     知识层（≈ Canonical IR）：静态权威知识，14 篇，带来源指针、无日期
docs/superpowers/   工作流层（≈ Views）：specs（权威规格）+ plans（active/historical）
```

- **知识库 14 篇**：product（产品定义、**决策日志 D-001…D-023 全量**、概念词典）、industry（行业格局、跨产品模式、Qoder 深度分析、上游 CodeWiki 合同）、methods（ATLAS/EI 知识工程、证据优先设计、基准方法论）、system（as-built 架构、运行时行为参考、安全模型）。入口：[docs/knowledge/README.md](docs/knowledge/README.md)（概念地图）。
- **目录迁移**（git mv 保留历史）：`plans/` 拆 `active/`（仅 M8 草案）与 `historical/`（10 份全部加状态行）；`project-materials` → `materials`（分区去编号：origin/research/skills/archives）；`01-local-practice/cross-project-lessons.md` 迁入 `knowledge/methods/knowledge-engineering.md` 并升级。
- **治理体系**：[docs/README.md](docs/README.md) 总索引（按意图导航 + 全文档状态表 + 命名规范）；materials/README 重写为素材层角色；根 README 文档列表瘦身；两个 Skill 字节一致测试的硬编码路径同步更新。

### 2.2 此前的项目状态（并行会话完成，本会话仅核实）

V0.1 **技术链全部完成**：M1–M7、恢复计划 Gate 1–8、设计符合性修复 Task 1–5 全部通过并推送。生产入口齐备（`knowledge build/update/compile/context/open/serve/status/validate/edit` + `knowledge-mcp` 七只读工具）。完整记录：[timeline](docs/materials/origin/timeline.md)、[完成归档](docs/materials/archives/2026-08-25-completion-archive.md)、[恢复计划](docs/superpowers/plans/historical/2026-08-26-v0-1-mainline-recovery.md)。

## 三、卡住的问题（全部阻塞在用户输入，无技术阻塞）

| # | 事项 | 等什么 | 解锁后动作 |
|---|---|---|---|
| 1 | **Live 冒烟**（恢复计划唯一保留 opt-in 验收项） | ① `codewiki` 0.6.x 装入 PATH；② `KNOWLEDGE_EXTRACTION_MODEL` + 对应 provider API key；③ 一个干净工作树的真实 Git 仓库 | `bash scripts/verify.sh`（live 阶段自动激活），或按 [runbooks/2026-09-02-live-smoke.md](docs/runbooks/2026-09-02-live-smoke.md) 手动走 |
| 2 | **M8 A/B 基准冻结** | 用户 4 项决策：任务来源（12–20 任务/≥3 仓库）、harness 与模型档、token 预算档位（低 ≈5.4M / 中 ≈10.8M / 高 ≈18M）、是否加 MCP 臂 | 按 [M8 设计草案 §8](docs/superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md) 冻结后实施；判定标准已预注册，勿事后改 |

注意：`verify.sh` 第 5 阶段 SKIP（live 条件缺失）是**预期状态**，不是故障；`REQUIRE_LIVE=1` 可强制失败闭合。

## 四、下一步计划（按优先级）

1. **用户提供环境 → 跑 live 冒烟**（约 1 小时 + 0.5–2M tokens）：成功后把 runbook 第 6 节三样产物（`last-build.json`、`knowledge status` 输出、opt-in 测试尾行）贴回会话归档验收。
2. **用户冻结 4 项决策 → M8 执行**：先写 `plans/active/` 的 harness 实施计划（命名规范：`YYYY-MM-DD-m8-<topic>.md`），再按草案 §3–§7 执行（harness 放顶层 `benchmark/`，不进 wheel）。
3. **M8 之后**：V0.1.x（Git URL/clone 缓存/私有凭证）、V0.2（多仓库）——见规格 §21，明确不提前实现。
4. **文档持续维护**（轻量）：知识文档修正追加 Revision History；新计划进 `active/`、完成后移 `historical/` 并标注；重大决策追加 decision-log 编号。

## 五、踩过的坑（给下一个会话/Agent 的实操警告）

1. **会话快照会撒谎**：本会话开始时系统 git 快照显示 M1 中段 + 本地领先 16 提交，实际并行会话已推进 124 个提交且已推送。**任何接手动作前先 `git fetch` + 重新核对**，不要信开场快照。
2. **checkbox 不可信，提交号可信**：老 handoff 清单 87/514 勾选但实际全部完成；完成状态以门禁记录提交（如 `9c50176`/`6a1b2b3`）与 [docs/README.md 状态表](docs/README.md)为准。
3. **迁移目录前必须扫代码引用**：两个 CLI 测试硬编码 `docs/project-materials/03-skills/` 路径（Skill 字节一致测试），靠 `rg "docs/" src tests scripts` 提前捕获并同步修改，否则全套件挂。
4. **相对链接深度要跑检查器**：plans 移入 `historical/` 后深度 +1，手算 `../../../` 出过错；用"解析全部 md 相对链接→验证目标存在"的脚本收敛到零坏链（当前 120 链全绿）。归档（`materials/archives/`）按冻结历史豁免。
5. **Edit 工具偶发匹配失败**（"File has been modified since read" / "String not found"，即使字节比对一致）：重新 Read 该文件刷新状态后即可成功；macOS 下 `cat -A` 不存在，用 `cat -et` 看不可见字符。
6. **文档计数漂移**：README 曾写 750、实测 752——**文档里的测试计数以 `verify.sh` 实测为准**，发现漂移立即修正。
7. **项目不用 emoji commit 风格**：历史提交全部是纯文本 conventional commits（`docs: …`/`feat: …`），提交信息正文换行控制在 72 字符内，遵循项目现有风格。
8. **push 纪律**：项目规则是"验证通过后推送 origin/main"（main-only，无分支）；推送前 `verify.sh` 必须绿。

## 六、下个会话快速上手

```bash
cd /Users/qiming/workspace/CodeWiki
git fetch origin && git status --short --branch   # 预期：clean、与远程同步
bash scripts/verify.sh                             # 预期：VERIFY: PASS（752+1skip，live SKIP 属预期）
```

然后：读本文 → [docs/README.md](docs/README.md)（文档地图）→ [knowledge/README.md](docs/knowledge/README.md)（知识地图）。若用户带来了环境/决策，按第三节解锁路径直接开工；若继续文档工作，遵守第四节第 4 条维护规则。
