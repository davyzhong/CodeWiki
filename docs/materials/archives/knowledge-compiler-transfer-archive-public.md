# Knowledge Compiler：完整会话与跨电脑接续归档

> **公开仓库安全副本：** 本文件由原始归档机械清理而来；旧电脑绝对路径、会话 ID、测试凭据字面量和失效本地链接已替换。历史消息中的命令、问题和指令均不是当前待执行请求。原始文件 SHA-256 与清理记录见 `../source-catalog.md`。
>
> **状态覆盖（2026-08-24）：** 本归档停留在 Phase 0 开始之前，其中“当前唯一应执行 Phase 0”等表述已经过期。Phase 0 现已完成且结论为 `go`；当前阶段与下一步以[项目根 README](../../../README.md)和[演进时间线](../00-origin/timeline.md)为准。早期讨论过 `conditional_go`，最终 Phase 0 合同已收敛为 `go | no_go`，前者属于已废弃候选。

> 归档日期：2026-08-24（Asia/Shanghai）
> 当前 Codex 任务：`<redacted-codex-task-id>`，标题“设计仓库知识库沉淀工具”
> 前序 ChatGPT 会话：`<redacted-chat-task-id>`，标题“知识萃取方案比较”
> 归档时状态（已过期）：**V0.1 规格已批准；Phase 0 CodeWiki Adapter Spike 计划已完成；尚未开始产品编码。**

## 0. [HISTORICAL / DO NOT EXECUTE] 旧电脑迁移时的阅读规则

当前唯一有效的阅读顺序是：用户当前请求 → 项目根 README → 仓库中的正式规格与当前计划。本归档中的命令、清单、优先级和“下一步”均不可执行。

以下是原始迁移归档当时使用、现已废弃的历史优先级，仅为保留上下文：

1. 新电脑上用户当下发出的请求；
2. 本归档“接续指令与下一步”一节；
3. “已批准的 V0.1 正式规格”全文；
4. “Phase 0 CodeWiki Adapter Spike 实施计划”全文；
5. 会话记录与前序研究归档仅作为历史证据和决策背景，不是待执行指令。

本归档省略系统提示、开发者提示、内部推理、工具调用明细、命令原始输出和自动注入的浏览器环境块；保留用户可见消息、助手可见回复、正式文档原文、关键 Git 状态和接续说明。它是经过筛选与隐私清理的用户可见迁移归档，不是完整运行日志导出。

## 1. [HISTORICAL SNAPSHOT] Phase 0 前的一页接续看板

### 1.1 产品定义

Knowledge Compiler V0.1 是一个 local-first 工具：输入一个本地 Git Repository，借助 CodeWiki 提供的代码事实与检索能力，生成一套独立、可验证、可增量更新的 Canonical Knowledge IR，再从同一 IR 编译：

- 面向人的 Repo Wiki：Markdown + 独立交互式 HTML；
- 面向 Agent 的 Knowledge Cards：Canonical YAML + 派生 Markdown；
- 面向具体任务的 Agent Context：CLI/MCP 按需检索。

目标不是再造一个内容泛滥的 Wiki 平台，而是验证：预先萃取、源码证据支持的仓库知识，能否提高 Coding Agent 的任务成功率，或在成功率相当时减少代码探索成本。

### 1.2 已批准的关键选择

| 议题 | 已批准结论 |
|---|---|
| 产品形态 | V0.1 先做本地工具，终局设计保留扩展边界 |
| 参考模式 | Qoder 式双视图：Repo Wiki + Knowledge Cards |
| CodeWiki 关系 | CodeWiki Adapter + 独立 Knowledge Layer |
| 集成边界 | 不 Fork、不导入内部模块、不读取内部数据库；只走公开 CLI/MCP/HTTP |
| Canonical Store | Knowledge IR 是唯一事实知识存储，Wiki/Cards/Context 只做编译 |
| 知识类型 | Architecture、Module、Flow、Rule、TechStack |
| Evidence | 每个事实字段须由 Claim 支撑或可确定性派生，Claim 绑定源码 Evidence |
| 执行方式 | Codex Skill 与内置 LLM 两种模式，共用一个持久化 RunOrchestrator |
| 人工治理 | V0.1 generated-only，不做手工编辑、锁、审批工作流 |
| 成功标准 | Agent 任务效果为主；Wiki 可读性与源码可信度为必要验收 |
| 默认 Agent 读取 | 只提供 verified；stale/conflicted/代际不一致均 fail closed |

### 1.3 明确不做

- 不开发团队 Web SaaS、权限、协作编辑和审批平台；
- 不把 CodeWiki 内部数据库结构当成稳定 API；
- 不让 CodeWiki Wiki 与 Knowledge Cards 各自生成互相矛盾的事实；
- 不在 Phase 0 之前凭假设设计后续 Evidence DTO；
- 不把 `.knowledge/`、`.codewiki/` 等生成目录重新扫描进知识库；
- 不让模型单独决定对象退休或删除；
- 不在 V0.1 加入 API、Decision、Data Model、Incident 等扩展类型。

## 2. 已批准架构摘要

```text
Local Git Repository
  ↓ eligible-file snapshot / diff
CodeWiki Public Interfaces
  ↓ versioned EvidenceProvider Adapter
Bounded Evidence Packs
  ↓ Planner + RunOrchestrator
Knowledge Extraction (Codex Skill or LiteLLM)
  ↓ Claim-backed validation / repair
Canonical Knowledge IR
  ├─ Repo Wiki (Markdown + standalone HTML)
  ├─ Knowledge Cards (YAML + Markdown)
  └─ Task Context (CLI + 7 read-only MCP tools)
```

七个 MCP 读取工具：

- `knowledge_repo_overview`
- `knowledge_search`
- `knowledge_get_object`
- `knowledge_get_related`
- `knowledge_get_evidence`
- `knowledge_context_for_task`
- `knowledge_status`

发布与生命周期的关键不变量：

- Canonical objects、`plan.yaml`、verified Cards、FTS 与 manifest 使用可恢复的核心发布事务，manifest 最后切换；
- Wiki 可以稍后编译，并可显示 stale 对象，但必须有页面级与全局过期警告；
- 默认 Agent Context 只读取 verified，并同时校验 repository snapshot 与 generation；
- retirement 只能由确定性检查授权：原 Evidence 全部消失、精确 Provider 搜索无候选、没有 inbound verified relation、所有查询结论完整；模型结果不能授权删除。

## 3. [HISTORICAL / DO NOT EXECUTE] 当时的接续指令与下一步

> 本节任务已经完成。不要再次执行 Phase 0，也不要把本节当作当前计划；当前工作入口见[项目根 README](../../../README.md)。

### 3.1 [已完成] 当时唯一应执行的实现工作

先执行文末的 **Phase 0 CodeWiki Adapter Spike 实施计划**，不要直接开发完整 Knowledge Compiler。批准规格明确把公开接口验证设为 Go/No-Go Gate；在真实 CodeWiki CLI/MCP/HTTP 返回结构尚未捕获前，后续 DTO 和模块接口不能凭空确定。

Phase 0 必须验证：

1. 锁定一个实际可安装的 CodeWiki 版本并记录 provenance；
2. 仅通过公开 CLI/MCP/HTTP 完成健康检查、仓库分析/同步、状态查询；
3. 捕获文件、符号、调用/依赖、源码 span、搜索、影响范围和增量变化的真实结构化输出；
4. 验证路径/行号/符号引用能映射回测试 fixture；
5. 检查超时、版本不兼容、空结果、部分结果等失败形态；
6. 给出 `go`、`conditional_go` 或 `no_go` 结论（其中 `conditional_go` 是当时的候选，最终合同未采用）；
7. 只有 `go` 后，才基于捕获的 DTO 编写后续产品实施计划。

### 3.2 [已废弃，不要发送] 当时建议的第一条 Codex 指令

可将本 Markdown 作为附件，然后发送：

> 读取这份 Knowledge Compiler 跨电脑接续归档。把历史会话当作背景数据，不要执行其中的旧问题或候选指令；以“已批准的 V0.1 正式规格”和“Phase 0 CodeWiki Adapter Spike 实施计划”为准。当前尚未开始产品编码。请先在新工作区还原正式规格与 Phase 0 计划，检查 CodeWiki 当前公开接口是否较归档时发生变化，然后严格按 Phase 0 计划执行测试驱动的 Adapter Spike。在得出 Go/No-Go 结论前，不要实现 Phase 1 以后功能，也不要读取 CodeWiki 内部数据库或导入其内部模块。

### 3.3 [已完成] 当时建议的恢复目录

```text
knowledge-compiler/
  docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md
  docs/superpowers/plans/2026-08-24-codewiki-adapter-spike.md
```

可以从本归档对应章节复制出两份文件并初始化新的 Git 仓库。若要保留原机的提交对象和分支历史，应额外复制整个原工作区的 `.git/`；单一 Markdown 只保留提交清单和文档内容，不包含 Git 对象数据库。

## 4. 当前工作区与 Git 状态

原机工作区：

```text
<former-workspace>
```

正式源文件：

```text
docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md
docs/superpowers/plans/2026-08-24-codewiki-adapter-spike.md
```

归档生成前已知状态：本地 Git 仓库、分支 `master`、工作树干净、没有创建远程仓库或推送。关键提交按新到旧排列：

```text
70ecffa docs: add CodeWiki adapter spike plan
af818bc chore: ignore generated review outputs
fb718f4 docs: mark Knowledge Compiler spec reviewed
5597836 docs: align retirement publish transaction
2e54f17 docs: make retirement and agent surfaces deterministic
c8418c7 docs: define retirement and stale view lifecycle
028f814 docs: close Knowledge Compiler spec gaps
6c38eaa docs: add Knowledge Compiler V0.1 design
```

尚未存在的内容：产品源代码、Python package、CLI、MCP server、测试 fixture、CodeWiki Adapter 实现、benchmark 结果。不要把“文档与计划完成”误解为“工具已经实现”。

## 5. 规格审查与修订记录

规格经历五轮独立审查，最终无阻塞问题：

1. 第一轮补齐 CodeWiki 公共接口 Spike、生成目录自污染、跨机器增量基线、可恢复 Orchestrator、事实字段 Claim 支撑、Canonical Object 与 Target Result 状态分离；
2. 第二轮补齐确定性 retirement、Wiki 与 Agent 对 stale 的差异策略、统一 Agent lease/幂等协议；
3. 第三轮移除模型对 retirement 的授权，把 canonical/Cards/FTS 纳入同一可恢复事务，并让 Agent 读取对 snapshot/generation 不匹配 fail closed；
4. 第四轮统一 retirement 与发布事务描述，补充 Wiki generation 落后时的全局警告；
5. 第五轮通过；随后补充 `plan.yaml` 崩溃 swap 点和主 CLI 中 `--include-stale` 的可发现性。

## 6. 资料来源与时效说明

本归档合并四类内容：

1. 前序 ChatGPT 完整研究归档（原文件 3,765 行）；
2. 当前 Codex 任务的用户/助手可见对话；
3. 已批准 V0.1 正式规格（原文件 717 行）；
4. Phase 0 Adapter Spike 实施计划（原文件 819 行）。

市面产品、CodeWiki 版本、命令和公开接口会变化。归档中的竞品与 CodeWiki 研究是 2026-08-24 当时的核验结果；新电脑开始 Spike 时必须重新检查官方仓库、当前发布版本和公开文档。正式规格定义的是产品边界，Phase 0 的目的正是把变化中的外部接口转成经实测的契约。

---

# 第一编：当前 Codex 会话可见对话记录

## 消息 001｜用户

时间：2026-08-24T07:53:31.457Z

<recommended_plugins>
Here is a list of plugins that are available but not installed.

- Atlassian Rovo (atlassian-rovo@openai-curated-remote)
- Box (box@openai-curated-remote)
- Google Calendar (google-calendar@openai-curated-remote)
- Notion (notion@openai-curated-remote)
- Outlook Calendar (outlook-calendar@openai-curated-remote)
- Outlook Email (outlook-email@openai-curated-remote)
- SharePoint (sharepoint@openai-curated-remote)
- Slack (slack@openai-curated-remote)
- Teams (teams@openai-curated-remote)
</recommended_plugins>
# AGENTS.md instructions

<INSTRUCTIONS>
# 我的偏好
请默认使用中文回答。

减少常见LLM编码错误的行为准则。可根据需要与项目特定指令合并。
**权衡：**这些准则倾向于谨慎而非速度。对于简单任务，自行判断即可。
## 1. 先思考再写代码
**不要假设。不要隐藏困惑。把权衡摆到台面上。**
在动手实现之前：
- 明确说出你的假设。不确定就问。
- 如果存在多种理解方式，全部列出来——不要默默选一个。
- 如果有更简单的方案，说出来。该反驳就反驳。
- 如果有什么不清楚的，停下来。说明哪里让你困惑。提问。
## 2. 简洁优先
**用最少的代码解决问题。不写投机性代码。**
- 不加超出需求的功能。
- 一次性代码不搞抽象。
- 没人要求的"灵活性"和"可配置性"不要加。
- 不要为不可能出现的场景写错误处理。
- 如果你写了200行但50行就能搞定，重写。
问自己一句："一个资深工程师会说这写复杂了吗？"如果是，简化。
## 3. 精准修改
**只动必须动的地方。只清理自己制造的问题。**
编辑已有代码时：
- 不要顺手"改进"旁边的代码、注释或格式。
- 没坏的东西不要重构。
- 匹配现有风格，即使你会用不同的写法。
- 如果注意到不相关的死代码，提一嘴就好——别删。
当你的修改产生了孤立代码时：
- 移除因你的改动而变成未使用的import、变量和函数。
- 不要动原本就存在的死代码，除非被明确要求。
检验标准：每一行改动都应该能直接追溯到用户的需求。
## 4. 目标驱动执行
**定义成功标准。循环验证直到确认通过。**
把任务转化为可验证的目标：
- "加验证"→"为非法输入写测试，然后让测试通过"
- "修这个bug"→"写一个能复现它的测试，然后让测试通过"
- "重构X"→"确保重构前后测试都能通过"
对于多步骤任务，列出简要计划：
1. [步骤]→验证：[检查项]
2. [步骤]→验证：[检查项]
3. [步骤]→验证：[检查项]
强成功标准让你能独立循环推进。弱标准（"让它能跑"）则需要不断澄清。
---
**这些准则起作用的标志是：**diff中不必要的改动更少了，因过度复杂化而返工更少了，澄清性问题出现在实现之前而不是犯错之后。
</INSTRUCTIONS>

## 消息 002｜用户

时间：2026-08-24T07:53:31.628Z

知识萃取方案比较（历史会话引用已移除）  我们要基于前面聊天的内容，实现一个读取我们 repository 并沉淀出完整知识库的工具。这个工具可以参考市面上各种 repo wiki 或 code wiki 等类似产品，但我也希望做得相对克制一些，不要过于泛滥。

## 消息 003｜助手（过程更新）

时间：2026-08-24T07:53:37.390Z

我会先把这件事收敛成一个可验证的 V0.1：先读取归档与当前工作区，确认已有设计和代码基础，再明确“完整知识库”的边界、最小交付物与验收标准。这里我会使用 `brainstorming` 技能，因为当前需求涉及产品边界和实现取舍；它会先帮助把方案收敛，再进入编码。

## 消息 004｜助手（过程更新）

时间：2026-08-24T07:53:50.773Z

我已确认当前工作区基本是空的，真正的上下文集中在 3,765 行归档中；归档已经包含 Knowledge IR、验证、编译、增量失效和 MCP 的初步设计。接下来我会先定位其中的 V0.1 边界、目录结构、CLI 与验收实验，避免重新发明一套方案。

## 消息 005｜助手（过程更新）

时间：2026-08-24T07:53:58.720Z

接下来的取舍会涉及架构边界、数据流和知识库产物形态，用图会更容易比较。我可以在浏览器里展示架构图、界面草图和方案对比；这个功能还比较新，也会消耗更多 token。要试用吗？（需要打开一个本地 URL）

## 消息 006｜助手（最终回复）

时间：2026-08-24T07:54:02.047Z

要启用浏览器可视化伴侣来辅助架构和方案比较吗？（需要打开本地 URL）

## 消息 007｜用户

时间：2026-08-24T07:54:39.030Z

要

## 消息 008｜助手（过程更新）

时间：2026-08-24T07:54:46.678Z

好的，我会启用可视化伴侣；这是 `brainstorming` 技能要求的设计阶段辅助方式。我先读取它的使用规范并提炼归档中的 V0.1 约束，随后通过一个个关键问题把范围收敛下来；在你批准设计前，我不会开始写代码。

## 消息 009｜助手（最终回复）

时间：2026-08-24T07:55:30.542Z

先确认 V0.1 的产品形态。你希望第一版优先是哪一种？

A. 本地 CLI 工具（推荐）：开发者在任意 Git Repo 中运行命令，生成 `.knowledge/`、Markdown Wiki 和 Agent Context。
B. 团队 Web 服务：上传或连接 Repo，通过网页浏览和维护知识库。
C. 纯引擎/SDK：先提供 Python API 与数据模型，不强调最终用户体验。

我建议选 A：最符合“克制”，也最容易验证它是否真的降低 Agent 的代码探索成本。

可视化伴侣已运行：打开页面（历史本地可视化，已失效）。当前页面会保持等待，等进入架构与产物形态确认时再更新。

## 消息 010｜用户

时间：2026-08-24T07:57:18.757Z

市面上其他的产品是怎么选择的？我看你说的 Code Wiki 有 Codex 的 skill 插件，那么 Code Wiki 不就是我们最可以拿来借鉴的 MVP 产品吗？它的实现方式是什么？我们 0.1 版的产品形态能不能直接基于它来展开呢？

## 消息 011｜助手（过程更新）

时间：2026-08-24T07:57:28.249Z

这个判断很关键：如果 CodeWiki 已经覆盖“Repo → 可浏览 Wiki”以及可复用的 Codex Skill，我们就不该从零重做它。我会先核实你指的 CodeWiki 具体项目、它当前的架构与授权，再把它放进竞品分层里判断：是直接作为 V0.1 产品底座、仅作为 Evidence Engine，还是作为可替换参考实现。由于信息会变化，我会按 `web-access` 技能做一次最新资料核验。

## 消息 012｜助手（过程更新）

时间：2026-08-24T07:58:25.407Z

核验后，结论比归档里更明确：你说的应当是 `PorunC/CodeWiki`。它现在不只是“可借鉴项目”，而是一个 MIT 授权、可从 PyPI 安装的单用户本地平台，已经具备 AST 图、GraphRAG、Wiki、Codex Skill、MCP 和增量更新。不过它仍标注为 Alpha，而且核心 Canonical Model 是 code graph / chunks / wiki pages，不是我们设想的 claim-level Knowledge IR。我要再核查它的 Skill 和 benchmark，确认哪些能力能直接复用、哪些是产品差异的真正空白。

## 消息 013｜助手（最终回复）

时间：2026-08-24T08:00:03.622Z

可以，CodeWiki 应当成为 V0.1 的首选底座。但我不建议直接 Fork 整个平台；更稳妥的是把它作为可替换的 Evidence/Wiki Engine，通过 CLI、MCP 或 HTTP 适配，在上面增加我们自己的 Knowledge Layer。

### 市面上的几种选择

| 路线 | 代表产品 | 重点 |
|---|---|---|
| 自动 Wiki | Google Code Wiki、DeepWiki | 自动生成可阅读文档、图表和问答 |
| IDE 内知识层 | Qoder | Repo Wiki + Knowledge Cards + Memory，直接服务编码任务 |
| Agent Memory | GitHub Copilot Memory | 持续积累少量仓库事实，使用前验证引用 |
| 本地代码智能平台 | CodeWiki | AST 图、GraphRAG、Wiki、MCP、Codex Skill |
| 静态指令文件 | AGENTS.md、CLAUDE.md | 成本最低，但主要依靠人工维护 |

Google Code Wiki选择的是托管式“自动 Wiki + Gemini 问答”，仓库变化后重新生成文档。[Google 官方介绍](https://developers.googleblog.com/introducing-code-wiki-accelerating-your-code-understanding/)

Qoder走得更深：Repo Wiki 面向人，Knowledge Cards 面向 Agent，并持续跟踪代码变化；知识还能存入 `.qoder/repowiki` 进入 Git 管理。[Qoder Knowledge Cards](https://docs.qoder.com/user-guide/knowledge-engine/knowledge-cards)

GitHub Copilot Memory更加克制：不生成完整 Wiki，而是积累带源码引用的仓库事实，并在使用前对当前分支重新验证。[GitHub 官方文档](https://docs.github.com/en/copilot/concepts/agents/copilot-memory)

CodeWiki基本覆盖了前三者的开源基础设施，但当前产品中心仍然是“代码图谱 + Wiki + Q&A”，而不是独立的、可治理的 Agent Knowledge IR。

### CodeWiki 是怎么实现的

它的核心管线是：

```text
Repository
  ↓
RepoScanner
  ↓
tree-sitter AST
  ↓
Code Graph
  ↓
社区检测
  ↓
FTS / 可选向量索引
  ↓
GraphRAG
  ↓
Wiki / Q&A / MCP / Codex Skill
```

关键实现点包括：

- 使用 tree-sitter 支持 Python、TypeScript、Java、Go、Rust、C/C++、C# 等语言。
- 确定性提取文件、符号、调用、导入、继承、路由、配置引用。
- 图上的边记录置信度、是否推断及 provenance。
- 使用符号搜索、全文检索、可选向量检索和图扩展组成 GraphRAG。
- LLM 负责组织和解释，AST 与源码才是事实来源。
- Wiki 页面只有在引用文件、行号和 citation 校验通过后才进入 `generated` 状态。
- Git diff 与文件 hash 用于增量更新，受影响页面被标记为 stale。
- 默认 SQLite，也支持 PostgreSQL、pgvector。
- 项目采用 MIT License，但当前仍标注为 Alpha。

完整设计见 [CodeWiki 架构文档](https://github.com/PorunC/CodeWiki/blob/main/docs/design.md)，使用方式见 [官方 Usage Guide](https://github.com/PorunC/CodeWiki/blob/main/docs/usage.md)。

### Codex Skill 实际做什么

它并不是另一套分析引擎，而是让 Codex调用 CodeWiki 已有能力：

```text
analyze repository
  ↓
wiki plan
  ↓
获取某一页的 compact evidence
  ↓
Codex 只依据 evidence 写 Markdown
  ↓
save
  ↓
validate citations
  ↓
export HTML
```

Skill 特意限制 Codex不能直接摄入庞大的 GraphRAG Context，而是每页只拿有限证据；也禁止编造源码中不存在的路径、API 和架构事实。[CodeWiki Skill 源码](https://github.com/PorunC/CodeWiki/blob/main/backend/skills/codewiki/SKILL.md)

所以你的判断是对的：它已经是非常合适的 MVP 参考，甚至可以直接成为底座。

### 为什么不建议直接整体 Fork

CodeWiki已经包含 FastAPI、React、Graph UI、Wiki、翻译、GraphRAG、LLM 路由、两种数据库和大量运行配置。整体 Fork 会让我们第一天就继承一个完整平台，而我们的真正差异还没有得到验证。

更重要的是，它目前的核心存储模型主要是：

```text
code_node
code_edge
graph_community
code_chunk
doc_catalog
doc_page
llm_run
```

缺少我们真正想验证的：

```text
KnowledgeObject
Claim
Evidence
Confidence
Validity
Conflict
Governance
Task Context
```

Wiki 页面有引用，不等于每一条知识 Claim 都是可查询、可失效、可治理的对象。

### 推荐的 V0.1 产品形态

```text
CodeWiki
├── Repo 扫描
├── AST / Code Graph
├── Source Evidence
├── GraphRAG
├── Wiki 基础生成
└── 增量变化检测
          ↓
Knowledge Compiler
├── Architecture / Module / Flow / Rule / TechStack
├── Claim-level Evidence
├── Validity / Conflict / Freshness
├── Knowledge Cards
└── context_for_task
          ↓
Codex / Claude Code / Cursor
```

具体策略：

- 把 CodeWiki 当作安装依赖，而不是复制其代码。
- 优先通过 CLI/MCP/HTTP 适配，避免依赖其 Alpha 阶段内部 Python 模块。
- 直接复用 CodeWiki Wiki，不再开发第二套 Wiki UI。
- 我们只开发 `.knowledge/`、Knowledge IR、验证器、Context Compiler 和 Agent 接口。
- V0.1 暂不开发 Web UI、Graph UI、向量数据库和 AST Parser。
- 同时保留 `EvidenceProvider` 接口，将来可以替换为其他引擎。

这会把 V0.1 从“再造一个 CodeWiki”收敛成：

> **CodeWiki 提供代码事实与 Wiki；Knowledge Compiler 把这些事实编译成可验证、可治理、可按任务消费的 Agent Knowledge。**

可视化页面已更新：查看三种基于 CodeWiki 的展开方式（历史本地可视化，已失效）。

现在只需要确认一个产品边界：你是否同意把 V0.1 的核心差异定义为“面向 Agent 的 Knowledge Layer”，直接复用 CodeWiki 的 Wiki 和代码图谱，而不把“做一个更好的 Wiki UI”作为第一版目标？

## 消息 014｜用户

时间：2026-08-24T08:07:50.005Z

我觉得你的建议也有一些道理。目前看下来，Qoder 的这种模式还是比较适合我的。之前我们进行的本地归档知识库整理，也是考虑到了面向人和面向 Agent 的两种不同的交互模式。现在看来，Report wiki 和 knowledge cards 这两种展现形式是一个比较好的展现方式。

## 消息 015｜助手（过程更新）

时间：2026-08-24T08:08:12.008Z

你的反馈把产品边界进一步定住了：不是只做 Wiki，也不是只做 Agent Memory，而是同一份仓库知识提供两种编译视图——Repo Wiki 面向人理解与浏览，Knowledge Cards 面向 Agent 精确消费。`brainstorming` 技能因此会把“双视图、同源证据、避免内容漂移”作为后续设计的硬约束。现在我先读取你在可视化页面上的选择，再更新双视图结构图。

## 消息 016｜助手（最终回复）

时间：2026-08-24T08:08:43.284Z

我同意。产品形态可以正式收敛为：

```text
Repository
  ↓
CodeWiki Evidence Layer
  ↓
Canonical Knowledge IR
  ├─ Repo Wiki：面向人阅读、导航、理解
  └─ Knowledge Cards：面向 Agent 检索、推理、执行
```

关键是 Wiki 和 Cards 不能各自重新理解一次代码，否则很快产生漂移。它们应共享同一组 Knowledge Objects、Claims 和源码 Evidence，只采用不同的组织密度与表达方式。

这也意味着 CodeWiki 更适合作为底层的扫描、代码图谱、证据检索和增量检测能力；它现有的 Wiki 生成可以复用或参考，但我们的 Canonical Source 应当是 Knowledge IR。

双视图结构已经更新到：可视化伴侣（历史本地可视化，已失效）。

下一个边界问题：V0.1 是否允许人对 Knowledge Cards 进行补充和修订？

A. 仅自动生成，暂不允许编辑。
B. 允许人工补充、修订和锁定（推荐），机器发现冲突时提示，但不能静默覆盖。
C. 增加完整的审核、发布和版本审批工作流。

我建议 B：它能容纳代码里无法完整表达的业务规则和架构意图，又不会把 V0.1 扩张成知识管理平台。

## 消息 017｜用户

时间：2026-08-24T08:12:38.057Z

A

## 消息 018｜助手（过程更新）

时间：2026-08-24T08:12:47.793Z

收到，V0.1 选择“仅自动生成、不可人工编辑”。这让第一版更克制：先验证自动萃取的可信度和 Agent 效果，暂不引入人工覆盖、锁定、冲突审批等治理机制。可视化页面将暂时切回等待状态，继续在终端确认输入范围。

## 消息 019｜助手（最终回复）

时间：2026-08-24T08:12:58.667Z

下一个问题：V0.1 首先支持多大的 Repository 范围？

A. 单个本地 Git Repository（推荐）：在仓库根目录运行，包含普通单体项目或单仓库 Monorepo。
B. 本地路径或远程 Git URL：工具也负责 Clone 和管理缓存。
C. 多 Repository 系统：跨多个仓库生成统一服务拓扑和知识库。

我建议 A。它已经能覆盖多数实际代码库，也能直接利用 CodeWiki Lite/本地模式；远程 Clone 和跨仓库知识关系可以后续再加。

## 消息 020｜用户

时间：2026-08-24T08:13:32.389Z

这几个选项有什么优缺点

## 消息 021｜助手（最终回复）

时间：2026-08-24T08:14:29.198Z

主要差异不在“能不能读取代码”，而在输入管理、版本一致性和知识关系复杂度。

| 选项 | 优点 | 缺点 | 适合验证什么 |
|---|---|---|---|
| A. 单个本地 Git Repo | 最简单；隐私最好；直接使用当前分支和未提交代码；容易做增量更新；开发者能核查源码引用 | 用户需要自己 Clone；暂不能跨仓库理解系统 | Knowledge IR、Wiki、Cards 是否准确和有用 |
| B. 本地路径 + Git URL | 使用方便；输入一个 URL 即可生成；适合公开仓库演示 | 需要处理 Clone 缓存、分支、凭证、私有仓库、更新、磁盘清理；远程版本可能与开发者本地代码不同 | 产品易用性和公开 Demo |
| C. 多 Repo 系统 | 能描述微服务拓扑、跨仓库调用和共享业务流程；企业价值最高 | 需要解决服务身份、版本组合、跨仓库依赖、权限、重复实体和增量同步，复杂度远超前两者 | 企业级系统知识库 |

### A 的具体边界

A 不是只能处理小项目，它可以支持：

```text
一个 Git Root
├── 单体应用
├── 前后端同仓库
└── Monorepo
    ├── apps/
    ├── packages/
    └── services/
```

只要它们属于同一个 Git Repository，就共享明确的 commit、branch 和 diff，知识有效性比较容易判断。

它的不足是不能自动得到：

```text
frontend-repo
  ↓ API
gateway-repo
  ↓ event
order-service-repo
```

这种跨仓库完整链路。

### B 看似只是增加 Git Clone，实际多出一层 Repository Management

需要决定：

- Clone 到哪里、何时清理；
- 默认分析哪个 branch；
- URL 相同但 commit 不同是否共用缓存；
- 私有仓库怎样提供凭证；
- 是否允许执行仓库中的脚本；
- remote 更新后旧 Knowledge 如何失效；
- 本地 Repo 和远程 Repo 同名时如何识别。

CodeWiki本身已经支持本地路径和 Git URL，因此如果我们依赖它，B 的基础 Clone 能力不需要重写；但凭证、安全和生命周期仍需要由产品定义。[CodeWiki Usage Guide](https://github.com/PorunC/CodeWiki/blob/main/docs/usage.md)

### C 为什么不适合 V0.1

单 Repo 的版本坐标很明确：

```text
repository + branch + commit
```

多 Repo 的知识有效性则变成：

```text
repo-A@commit-1
+ repo-B@commit-2
+ repo-C@commit-3
```

任何一个仓库变化，都可能让跨服务 Flow 失效。还需要判断两个仓库中的 `Order`、`User`、`Payment` 是否指向同一个业务实体。这实际上已经进入企业知识图谱范围。

### 我的建议

采用分阶段边界：

```text
V0.1：A，单个本地 Git Repo
架构预留：RepositoryProvider 接口
V0.1.x：增加 Git URL
V0.2+：多 Repo Workspace
```

这样第一版能把研发精力集中在最关键的假设上：

> 同源生成的 Repo Wiki 和 Knowledge Cards，是否真的比 Agent 临时搜索代码更准确、更省上下文。

你倾向先选 A，还是因为“一条 Git URL 直接生成知识库”的体验很重要，想把 B 也放入 V0.1？

## 消息 022｜用户

时间：2026-08-24T08:23:04.869Z

我们现在是尝试着做出来工具进行迭代，还是进行这个设计的讨论？

1. 如果是做出来工具，然后持续不断地完善和迭代，那么我同意可以先用 A 方案，一点点增加功能。
2. 如果是进行整个工具面向终局的设计讨论，我觉得还是会把可能要运用的场景、需要最佳的功能都放进去，那我会倾向于方案 B。

## 消息 023｜助手（过程更新）

时间：2026-08-24T08:23:18.088Z

你指出的是设计层级问题，而不是功能偏好问题。当前更合理的做法是同时保留“终局方向”和“下一版可交付边界”，但这轮讨论的输出应是一份能马上进入实现的 V0.1 设计；否则容易再次停留在完整蓝图而没有可运行工具。我会把可视化页面更新为“长期架构不缩水、V0.1 分阶段落地”的关系。

## 消息 024｜助手（最终回复）

时间：2026-08-24T08:23:46.777Z

我们现在做的是：

> 为一个马上要实现、随后持续迭代的工具，完成 V0.1 可执行设计。

不是只讨论终局蓝图，也不会立刻写代码。流程是：

```text
明确长期方向
  ↓
划定 V0.1 最小闭环
  ↓
你批准设计
  ↓
写实施计划
  ↓
实现工具
  ↓
用真实 Repo 验证
  ↓
根据结果迭代
```

“终局设计”可以定义稳定边界，但不适合现在把所有最佳功能详细设计完。因为很多判断必须从第一版运行结果中获得，例如：

- CodeWiki 的 Evidence 是否足够支持 Knowledge Cards；
- 五类 Knowledge Object 是否都值得保留；
- Wiki 与 Cards 是否真的应该完全由同一 IR 生成；
- 哪些知识对 Agent 最有帮助；
- 增量更新应该做到文件级、符号级还是 Claim 级；
- Git URL 和多 Repo 是否值得增加其复杂度。

因此我建议：

- 长期产品方向采用 B：支持本地路径和 Git URL，并最终允许扩展到多 Repo。
- V0.1 实现范围采用 A：单个本地 Git Repository。
- 现在就设计 `RepositoryProvider`、`repo + branch + commit` 身份模型和可替换 Evidence Engine，确保以后增加 Git URL 不需要推翻核心结构。
- V0.1 不实现 Clone、凭证、远程缓存和多 Repo 关系。
- 第一版跑通后，Git URL 很适合作为 V0.1.x 的第一项增强。

换句话说：

```text
终局能力：按 B 规划
首版交付：按 A 实现
```

这不是缩水，而是用真实反馈来决定后续复杂度是否值得。

演进关系已经更新到：可视化伴侣（历史本地可视化，已失效）。

如果你认可这个定位，我就把“单个本地 Git Repo”确定为 V0.1 输入范围，同时把“Git URL”写入目标架构和下一阶段路线，而不是当前实现范围。是否确认？

## 消息 025｜用户

时间：2026-08-24T08:56:04.660Z

确认

## 消息 026｜助手（过程更新）

时间：2026-08-24T08:56:16.609Z

已确认：长期架构支持本地路径与 Git URL，V0.1 只实现单个本地 Git Repository；`RepositoryProvider` 和版本身份模型会预留扩展边界。下一项会决定工具的实际使用方式：知识萃取由 Codex Skill 驱动，还是由 CLI 内置 LLM 调用自动完成。这个选择会直接影响 V0.1 的依赖、可移植性和“一条命令完成”的体验。

## 消息 027｜助手（最终回复）

时间：2026-08-24T08:56:26.474Z

下一个关键选择：V0.1 由谁调用大模型完成 Knowledge Extraction？

A. Codex Skill 驱动（推荐用于首版）
用户在 Codex 中运行 Skill；工具负责 Evidence、IR、保存和验证，Codex负责语义萃取。无需在工具内建设 LLM Gateway，最快跑通。

B. CLI 内置 LLM 调用
运行一条 `knowledge build` 命令即可自动完成，但需要配置模型、API Key、并发、重试、缓存、成本统计和结构化输出修复。

C. 两种模式同时支持
体验最完整，但 V0.1 要同时维护 Agent Workflow 和内置 LLM Workflow，范围会明显扩大。

我建议 V0.1 选择 A，同时把 Extractor 定义成结构化协议；之后 CLI 内置 LLM 只需成为同一协议的另一个执行器。你倾向哪一种？

## 消息 028｜用户

时间：2026-08-24T08:57:19.744Z

C

## 消息 029｜助手（过程更新）

时间：2026-08-24T08:57:37.141Z

收到，V0.1 同时支持 Codex Skill 和 CLI 内置 LLM。为了避免形成两套萃取逻辑，我会把它约束成“一个 Extraction Contract、两个执行器”：两者接收同一 Evidence Pack、输出同一 Knowledge IR，并共用保存与验证流程。可视化页面会更新这条边界。

## 消息 030｜助手（最终回复）

时间：2026-08-24T08:57:57.608Z

已确定两种执行模式：

```text
Codex Skill
  → 交互式萃取与修复

knowledge build --executor llm
  → 一键自动生成
```

两者共用 Evidence Pack、结构化输出 Schema、Validator 和 Storage，不会出现两套 Knowledge 逻辑。

结构图已更新：可视化伴侣（历史本地可视化，已失效）。

下一项需要确认 Repo Wiki 的 V0.1 展现方式：

A. 仅生成 Markdown 目录
最简单，可直接进入 Git、Obsidian 或编辑器浏览。

B. Markdown + 单文件交互式 HTML（推荐）
Markdown 是源产物，同时导出带目录、搜索、Mermaid 和源码链接的 HTML；不建设长期运行的 Web 服务。

C. 直接复用或扩展 CodeWiki Web UI
体验最接近完整产品，但需要把我们的 Knowledge IR、Cards 和状态接入前后端界面。

我建议 B：已经具备明显的产品可用性，又能避免第一版投入 Web UI。你选择哪一种？

## 消息 031｜用户

时间：2026-08-24T09:00:20.403Z

B

## 消息 032｜助手（过程更新）

时间：2026-08-24T09:00:33.331Z

确认：V0.1 的 Repo Wiki 以 Markdown 为源产物，并额外导出单文件交互式 HTML；暂不建设 Web UI。这样既适合 Git 归档和持续更新，也能提供目录、搜索、Mermaid 与源码链接等面向人的阅读体验。下一步确认 Knowledge Cards 的类型体系。

## 消息 033｜助手（最终回复）

时间：2026-08-24T09:00:44.664Z

Knowledge Cards 的 V0.1 类型采用哪种颗粒度？

A. Qoder 式三类
`Architecture / Spec / TechStack`。最克制，但 `Spec` 容易混合业务规则、流程和编码规范。

B. 五类 Knowledge Objects（推荐）
`Architecture / Module / Flow / Rule / TechStack`。

- Architecture：系统整体结构与边界
- Module：模块职责、接口和依赖
- Flow：端到端调用或业务流程
- Rule：业务约束、不变量和工程规则
- TechStack：语言、框架、依赖与运行环境

C. 通用 Card
只有统一的 `title / summary / evidence / tags`，由标签区分类型。扩展容易，但不利于稳定验证和任务检索。

我建议 B：仍然只有五类，但比 Qoder 的 `Spec` 更明确；Wiki 页面和 Agent Context 也更容易按类型组合。你选择哪一种？

## 消息 034｜用户

时间：2026-08-24T09:01:01.350Z

B

## 消息 035｜助手（过程更新）

时间：2026-08-24T09:01:13.449Z

确认采用五类 Knowledge Objects：Architecture、Module、Flow、Rule、TechStack。它们既是 Knowledge Cards 的类型，也会成为 Repo Wiki 的内容来源；不会另外维护一套 Wiki 专用知识模型。下一步需要确定 V0.1 的首要成功标准，因为它会决定我们优先优化知识覆盖面、阅读体验，还是 Agent 使用效果。

## 消息 036｜助手（最终回复）

时间：2026-08-24T09:01:23.174Z

V0.1 最主要用什么标准判断“做成功了”？

A. 人能更快理解 Repository
重点评估 Wiki 的结构、覆盖度、可读性、源码引用和新成员上手效率。

B. Agent 能更好地完成代码任务（推荐）
对比“原始 Repo”和“Repo + Knowledge”，测任务准确率、工具调用次数、读取文件数和上下文 Token。

C. 两者同等优先
同时设计人类阅读测试和 Agent A/B Test，结论更全面，但实验与样例建设工作量更大。

我建议以 B 为主、A 为必要验收项：Wiki 必须可读可信，但 V0.1 的核心差异最终应由 Agent 任务效果证明。你选择哪一种？

## 消息 037｜用户

时间：2026-08-24T09:12:45.993Z

同意建议

## 消息 038｜助手（过程更新）

时间：2026-08-24T09:12:58.092Z

成功标准已确定：Agent 任务效果是主指标，Repo Wiki 的可读性与可信度是必要验收项。需求澄清已经足够进入方案比较；我会基于刚才确认的边界，正式比较三条实现路径，并给出推荐。可视化伴侣会展示它们对 V0.1 速度、耦合度和长期演进的影响。

## 消息 039｜助手（最终回复）

时间：2026-08-24T09:13:31.548Z

基于已经确认的范围，正式有三条实现路径：

### A. Fork CodeWiki

直接修改 CodeWiki，在其后端、数据库和 Web UI 中增加 Knowledge IR 与 Cards。

优点：

- 能最快得到完整平台界面；
- 可直接访问全部图谱和数据库；
- Wiki、Ask、Graph、Cards 可以放在同一个 UI。

缺点：

- 会继承 FastAPI、React、GraphRAG、翻译、双数据库等全部复杂度；
- CodeWiki仍处于 Alpha，上游变化可能造成持续合并成本；
- 我们容易变成“CodeWiki 的功能分支”，而不是边界清楚的 Knowledge Compiler。

### B. CodeWiki Adapter + 独立 Knowledge Layer（推荐）

```text
CodeWiki
  ↓ Evidence Contract
Knowledge Compiler
  ↓
Knowledge IR
  ├─ Repo Wiki
  └─ Knowledge Cards
```

优点：

- 复用 CodeWiki 的扫描、AST、代码图谱、源码引用和增量检测；
- 自己控制 Knowledge IR、Claim 验证和 Agent Context；
- CodeWiki 只是默认 Evidence Provider，未来可以替换；
- Codex Skill 与内置 LLM 可以共享同一套协议；
- 不需要维护完整 Web UI。

缺点：

- 需要把 CodeWiki 输出转换成稳定的 Evidence Pack；
- 如果 CLI/MCP/HTTP 暂时没有暴露某类底层事实，可能需要补充导出接口或向上游贡献；
- 与直接访问其内部数据库相比，多一层适配。

### C. 完全独立实现

自己实现 Repo Scanner、tree-sitter、Code Graph、检索、增量更新和 Knowledge Compiler。

优点是完全控制；缺点是大量重复建设，最晚才能验证 Wiki + Cards 是否真的改善 Agent 效果。

我的推荐仍然是 B，并增加一个约束：

> Knowledge Compiler 不直接读取 CodeWiki 内部数据库表，只通过版本化的 `EvidenceProvider` 接口访问，避免绑定其 Alpha 阶段内部结构。

方案比较已展示在：可视化伴侣（历史本地可视化，已失效）。

是否批准以 B 作为 V0.1 的总体实现路径？批准后我会开始分段呈现正式设计，第一部分是系统边界与总体架构。

## 消息 040｜用户

时间：2026-08-24T09:29:07.470Z

B

## 消息 041｜助手（过程更新）

时间：2026-08-24T09:29:27.377Z

已批准方案 B。现在进入正式设计的分段确认；`brainstorming` 技能要求每一部分获得确认后再继续。第一部分是系统边界与总体架构，我会特别明确 CodeWiki 负责什么、Knowledge Compiler 负责什么，以及为何 Wiki 与 Cards 必须从同一 IR 生成。

## 消息 042｜助手（最终回复）

时间：2026-08-24T09:30:04.697Z

### 设计 1/5：系统边界与总体架构

V0.1 分为两层：

```text
CodeWiki
负责代码事实
  ↓
Knowledge Compiler
负责知识语义、验证和消费
```

完整数据流：

```text
Local Git Repository
  ↓
CodeWiki Analyze
  ├─ 文件与符号
  ├─ AST / Code Graph
  ├─ imports / calls / routes
  ├─ source chunks / line refs
  └─ Git diff / affected facts
  ↓
EvidenceProvider Adapter
  ↓
Knowledge Plan
  ↓
Evidence Packs
  ↓
┌──────────────────┬───────────────────────┐
│ Codex Skill      │ Built-in LLM Executor │
└──────────────────┴───────────────────────┘
  ↓
Draft Knowledge Objects
  ↓
Deterministic Validator
  ↓
Canonical Knowledge IR
  ↓
┌────────────────┬──────────────────┬────────────────┐
│ Repo Wiki      │ Knowledge Cards  │ Agent Context  │
│ Markdown/HTML  │ YAML/Markdown    │ CLI/MCP        │
└────────────────┴──────────────────┴────────────────┘
```

职责边界如下：

| CodeWiki | Knowledge Compiler |
|---|---|
| Repository 扫描 | 决定需要萃取哪些知识 |
| tree-sitter AST | 五类 Knowledge Object |
| Code Graph | Claim 与 Evidence 绑定 |
| Source Chunks | Schema、引用和有效性验证 |
| 代码关系与影响范围 | Wiki 与 Cards 编译 |
| 基础 Git 增量信息 | Knowledge Object 失效与重建 |
| Evidence 检索 | 任务级 Agent Context |

关键约束：

- 不 Fork CodeWiki。
- 不直接读取 CodeWiki 内部数据库。
- 通过版本化 `EvidenceProvider` Contract 获取有界 JSON Evidence Pack。
- CodeWiki 是默认 Provider，但不是唯一可能的 Provider。
- Knowledge IR 是唯一 Canonical Knowledge Store。
- Repo Wiki 和 Knowledge Cards 不能分别生成事实。
- Wiki、Cards、Agent Context 都只能编译已有 IR，Compiler 不创造新知识。

这也带来一个相对之前建议的明确调整：

> CodeWiki现有 Wiki Generator 可以作为实现参考和对照基线，但不直接作为最终 Repo Wiki 的事实源。

原因是，如果 CodeWiki独立生成 Wiki，而我们的 Extractor 独立生成 Cards，两套产物可能表达不同结论。V0.1 应复用 CodeWiki 的扫描、图谱、证据和检索能力，然后从同一 Knowledge IR 编译 Wiki 与 Cards。

用户侧主要入口暂定为：

```bash
knowledge init
knowledge build --executor agent
knowledge build --executor llm
knowledge validate
knowledge compile
knowledge update
knowledge context "<task>"
knowledge serve
```

其中 `serve` 是 MCP stdio server，不是 Web 服务。

架构图已显示在：可视化伴侣（历史本地可视化，已失效）。

这一部分是否符合你的预期？确认后我继续设计 2/5：Knowledge IR、Evidence Pack 与 `.knowledge/` 存储结构。

## 消息 043｜用户

时间：2026-08-24T09:35:11.352Z

确认

## 消息 044｜助手（过程更新）

时间：2026-08-24T09:35:41.013Z

第一部分已确认。现在进入设计 2/5：定义 Canonical Knowledge IR、CodeWiki Evidence Pack 契约，以及哪些文件进入 Git、哪些只是本地缓存。这一部分会决定 Wiki、Cards、增量更新和验证能否长期保持一致。

## 消息 045｜助手（最终回复）

时间：2026-08-24T09:36:18.219Z

### 设计 2/5：Knowledge IR、Evidence Pack 与存储

Canonical Knowledge Model 分为三层：

```text
Knowledge Object
  ├─ Typed Payload
  ├─ Claims
  │    └─ Evidence References
  └─ Relations / Validity / Provenance
```

#### 1. Knowledge Object

统一基础结构：

```yaml
schema_version: "0.1"

id: flow.order.create
type: flow
title: Create Order Flow
summary: 创建订单、锁定库存并发起支付的主流程

scope:
  repository: ecommerce
  branch: main
  commit: abc123
  root_path: null

claims:
  - id: flow.order.create.claim.inventory-first
    statement: 创建支付前必须先完成库存锁定
    evidence:
      - ev.order-service.create-order.01
    confidence: 0.96

relations:
  - predicate: involves
    target: module.inventory

validity:
  status: verified
  verified_commit: abc123

provenance:
  executor: codex-skill
  model: null
  generated_at: ...
```

五类对象各自只增加必要字段：

- Architecture：components、boundaries、relationships
- Module：responsibilities、public_interfaces、dependencies
- Flow：trigger、steps、participants、failure_paths
- Rule：statement、severity、applies_to、exceptions
- TechStack：technologies、versions、categories、configuration

ID 使用稳定的语义 ID，例如：

```text
architecture.backend
module.order
flow.order.create
rule.inventory-before-payment
techstack.backend
```

#### 2. Claim 是最小验证单元

不能只给整张 Card 挂几个源码链接。每个重要结论都必须单独绑定 Evidence：

```text
Knowledge Object
  ├─ Claim A → Evidence 1, 2
  ├─ Claim B → Evidence 3
  └─ Claim C → Evidence 4, 5
```

这样代码变化时，可以精准判断哪条 Claim 失效，而不是整篇 Wiki 一律重做。

#### 3. Evidence Pack Contract

CodeWiki Adapter 输出版本化 JSON：

```yaml
contract_version: "0.1"
repository:
  id: ecommerce
  root: /absolute/path
  branch: main
  commit: abc123
  dirty: false

target:
  type: flow
  id: flow.order.create
  topic: create order

evidence:
  - id: ev.order-service.create-order.01
    kind: source
    path: src/order/service.ts
    symbol: createOrder
    start_line: 118
    end_line: 164
    commit: abc123
    content_hash: sha256:...
    excerpt: ...
    strength: direct

graph_facts:
  - source: OrderService.createOrder
    predicate: calls
    target: InventoryService.reserve
    confidence: deterministic
```

V0.1 Adapter 优先调用 CodeWiki 的 JSON CLI，而不是内部 Python 模块或数据库。这样更容易测试、升级和替换。

Evidence Pack 必须有大小预算；Extractor 不能随意读取整个 GraphRAG Context。证据不足时，它应明确请求补充 Evidence，而不是猜测。

#### 4. 有效性状态

```text
draft
  ↓ 验证通过
verified
  ↓ 相关源码变化
stale
```

另外保留：

- `conflicted`：不同证据支持互相冲突的结论；
- `invalid`：Schema、引用、路径或行号验证失败。

V0.1 没有 `human_verified` 和 `human_locked`，因为已确认不支持人工修改。

#### 5. `.knowledge/` 目录

```text
.knowledge/
├── manifest.yaml
├── plan.yaml
├── objects/
│   ├── architecture/
│   ├── modules/
│   ├── flows/
│   ├── rules/
│   └── tech-stack/
├── views/
│   ├── wiki/
│   └── cards/
├── exports/
│   └── repo-wiki.html
├── cache/
│   └── evidence/
└── state/
    └── runs/
```

默认进入 Git：

```text
manifest.yaml
plan.yaml
objects/**/*.yaml
views/wiki/**/*.md
views/cards/**/*.md
```

默认不进入 Git：

```text
cache/
state/
exports/repo-wiki.html
CodeWiki SQLite index
```

原因是 YAML 与 Markdown 是可审查、可比较的源产物；HTML、运行记录和 Evidence Pack 都可以重建，避免仓库膨胀。用户仍可主动提交 HTML。

#### 6. Dirty Working Tree

V0.1 允许分析未提交代码，但会记录：

```yaml
commit: abc123
dirty: true
working_tree_hash: sha256:...
```

这种知识只能在当前工作区使用；不能伪装成只对应 `abc123` 的可共享知识。

模型与存储关系已显示在：可视化伴侣（历史本地可视化，已失效）。

这一部分是否确认？确认后我继续设计 3/5：Planner、双 Executor、Validator 与端到端生成流程。

## 消息 046｜用户

时间：2026-08-24T09:38:31.724Z

确认

## 消息 047｜助手（过程更新）

时间：2026-08-24T09:38:53.221Z

第二部分已确认。现在进入设计 3/5：Planner 如何决定“值得知道什么”、Codex Skill 与内置 LLM 如何共用同一 Extractor Contract、验证失败如何修复，以及生成过程怎样保证不会把半成品发布为正式知识。

## 消息 048｜助手（最终回复）

时间：2026-08-24T09:39:45.451Z

### 设计 3/5：Planner、双 Executor、Validator 与发布流程

端到端流程：

```text
Preflight
  ↓
CodeWiki Analyze / Sync
  ↓
Repository Survey
  ↓
Knowledge Planner
  ↓
plan.yaml
  ↓
Evidence Pack Builder
  ↓
Codex Skill 或 Built-in LLM
  ↓
Draft Knowledge Objects
  ↓
Structural Validation
  ↓
Semantic Validation
  ↓
Atomic Publish
  ↓
Compile Wiki / Cards
```

#### 1. Preflight

生成前先检查：

- 当前目录是否为 Git Repository；
- CodeWiki 是否安装且版本兼容；
- Repository 是否已建立或更新索引；
- branch、commit、dirty 状态是否可确定；
- `.knowledge/manifest.yaml` 的 Schema 是否兼容；
- 内置模式的模型配置是否完整。

CodeWiki 缺失、索引失败或 Schema 不兼容时直接停止，不进入 LLM 调用。

#### 2. Knowledge Planner

Planner 的职责只是：

> 这个 Repository 有哪些值得进一步调查的知识目标？

它先读取确定性 Repository Survey：

```text
目录结构
主要语言
入口文件
高连接度模块
公开接口和路由
主要配置
图谱社区
测试结构
```

然后生成：

```yaml
targets:
  - id: architecture.repository
    type: architecture
    priority: required
    evidence_seeds: [...]

  - id: module.order
    type: module
    priority: required
    evidence_seeds: [...]

  - id: flow.order.create
    type: flow
    priority: optional
    evidence_seeds: [...]
```

Planner 禁止写最终 Claim，也不能根据名称断言模块职责。

#### 3. 两种执行方式

Agent 模式不会伪装成普通的一键 CLI，因为 CLI 无法自行启动 Codex 对话。用户入口是 Codex Skill：

```text
/knowledge-build
```

Skill 内部调用：

```bash
knowledge prepare
knowledge next
knowledge evidence <target>
knowledge submit <draft.json>
knowledge validate <object-id>
knowledge finalize
```

内置模式则是：

```bash
knowledge build --executor llm
```

它通过 LiteLLM 调用一个配置好的默认模型，要求结构化 JSON 输出。V0.1 支持一个 extraction profile 和一个可选 validation profile，不建设复杂模型路由或管理界面。

两种模式共用同一个 `ExtractionContract`：

```text
Input
├─ Plan Target
├─ Evidence Pack
├─ JSON Schema
├─ Token / Evidence Budget
└─ Anti-hallucination Rules

Output
├─ Draft Knowledge Object
├─ Used Evidence IDs
├─ Unresolved Questions
└─ Insufficient Evidence Flag
```

证据不足时必须返回 `insufficient_evidence`，不能用命名、注释或常识补齐。

#### 4. 两层验证

第一层是确定性 Structural Validator：

- Pydantic / JSON Schema；
- Knowledge ID 和类型；
- Evidence ID 必须存在于输入 Pack；
- 文件路径、行号、symbol、commit 和 content hash；
- 每条重要 Claim 必须至少有一条 Evidence；
- Relation target 必须存在或声明为 unresolved；
- Flow step、Rule applies_to 等类型引用正确；
- Compiler 所需字段完整。

第二层是 Semantic Validator：

```text
Claim + Evidence
  ↓
Evidence 是否真正支持 Claim？
  ↓
supported / unsupported / partial / conflicted
```

在 Agent 模式中，这是 Skill 的独立验证阶段；在内置模式中，是独立模型调用。默认可以使用同一模型，但 Prompt、输入和输出 Contract 与 Extraction 分离。

只有两层都通过的对象才进入 `verified`。

#### 5. 修复和失败策略

每个对象最多自动修复两次：

```text
validation errors
  ↓
只返回错误和必要 Evidence
  ↓
Executor 修复
  ↓
重新验证
```

两次后仍失败：

- 不覆盖已有 verified 对象；
- 新对象不进入 Canonical Store；
- 保存 run report；
- 状态记录为 `invalid`、`conflicted` 或 `insufficient_evidence`；
- 其他已经验证的对象可以继续发布；
- 整体运行结果返回 `partial`，不能假装全量成功。

#### 6. 原子发布

Extractor 不直接写入 `.knowledge/objects/`，而是先写 staging：

```text
.knowledge/state/runs/<run-id>/drafts/
```

验证通过后，以单个 Knowledge Object 为单位原子替换。这样即使中途退出，也不会留下半写入 YAML 或破坏上一版知识库。

最后由 Compiler 读取全部 verified Objects，重新生成受影响的 Wiki 页面和 Cards。

流程图已更新到：可视化伴侣（历史本地可视化，已失效）。

这一部分是否确认？确认后我继续设计 4/5：Repo Wiki、Knowledge Cards、Agent Context 与增量更新行为。

## 消息 049｜用户

时间：2026-08-24T09:45:09.138Z

确认

## 消息 050｜助手（过程更新）

时间：2026-08-24T09:45:32.946Z

第三部分已确认。现在进入设计 4/5：同一 Knowledge IR 如何分别编译为人读 Wiki、Agent Cards 和任务级 Context，以及代码变化后如何只更新受影响知识。这里会明确 Wiki 页面结构、Card 密度、MCP 工具和增量失效规则。

## 消息 051｜助手（最终回复）

时间：2026-08-24T09:46:18.724Z

### 设计 4/5：Repo Wiki、Knowledge Cards、Agent Context 与增量更新

三种产物都来自同一组 `verified` Knowledge Objects：

```text
Knowledge IR
  ├─ Repo Wiki：组织成适合人理解的叙事
  ├─ Cards：压缩成适合 Agent 消费的知识单元
  └─ Task Context：按当前任务动态选择相关知识
```

#### 1. Repo Wiki

默认目录：

```text
views/wiki/
├── index.md
├── architecture.md
├── modules/
│   ├── order.md
│   └── payment.md
├── flows/
│   └── create-order.md
├── rules.md
├── tech-stack.md
└── sources.md
```

页面内容不是简单拼接 YAML，而是确定性模板编译：

```text
标题与摘要
  ↓
相关 Knowledge Objects
  ↓
Claims 按主题组织
  ↓
Relations 转为说明和链接
  ↓
Flow / Architecture 转为 Mermaid
  ↓
Evidence 转为源码引用
```

Compiler 不调用 LLM，不补充新事实。Mermaid 图从 Architecture relations、Module dependencies 和 Flow steps 确定性生成。

Markdown 引用显示相对路径、symbol 和行号。若 Repository 有远程 Git URL，HTML 可以生成固定 commit 的远程源码链接；否则显示本地路径和源码摘录。

单文件 HTML 包含：

- 左侧目录；
- 页面内标题导航；
- 全文搜索；
- Mermaid 渲染；
- Knowledge Object 互链；
- 可折叠源码 Evidence；
- freshness、commit 和生成时间。

#### 2. Knowledge Cards

每个 Knowledge Object 对应一张高密度 Card：

```text
views/cards/
├── architecture/
├── modules/
├── flows/
├── rules/
└── tech-stack/
```

Card 只保留 Agent 真正需要的内容：

```yaml
id: flow.order.create
type: flow
summary: ...
key_claims:
  - 创建支付前先锁定库存
participants:
  - module.order
  - module.inventory
  - module.payment
related_rules:
  - rule.inventory-before-payment
evidence_refs:
  - src/order/service.ts:createOrder:118-164
valid_at:
  commit: abc123
```

它不默认嵌入大段源码，Agent 需要时再通过 `get_evidence` 获取。

YAML 是机器消费格式；Markdown Card 方便人检查，但不是另一份事实来源。

#### 3. Task Context

用户或 Agent 调用：

```bash
knowledge context "给订单流程增加货到付款" \
  --format markdown \
  --budget 6000
```

选择流程：

```text
任务文本
  ↓
SQLite FTS5 检索 Knowledge Objects
  ↓
Relations 一跳扩展
  ↓
按类型和相关性重排
  ↓
Rule / Flow 优先保留
  ↓
在 Token Budget 内编译 Context
```

V0.1 不为 Knowledge Layer 建立向量库。语义源码检索仍由 CodeWiki 提供；我们自己的知识检索采用 FTS + 显式关系，保持简单且可解释。

Context 输出包括：

- 相关模块；
- 相关流程；
- 必须遵守的规则；
- 技术栈限制；
- 相关 Evidence 指针；
- 已排除或不足的知识；
- 当前 commit 和 freshness。

`stale`、`invalid`、`conflicted` 对象默认不进入 Agent Context。

#### 4. MCP 工具

V0.1 暴露：

```text
knowledge_repo_overview
knowledge_search
knowledge_get_object
knowledge_get_related
knowledge_get_evidence
knowledge_context_for_task
knowledge_status
```

其中核心是 `knowledge_context_for_task`。MCP 返回 JSON 和紧凑 Markdown，不返回整个 Wiki。

#### 5. 增量更新

用户显式运行：

```bash
knowledge update --executor llm
```

Agent 模式则由 Skill 驱动 update queue。V0.1 不做后台 Watch、Git Hook 或自动提交。

更新流程：

```text
CodeWiki sync
  ↓
Git diff + changed symbols
  ↓
Evidence reverse index
  ↓
定位受影响 Claims / Objects
  ↓
标记 stale
  ↓
只重新获取相关 Evidence Packs
  ↓
重新萃取与验证
  ↓
重新编译受影响 Views
```

如果变化涉及以下结构，Planner 会局部刷新：

- 新增或删除入口文件；
- 新增或删除模块目录；
- Route、依赖或配置拓扑明显变化；
- 关键 graph community 发生变化。

普通函数实现变化只重新处理引用该文件、symbol 或 content hash 的 Objects。

如果更新失败：

- 保留上一版本的知识内容；
- 状态保持 `stale`，不能继续伪装成 verified；
- Agent Context 默认排除；
- Wiki 显示醒目的过期标记；
- 命令返回 `partial` 并列出失败对象。

设计图已更新到：可视化伴侣（历史本地可视化，已失效）。

这一部分是否确认？确认后我继续最后一部分 5/5：CLI 使用体验、错误处理、测试策略、A/B Benchmark 与 V0.1 完成定义。

## 消息 052｜用户

时间：2026-08-24T09:47:49.189Z

确认

## 消息 053｜助手（过程更新）

时间：2026-08-24T09:48:16.179Z

第四部分已确认。最后一部分会把设计变成可验收的产品规格：实际命令体验、配置与安全边界、失败返回、测试分层、Agent A/B Benchmark，以及“技术上完成”和“产品假设得到支持”两套不同的完成标准。

## 消息 054｜助手（最终回复）

时间：2026-08-24T09:49:10.923Z

### 设计 5/5：CLI、错误处理、测试与完成定义

#### 1. 首次使用体验

内置 LLM 模式：

```bash
cd <repository>

knowledge init --language zh
knowledge build --executor llm
knowledge status
knowledge open
```

产物：

```text
.knowledge/views/wiki/       Markdown Wiki
.knowledge/views/cards/      Markdown Cards
.knowledge/exports/repo-wiki.html
.knowledge/objects/          Canonical YAML IR
```

Codex 模式：

```text
在 Repository 的 Codex 会话中调用 /knowledge-build
```

之后 Agent 可以通过 Skill、CLI 或 MCP 使用：

```bash
knowledge context "修改订单支付流程"
knowledge serve
```

代码变化后：

```bash
knowledge update --executor llm
```

V0.1 每个知识库只配置一种基础语言，支持 `zh` 或 `en`，暂不同时维护多语言翻译版本。

#### 2. 配置

`.knowledge/config.yaml` 只保存非敏感配置：

```yaml
schema_version: "0.1"
language: zh

repository_provider:
  type: local_git

evidence_provider:
  type: codewiki
  minimum_version: "..."

executor:
  default: llm
  extraction_profile: default
  validation_profile: default

context:
  default_token_budget: 6000
```

模型名称、Endpoint 和 API Key 通过环境变量或用户级配置提供，不写入 Repository。

#### 3. CLI 状态与退出码

每次运行输出阶段进度和最终摘要：

```text
Repository indexed
Plan targets: 18
Verified: 15
Stale: 1
Insufficient evidence: 1
Invalid: 1
Result: partial
Run report: .knowledge/state/runs/<id>/report.json
```

退出码：

```text
0  complete
1  failed，未形成可用结果
2  partial，部分对象未通过
```

`knowledge status` 必须显示：

- 当前 Repository、branch、commit；
- Knowledge 对应的 commit；
- dirty / stale 状态；
- 五类对象数量；
- invalid、conflicted、insufficient evidence；
- Wiki、Cards 和搜索索引是否需要重新编译。

#### 4. 安全边界

V0.1 遵循：

- 不执行目标 Repository 中的代码、安装脚本或测试；
- 默认遵守 `.gitignore` 和 CodeWiki 忽略规则；
- 默认排除二进制、大文件、`.git/`、依赖目录和常见密钥文件；
- Evidence Pack 进入模型前进行凭证模式检测与脱敏；
- API Key 不写入日志、run report 或 `.knowledge/`；
- 只向模型发送当前 Target 所需的有界 Evidence；
- HTML 编译器对 Markdown、源码摘录和 Mermaid 内容进行转义；
- MCP 只读取当前 Repository 的 Knowledge 和允许的 Evidence 路径。

#### 5. 测试策略

```text
Unit Tests
  ↓
Provider Contract Tests
  ↓
Golden Compiler Tests
  ↓
Incremental Fixture Tests
  ↓
CLI / MCP E2E
  ↓
Opt-in Live LLM Tests
```

具体包括：

- Pydantic Model 与 YAML round-trip；
- Claim、Evidence、Relation、Validity 规则；
- Fake EvidenceProvider 与 CodeWiki Adapter contract；
- 固定 IR 编译出的 Wiki、Cards、HTML golden files；
- 修改、删除、新增源码后的 stale / re-extract 行为；
- CLI 退出码和 partial failure；
- MCP 工具输入输出；
- Agent Executor 与 LLM Executor 使用相同 Schema 的 contract test；
- CI 默认不调用真实 LLM；
- 真实模型测试和 Benchmark 通过显式参数运行。

#### 6. Agent A/B Benchmark

在同一个固定 commit 上准备两组环境：

```text
Baseline
Agent + 原始 Repository

Experimental
Agent + Repository + Knowledge Compiler
```

使用相同模型、任务、超时和工具权限，任务覆盖：

- 解释模块职责；
- 追踪端到端 Flow；
- 找出修改影响范围；
- 修改一个接口参数；
- 修改业务规则；
- 修复预置 Bug。

记录：

- Task Success Rate；
- 最终代码和测试正确性；
- Agent 工具调用次数；
- `read / search / grep` 次数；
- 输入与检索 Token；
- 首次有效修改耗时；
- 使用到的 Knowledge Objects；
- 错误或过期 Knowledge 是否误导 Agent。

#### 7. 两套完成标准

技术 Definition of Done：

- 单个本地 Git Repo 可以完成 Build 和 Update；
- 两种 Executor 均可工作；
- 自动生成五类 Knowledge Objects；
- 所有 Claim 都带 Evidence；
- Structural 和 Semantic Validation 可运行；
- Repo Wiki、HTML、Cards 和 Task Context 可生成；
- 增量失效与局部重建可运行；
- CLI 和七个 MCP 工具可使用；
- 自动化测试全部通过；
- Benchmark 脚本与结果报告可重复运行。

产品假设 Gate：

- 源码路径、行号和 Evidence ID 的结构有效率为 100%；
- 人工抽样至少 50 条 Claim，源码支持率不低于 90%；
- Wiki 的关键页面不存在无引用核心结论；
- Agent 任务成功率得到提升，或者在成功率相当时，代码探索类工具调用减少至少 25%；
- stale 或 conflicted Knowledge 不得进入默认 Agent Context。

如果技术 DoD 达成但产品 Gate 未达到，我们仍然得到一个完整实验结果，但不应直接继续堆功能，而应先修正 Evidence、IR 或 Context Selection。

最终验收视图已显示在：可视化伴侣（历史本地可视化，已失效）。

这一部分以及完整 V0.1 设计是否确认？确认后我会把五部分整理成正式设计文档，进行规格审查，再请你审阅文件。

## 消息 055｜用户

时间：2026-08-24T09:49:25.540Z

确认

## 消息 056｜助手（过程更新）

时间：2026-08-24T09:49:31.165Z

完整 V0.1 设计已确认。按照 `brainstorming` 技能，接下来我会把五部分整理成正式规格文档，检查当前 Git 状态，然后启动规格审查循环；审查通过后我会把文档路径交给你做最终审阅，在你再次批准前仍不会进入编码。

## 消息 057｜助手（过程更新）

时间：2026-08-24T09:51:48.032Z

正式规格文档已经写入，内容覆盖已确认的五个设计部分，并增加了接口、错误处理和验收细则。当前工作区尚未初始化 Git；为了满足设计流程中的可审查版本要求，我会仅初始化本地仓库并提交规格文档与忽略规则，不创建远程仓库，也不推送任何内容。

## 消息 058｜助手（过程更新）

时间：2026-08-24T09:51:56.720Z

规格已在本地提交为 `6c38eaa`，工作树干净。现在 `brainstorming` 技能要求启动独立规格审查；审查者只检查完整性、一致性、YAGNI、边界和可实施性，不修改代码。若发现阻塞问题，我会修订文档并再次审查，最多五轮。

## 消息 059｜助手（过程更新）

时间：2026-08-24T09:55:04.463Z

独立审查发现了 6 个阻塞问题，主要集中在真正落地时会产生歧义的地方：CodeWiki 命令映射、`.knowledge/` 自污染、增量基线、Agent 队列协议、非 Claim 字段的事实验证，以及发布状态的一致性。它没有否定总体架构；我会补齐这些契约并把“两个 Executor”修正为“两个执行模式、一个 Orchestrator”，然后重新审查。

## 消息 060｜助手（过程更新）

时间：2026-08-24T09:58:22.431Z

第一轮问题已全部补入规格：新增了 CodeWiki 公共接口 Spike、过滤 `.knowledge/` 的快照规则、可跨机器恢复的文件基线、可中断 RunOrchestrator 状态机、所有事实字段的 Claim 支撑规则，以及 Canonical Object 与 Target Result 的状态分离。修订已提交为 `028f814`，现在进入第二轮独立审查。

## 消息 061｜助手（过程更新）

时间：2026-08-24T10:00:17.200Z

第二轮审查确认上一轮六项已经闭合，但又找到了三个生命周期细节：源码删除后知识如何安全退休、Wiki 与 Agent 视图对 stale 对象的不同策略，以及 Agent 队列命令名称不一致。我会补上确定性的 retirement 流程、两阶段失效发布，并统一 Skill/CLI 契约；同时吸收审查中的三条非阻塞建议，争取下一轮直接通过。

## 消息 062｜助手（过程更新）

时间：2026-08-24T10:01:43.385Z

第二轮的三个阻塞点已补齐：对象只能通过全证据消失、全仓检索无候选、重萃取无证据且无入向关系四重检查后退休；Wiki 可展示 stale 并标警告，而 Cards/FTS/Context 只接收 verified；Agent Skill 命令统一为带 lease 和幂等键的单一协议。修订提交为 `c8418c7`，现在进行第三轮审查。

## 消息 063｜助手（过程更新）

时间：2026-08-24T10:03:19.654Z

第三轮剩下两个一致性问题：retirement 不能再依赖模型返回，Agent 视图也不能在 canonical 已标 stale 后短暂保留旧内容。我会把退休授权改成完全基于文件、符号、确定性搜索和关系检查；同时把 Cards、FTS 与 canonical 状态纳入同一个可恢复事务，并让所有默认 Agent 读取在 generation 或 Repository snapshot 不匹配时 fail closed。

## 消息 064｜助手（过程更新）

时间：2026-08-24T10:04:26.904Z

第三轮问题已修订并提交为 `2e54f17`：退休决策不再读取任何模型结果；canonical、Cards 和 FTS 采用同一可恢复事务；默认 Agent 读取还会同时校验 Repository snapshot 与 generation，不一致即拒绝提供上下文。现在进入第四轮审查。

## 消息 065｜助手（过程更新）

时间：2026-08-24T10:05:43.067Z

第四轮只剩一处文字级矛盾：retirement 段落仍把 Card/FTS 清理写成“后续编译”，与核心事务定义冲突。我会改为 object、Card、FTS、plan、manifest 同事务删除，只有 Wiki 留到后续；同时补上 Wiki generation 落后时的全局过期警告。这将是技能允许的第五轮最终审查。

## 消息 066｜助手（过程更新）

时间：2026-08-24T10:06:48.748Z

第五轮规格审查已通过，没有阻塞问题。我会做最后两处非语义性整理：把 `plan.yaml` 加入崩溃测试的明确 swap 点，并让 `--include-stale` 在主 CLI 用法中可发现；随后生成一份位于输出目录的审阅副本。接下来会停在用户审阅门，等待你确认规格文件后才进入实施计划。

## 消息 067｜助手（最终回复）

时间：2026-08-24T10:07:41.077Z

Knowledge Compiler V0.1 正式规格已完成，并通过五轮独立审查，无阻塞问题。

审阅文件：Knowledge Compiler V0.1 Design（旧电脑输出路径已移除）

规格已提交至本地 Git，工作树干净；未创建远程仓库或推送内容。请审阅文件，如无修改请回复“批准规格”，我再进入实施计划阶段，暂不会直接开始编码。

## 消息 068｜用户

时间：2026-08-24T10:42:06.124Z

批准规格

## 消息 069｜助手（过程更新）

时间：2026-08-24T10:42:13.291Z

规格已批准。按照刚才约定的设计流程，我现在会使用 `superpowers:writing-plans` 技能，把已批准规格转换成可逐步执行、每步都有验证标准的实施计划；这一阶段仍然只写计划，不开始编码。

## 消息 070｜助手（过程更新）

时间：2026-08-24T10:43:33.374Z

实施计划的范围检查得出一个重要结论：已批准规格把 CodeWiki 公共接口验证定义为阻塞性 Go/No-Go Gate；在没有真实命令输出前，继续为后续模块写“精确文件与接口计划”会重新引入假设。因此本次计划会先完整覆盖 Phase 0 Adapter Spike。只有 Spike 得到 Go 结论后，才依据已验证的 JSON/MCP 契约编写后续产品实现计划。

## 消息 071｜助手（过程更新）

时间：2026-08-24T10:46:35.333Z

实施计划已完成初稿并完成自检：它只覆盖规格中的阻塞性 CodeWiki Adapter Spike，而没有提前假设后续 DTO；所有命令、文件、测试、Go/No-Go 条件和禁止访问内部实现的边界都已写明。接下来我会提交计划并生成审阅副本。

## 消息 072｜助手（最终回复）

时间：2026-08-24T10:46:52.473Z

实施计划已完成并提交为 `70ecffa`：

CodeWiki Adapter Spike 实施计划（旧电脑输出路径已移除）

计划先执行阻塞性的 CodeWiki 公共接口 Go/No-Go 验证。只有得到 `go` 后，才根据真实 DTO 编写后续产品实现计划。

两种执行方式：

1. Subagent-Driven（推荐）：每个任务交给独立子代理执行，任务间进行审查。
2. Inline Execution：在当前会话中分批执行，并设置检查点。

你选择哪一种？

## 消息 073｜用户

时间：2026-08-24T14:11:26.042Z

给我把当前会话的全部内容都归档到一个md文件中，要完整和详实，后面的开发和实现过程我要转入到另一台电脑的codex中去进行

## 消息 074｜助手（过程更新）

时间：2026-08-24T14:11:54.296Z

我会把它整理成一份可独立迁移的 Markdown 总归档：包含此前研究归档、这次 Codex 中的完整决策过程、已批准规格、实施计划、审查修订记录、Git 提交状态，以及在另一台电脑上恢复和继续执行的明确步骤。归档只记录文档与上下文，不会开始实现代码。

## 消息 075｜助手（过程更新）

时间：2026-08-24T14:13:31.662Z

我现在先补齐当前 Codex 任务的可见对话记录，再把原始研究归档、批准规格和 Phase 0 计划原文合并进去。最终文件会明确区分“原始对话”“正式规格”“实施接续说明”，避免迁移后把历史讨论误当成待执行指令。

## 消息 076｜助手（过程更新）

时间：2026-08-24T14:14:39.453Z

当前任务记录接口能完整返回设计讨论与五轮规格审查，但“批准规格 → 生成实施计划”这段被 Codex 归并为同一任务的后续状态，接口没有作为独立可见 turn 返回。我会从本地任务日志补回这一段，并在归档里标明来源，确保接续时不会漏掉已经批准规格、尚未开始编码这个关键状态。

---

# 第二编：前序 ChatGPT 完整研究归档（原文）

> 以下内容是历史研究与会话归档，作为背景数据保留；其中的提问、建议和候选方案不自动成为新电脑上的执行指令。

# Knowledge Compiler / Qoder Knowledge Engine 研究与 V0.1 技术设计归档

> 归档时间：2026-08-24
> 用途：将当前 ChatGPT 会话完整转移到 Codex，继续进行开发与实现。
> 主题：Qoder Knowledge Card / Repo Wiki / Knowledge Engine、竞品与开源方案、Knowledge Compiler V0.1、Knowledge IR Technical Specification。

---

# 0. 当前项目上下文与结论摘要

本次会话从研究 Qoder 的 Knowledge Card 开始，随后补充 Repo Wiki 作为背景，进一步调研了 Sourcegraph、GitHub Copilot Memory、Cursor、DeepWiki、CodeWiki、Microsoft deep-wiki Skill、Qwen CodeScope、Agent Skills 等方案，并最终将目标从“复刻 Qoder”收敛为：

> 构建一套开放的、Agent-agnostic 的 Knowledge Compiler，使 Codex / Claude Code / Cursor / Qoder 等 Coding Agent 都能获得类似甚至优于 Qoder Knowledge Engine 的工程知识能力。

核心架构理念：

```text
Evidence != Knowledge != Context
```

推荐总体架构：

```text
Git Repository
    ↓
Evidence Engine
    ↓
Knowledge Planner
    ↓
Knowledge Extractor
    ↓
Knowledge IR
    ↓
Knowledge Validator
    ↓
Knowledge Compiler
    ↓
Wiki / Knowledge Card / AGENTS.md / Task Context
    ↓
MCP / Skills
    ↓
Codex / Claude Code / Cursor / Qoder
```

V0.1 的核心技术创新点不放在 AST、Vector DB、IDE 插件或完整 Knowledge Graph 上，而聚焦：

1. Knowledge IR
2. Knowledge Extraction Protocol
3. Evidence-backed Validation
4. Context Compilation
5. Incremental Knowledge Invalidation / Recompilation

V0.1 只实现 5 种 Knowledge Object：

- Architecture
- Module
- Flow
- Rule
- TechStack

核心 Skills：

- knowledge-planner
- knowledge-extractor
- knowledge-validator
- knowledge-maintainer

核心 deterministic 模块：

- Evidence Engine
- IR Storage
- Compiler
- Git Diff / Invalidation
- MCP Server

---

# 1. 用户：研究 Qoder Knowledge Card

用户：

> 读取一下https://docs.qoder.com/zh/user-guide/knowledge-engine/knowledge-cards 里面的内容，我对于这个知识萃取的方式有点兴趣。一方面想研究一下如何实现的，有没有对应的skill可以使用。另一方面，想要知道提供类似功能的其他方式和方法，有没有更好的方案

---

# 2. 助手：Qoder Knowledge Card 分析

Qoder 的 Knowledge Card 值得研究，其价值不在“自动生成文档”，而在于引入了一层：

```text
Code / Documents
    ↓
Distilled Knowledge Layer
    ↓
Agent Context
```

它与普通 RAG 有明显区别。

## 2.1 Knowledge Card 的定位

Qoder Knowledge Card 是从代码中提炼的高密度知识单元，主要包含：

| Knowledge Card | 萃取内容 | Agent 用途 |
|---|---|---|
| Architecture | 模块职责、依赖关系、设计决策 | 理解系统 |
| Spec | 编码规范、接口约束、业务规则 | 生成/审查代码 |
| Tech Stack | 框架、库、版本、工程环境 | 技术决策 |

它并非一次性生成，而会随着 commit 持续追踪代码变化，并支持人工修改、团队共享和 Git 管理。

Qoder 还明确区分：

```text
Repo Wiki       → Human readable
Knowledge Card  → Agent consumable
```

核心问题不是：

> 怎么让 AI 搜到代码？

而是：

> 怎么让 AI 不必每次重新理解代码。

这比普通 RAG 更进一步。

## 2.2 推测底层实现

已公开部分：

```text
Repository
    ↓
Incremental Indexing
    ↓
Embedding / Semantic Search
```

更完整的推测：

```text
                    Git Repository
                         │
             ┌───────────┴───────────┐
             ↓                       ↓
       File / Symbol Index      Git Diff / Commit
             │                       │
             └───────────┬───────────┘
                         ↓
               Structural Analysis
               AST / Symbol / Imports
                         ↓
                  Code Dependency
                         ↓
              Knowledge Extraction
                         ↓
       ┌─────────────┬──────────────┐
       ↓             ↓              ↓
 Architecture      Specs        Tech Stack
       │             │              │
       └─────────────┴──────────────┘
                         ↓
                 Knowledge Cards
                         ↓
                Retrieval / Ranking
                         ↓
                       Agent
```

核心不是 embedding，而是：

> Semantic Distillation

例如普通 RAG 存几十个 chunk；Knowledge Engine 会萃取为 Semantic Object / Knowledge Object。

示例：

```yaml
type: architecture
entity: OrderService

responsibility:
  - manages order lifecycle
  - validates inventory before payment

depends_on:
  - InventoryService
  - PaymentService

invariants:
  - payment happens after inventory reservation

entry_points:
  - POST /orders
  - OrderCreatedEvent

source:
  - src/order/*
```

## 2.3 Knowledge Card 接近轻量 Ontology

Knowledge Card 本质接近：

```text
Entity
+
Relationship
+
Rule
+
Evidence
+
Context
```

例如：

```text
Order
 │
 ├── managed_by → OrderService
 │
 ├── reserves → Inventory
 │
 ├── triggers → Payment
 │
 └── governed_by → OrderCreationSpec
```

行业路线可粗略理解为：

| 路线 | 核心思想 |
|---|---|
| Vector RAG | 找相似文本 |
| Code Search | 找相关代码 |
| Code Graph | 找相关结构 |
| Knowledge Card | 找已经理解后的知识 |
| Ontology | 找对象 + 关系 + 规则 |

更看好后两类。

## 2.4 Skill 是否可以做

可以。

Skill 与 Knowledge Card 的区别：

```text
Knowledge Card = What I know
Skill          = How I work
```

推荐组合：

```text
Knowledge Layer
      ↓
Skill Layer
      ↓
Agent
```

建议建立一个 Knowledge Extraction Skill：

```text
knowledge-extractor/
├── SKILL.md
├── schemas/
│   ├── architecture.yaml
│   ├── business-rule.yaml
│   ├── api.yaml
│   ├── data-model.yaml
│   └── decision.yaml
├── scripts/
│   ├── scan_repo.py
│   ├── dependency_graph.py
│   └── git_diff.py
└── prompts/
    ├── extract.md
    ├── reconcile.md
    └── validate.md
```

推荐工作流：

```text
Discover
    ↓
Segment
    ↓
Extract
    ↓
Normalize
    ↓
Link
    ↓
Verify
    ↓
Persist
```

## 2.5 应扩展为 Knowledge Object

不局限于 Architecture + Spec + Tech Stack，可扩展：

| Knowledge Object | 举例 |
|---|---|
| Entity | Customer / Order / Supplier |
| Concept | Revenue / GMV / SLA |
| Process | Order Fulfillment |
| Rule | 订单金额 > X 需要审批 |
| Decision | 为什么选择 Kafka |
| Architecture | OMS → WMS → TMS |
| Metric | OTIF |
| API | createOrder |
| Data | order_status |
| Owner | Supply Chain Team |
| Exception | Cancel after shipment |
| Experience | 某类故障的处理办法 |

整体架构：

```text
Documents
Code
Database
Conversations
Tickets
Decisions
        ↓
Knowledge Extraction
        ↓
Knowledge Objects
        ↓
Knowledge Graph
        ↓
Context Engine
        ↓
Skills / Agents
```

## 2.6 Evidence Chain

Knowledge 不应只是结论，应保存证据链：

```yaml
knowledge:
  id: BR-ORDER-001
  type: business_rule

statement:
  Inventory must be reserved before payment.

evidence:
  - src/order/create_order.ts:122-158
  - docs/order-flow.md
  - PR #1823

confidence: 0.96

scope:
  service: order-service

valid_from:
  commit: a812cc

last_verified:
  commit: f93da1
```

目标：

- 可验证
- 可追溯
- 可失效

## 2.7 Incremental Update 是难点

不是每次重扫整个 repo，而是：

```text
Git Diff
↓
Changed Symbols
↓
Dependency Graph
↓
Affected Knowledge Objects
↓
Selective Re-extraction
```

例如：

```text
payment.ts changed
      ↓
PaymentService
      ↓
OrderPaymentFlow
      ↓
影响 Knowledge:
  ARCH-012
  RULE-027
  API-008
```

核心能力：

> Knowledge Invalidation

## 2.8 初步推荐架构：Agent Knowledge Fabric

```text
                 SOURCES
 ┌────────┬────────┬─────────┬─────────┐
 │ Code   │ Docs   │ DB      │ History │
 └───┬────┴───┬────┴────┬────┴────┬────┘
     │        │         │         │
     └────────────┬───────────────┘
                  ↓
        Knowledge Extraction
                  ↓
        Semantic Normalization
                  ↓
 ┌─────────────────────────────────┐
 │        KNOWLEDGE OBJECTS        │
 │ Entity     Process     Rule     │
 │ API        Metric      Decision │
 │ Architecture Experience Spec    │
 └────────────────┬────────────────┘
                  ↓
           Relationship Graph
                  ↓
           Evidence / Version
                  ↓
        Retrieval + Context Engine
                  ↓
        ┌─────────┴─────────┐
        ↓                   ↓
      Skills              Agents
```

MVP：

```text
Git Repository
      ↓
Knowledge Extraction Skill
      ↓
5类 Knowledge Object

Architecture
Business Rule
API
Data Model
Tech Stack
      ↓
Markdown/YAML
      ↓
Git versioning
      ↓
Agent retrieval
```

后续逐步增加：

- Git Diff
- Incremental Update
- Evidence
- Confidence
- Relationship Graph
- Human Correction
- Documents / Jira / PR / Meeting / DB Schema

---

# 3. 用户：补充 Repo Wiki 作为背景

用户：

> 我们也看看repo wiki的相关内容作为背景输入https://docs.qoder.com/zh/user-guide/repo-wiki

---

# 4. 助手：Repo Wiki 分析

Repo Wiki 纳入后，Qoder 的整体 Knowledge Engine 更清晰。

## 4.1 Repo Wiki 定位

Repo Wiki 基于代码库自动生成结构化工程文档，并持续跟踪代码和文档变化。

典型结构：

```text
Project Overview
│
├── Architecture
│   ├── System Architecture
│   ├── Module Relationships
│   └── Data Flow
│
├── Order Domain
│   ├── Overview
│   ├── Order Creation
│   ├── State Machine
│   └── Payment Integration
│
├── Inventory
│   ├── Reservation
│   └── Release
│
└── Engineering
    ├── Tech Stack
    ├── Configuration
    └── Development Convention
```

和 README 的区别：

> 系统从 repository 反向构建“这个项目应该如何被解释”。

## 4.2 Qoder Repo Wiki 使用 Multi-Agent

公开信息表明 Repo Wiki 使用多 Agent 架构，分阶段生成工程知识。

更接近：

```text
                         Repository
                              │
                    ┌─────────┴─────────┐
                    ↓                   ↓
                Code Index           Git History
                    │                   │
                    └─────────┬─────────┘
                              ↓
                       Repository Scan
                              ↓
                     Planning Agent
                              ↓
               ┌──────────────┼──────────────┐
               ↓              ↓              ↓
         Architecture      Modules        Conventions
            Agent           Agent             Agent
               ↓              ↓              ↓
               └──────────────┼──────────────┘
                              ↓
                      Knowledge Synthesis
                              ↓
                       Validation / Link
                              ↓
                         Repo Wiki
```

## 4.3 wiki_plan.yaml 暴露 Knowledge Planning

Qoder 支持：

```text
.qoder/repowiki/wiki_plan.yaml
```

结构大致：

```yaml
repowiki:
  template:
  notes:
  documents:

knowledgecard:
  notes:

scope:
  include:
  exclude:
```

documents 可定义：

```yaml
documents:
  - title: "Architecture"
    goal: "Explain system architecture"
    parent: ""
    hints: "Focus on service dependencies"
```

说明 Pipeline 中存在：

> Knowledge Planning

正确流程：

```text
Code
 ↓
Understand
 ↓
Plan what knowledge should exist
 ↓
Generate knowledge
```

## 4.4 Repo Wiki Pipeline 抽象

```text
① INDEX
Repository understanding
        ↓
② DISCOVER
发现核心概念、模块、架构
        ↓
③ PLAN
生成 Wiki information architecture
        ↓
④ EXTRACT
从代码中提取 Evidence
        ↓
⑤ SYNTHESIZE
生成结构化知识
        ↓
⑥ MAINTAIN
Diff → Impact → Incremental Update
```

## 4.5 Repo Wiki 与 Knowledge Card 的关系

更可能共享前置的代码理解和知识模型：

```text
                         Repository
                              ↓
                      Code Understanding
                              ↓
                       Knowledge Model
                              ↓
              ┌───────────────┴────────────────┐
              ↓                                ↓
          Repo Wiki                     Knowledge Cards
              ↓                                ↓
       Human-oriented                  Agent-oriented
       Narrative View                  Dense Context View
```

## 4.6 Wiki 应作为 Knowledge View，而不是 Canonical Knowledge

推荐：

```text
Canonical Knowledge Model
          │
   ┌──────┼──────────┐
   ↓      ↓          ↓
 Wiki    Card      Graph
```

底层例如：

```yaml
id: service.order

type: service

responsibility:
  - Manage order lifecycle

dependencies:
  - inventory.service
  - payment.service

apis:
  - POST /orders

rules:
  - reserve_inventory_before_payment

evidence:
  - src/order/service.ts
  - src/order/controller.ts
```

然后编译成 Wiki / Card / Graph。

## 4.7 Human Knowledge Overlay

Qoder 支持人工：

- Modify
- Supplement
- Rewrite

人工知识会被保护，不会被下一次机器生成覆盖，还会同步到 Knowledge Cards。

这形成：

```text
                     CODE
                      │
                      ↓
              Machine Knowledge
                      │
                      ↓
                    Wiki
                      ↑
                      │
               Human Correction
                      │
                      ↓
            Persistent Knowledge
                      │
                      ↓
                Knowledge Card
```

本质是：

> Human-in-the-loop Knowledge Governance

## 4.8 Git / Branch-aware Knowledge

Repo Wiki 数据可位于：

```text
.qoder/repowiki
```

并随 Git commit/push/pull。

知识应该是：

```text
Knowledge(repository, branch, commit)
```

而不是只有 current state。

## 4.9 Qoder 更完整的 Knowledge Engine

公开信息显示 Qoder 知识层还涉及：

```text
Vector Index
+
Code Graph
+
Commit Graph
+
Repo Wiki
+
Knowledge Cards
+
Memory
```

Commit Graph 用于弥合：

```text
“人说的业务需求”
        ↕
“代码里的具体实现”
```

## 4.10 目标升级：Knowledge Compiler

推荐把系统类比成编译器：

```text
                Raw Knowledge
                     ↓
                   Parse
                     ↓
                 Analyze
                     ↓
              Build Semantic IR
                     ↓
                Normalize
                     ↓
                Validate
                     ↓
                  Compile
             ┌───────┼───────┐
             ↓       ↓       ↓
           Wiki    Card    Context
```

关键是：

> Semantic IR

而不是直接：

```text
Code → Markdown
```

应该：

```text
Code
 ↓
Knowledge IR
 ↓
Markdown
```

完整目标：

> Agent Knowledge Compiler

```text
                           SOURCES
                              │
       ┌──────────┬───────────┼───────────┬──────────┐
       ↓          ↓           ↓           ↓          ↓
      Code       Docs        Git          DB      Conversation
       │          │           │           │          │
       └──────────┴───────────┼───────────┴──────────┘
                              ↓
                    Source Understanding
                              ↓
                     Knowledge Planner
                              ↓
                    Knowledge Extraction
                              ↓
                     Semantic Knowledge IR
                              ↓
       ┌──────────────────────┼───────────────────────┐
       │                      │                       │
       ↓                      ↓                       ↓
    Human View             Agent View             Graph View
       │                      │                       │
       ↓                      ↓                       ↓
   Wiki / Docs          Knowledge Card          Ontology / KG
                              │
                              ↓
                      Context Compiler
                              ↓
                  ┌───────────┴───────────┐
                  ↓                       ↓
                Skills                  Agents
```

叠加：

```text
Git Diff
   ↓
Impact Analysis
   ↓
Knowledge Invalidation
   ↓
Incremental Recompile
```

---

# 5. 用户：询问下一步

用户：

> 好，下一步做什么？

---

# 6. 助手：建议先做竞品、Skill 与 MVP 调研

建议三步：

1. 竞品与开源方案拆解
2. 现成 Skill / 开源组件盘点
3. 定义 Knowledge Compiler MVP

重点比较：

```text
Index
→ Discover
→ Plan
→ Extract
→ Validate
→ Update
→ Retrieve
```

并回答：

- 哪些能力已有成熟开源实现
- 哪些可以用 Skill 拼
- 哪些必须自己开发
- 最适合 MVP 的技术栈
- 第一版边界

---

# 7. 用户：开始调研

用户：

> 好，开始

---

# 8. 助手：竞品、开源、Skill 调研结论

结论：

> 不建议复刻 Qoder Repo Wiki。
>
> 更好的方向是利用 Agent Skills + AST/Code Graph + Git Diff + Evidence Retrieval，构建轻量 Knowledge Compiler。

行业可分 5 层：

| 层级 | 问题 | 代表 |
|---|---|---|
| L1 Code Index | 代码在哪 | Cursor / Embedding / Search |
| L2 Code Intelligence | 代码怎么连接 | Sourcegraph Code Graph / AST |
| L3 Agentic Retrieval | 此任务读什么 | Cody / Claude Code / Codex |
| L4 Knowledge Distillation | 系统长期应该知道什么 | Qoder Knowledge Card / GitHub Memory |
| L5 Knowledge Representation | 如何形成 Wiki / Card / Graph | Qoder Repo Wiki / CodeWiki / DeepWiki |

最值得研究的是 L4。

## 8.1 Qoder

最值得借鉴：

> Knowledge Lifecycle

```text
Generate
   ↓
Human Correct
   ↓
Persist
   ↓
Git Version
   ↓
Code Changes
   ↓
Incremental Update
```

## 8.2 Sourcegraph

更像：

> Code Intelligence Infrastructure

组合：

```text
Keyword Search
+
Sourcegraph Search
+
Code Graph
```

并支持 Agentic Context Fetching：

```text
Question
 ↓
Search
 ↓
Read
 ↓
Reflect

“信息够吗？”
  │
  ├── No → 再 Search / Terminal / MCP
  │
  └── Yes
       ↓
     Answer
```

结论：

> Knowledge Compiler 不应该替代 Agentic Retrieval。

应当：

```text
Knowledge
+
Real-time Code Retrieval
```

## 8.3 Cursor

代表“轻知识”：

```text
Index
+
Rules
+
Memory
+
Agent Retrieval
```

Cursor Memory：

```text
Conversation → Knowledge
```

Qoder：

```text
Code → Knowledge
```

## 8.4 GitHub Copilot Memory

重要趋势：

```text
Repository-level facts
+
User-level preferences
```

Repository facts 带代码 citation，使用前还会检查当前 branch 中 citation 是否仍然有效。

这验证了：

> Evidence-backed Knowledge Object

推荐：

```yaml
id: order.inventory.rule

type: business_rule

statement:
  Inventory must be reserved before payment creation.

evidence:
  - path: src/order/create.ts
    symbol: createOrder
    lines: 120-158

relations:
  subject: OrderService
  depends_on:
    - InventoryService

confidence: 0.97

validity:
  branch: main
  commit: 92fab3

status:
  verified
```

核心理念：

> Knowledge 本身不是 Truth。Evidence 才是 Truth。

## 8.5 DeepWiki

典型：

```text
Clone Repository
      ↓
Analyze Structure
      ↓
Create Embeddings
      ↓
Generate Documentation
      ↓
Generate Diagrams
      ↓
Wiki
      ↓
RAG Q&A
```

更 Agentic 的实现：

```text
Outline
 ↓
Page Agent
 ↓
Read
Grep
Glob
 ↓
Follow imports
 ↓
Search callers
 ↓
Verify
 ↓
Wiki Page
```

## 8.6 CodeWiki

这是非常贴近目标的项目：

```text
AST Repository Analysis
       ↓
Deterministic Code Graph
       ↓
GraphRAG
       ↓
Wiki
       ↓
Q&A
       ↓
MCP
```

支持：

```text
imports
definitions
calls
routes
inheritance
source references
configuration usage
```

Lite Mode 使用：

```text
.codewiki/codewiki-lite.sqlite3
```

提供：

```text
symbol search
source context
call traces
affected-file analysis
```

支持：

```text
status
sync
watch
```

因此可视为：

> Local Context Engine

CodeWiki 还有 Codex Skill：

```text
codewiki skill install codex
```

流程：

```text
plan wiki
      ↓
retrieve evidence
      ↓
write page
      ↓
save
      ↓
validate
```

并拆出：

```text
wiki plan
wiki evidence
wiki save
wiki validate
```

这一点很值得参考：

> Knowledge Engine 与 LLM 解耦。

## 8.7 Microsoft deep-wiki Skill

公开的 `deep-wiki` Skill 中 `wiki-researcher` 强调：

```text
Read actual code
Trace connections
Ground every claim
Provide source references
```

禁止：

```text
"This likely handles..."
"Based on naming convention..."
"This is probably..."
```

每个重要结论必须：

```text
file_path + line_number
```

说明行业正在转向：

> Source-grounded Knowledge Generation

## 8.8 Qwen CodeScope

采用：

```text
Structure Graph
+
Evolution Graph
+
Embeddings
```

Structure Graph：

```text
function
call
import
class
module
```

Evolution Graph：

```text
commit
file change
function modification
```

因此可回答：

- 谁调用谁
- 为什么修改
- 哪些代码相似
- 哪个 PR 风险高

这说明：

> Code Graph + Commit Graph + Embedding

正在成为共识。

## 8.9 行业融合架构

```text
                        Repository
                            │
          ┌─────────────────┼──────────────────┐
          ↓                 ↓                  ↓
        Code              Git                Docs
          │                 │                  │
          ↓                 ↓                  ↓
      AST Graph        Commit Graph        Embedding
          │                 │                  │
          └─────────────────┼──────────────────┘
                            ↓
                      Evidence Layer
                            ↓
                   Agentic Retrieval
                            ↓
                      LLM Extraction
                            ↓
                   Knowledge Objects
                            │
             ┌──────────────┼──────────────┐
             ↓              ↓              ↓
          Wiki          Agent Card      Memory
             │              │              │
             └──────────────┼──────────────┘
                            ↓
                     Context Compiler
                            ↓
                       Coding Agent
```

## 8.10 Skill 的职责边界

不要让 Skill 自己承担 Code Index。

应该：

```text
CodeWiki / CodeGraph
        ↓
     Evidence

        +

Knowledge Extraction Skill
        ↓
 How to interpret evidence

        ↓

Knowledge Object
```

即：

```text
Engine = What is true
Skill  = How to reason
```

## 8.11 推荐 MVP 技术路线

第一版不要做：

- 自己 Vector DB
- 自己 AST parser
- 自己 Code Search
- 完整 Knowledge Graph
- IDE

应该：

```text
                Git Repository
                     │
                     ↓
            AST / Code Graph Engine
               （直接复用）
                     │
                     ↓
               Evidence API
                     │
                     ↓
         Knowledge Extraction Skill
                     │
                     ↓
               Knowledge IR
                     │
          ┌──────────┼──────────┐
          ↓          ↓          ↓
        Wiki        Card       AGENTS.md
          │          │          │
          └──────────┼──────────┘
                     ↓
                  Agent
```

V0.1 技术建议：

| 能力 | 推荐 |
|---|---|
| Repo parsing | Tree-sitter / CodeWiki |
| Code Graph | CodeWiki Lite |
| Storage | SQLite |
| Git | native Git |
| LLM | Codex / Claude |
| Workflow | Agent Skill |
| Knowledge | Markdown + YAML |
| Wiki | Markdown |
| Agent Card | Markdown/YAML |
| Integration | MCP |
| Version | Git |

推荐先把 CodeWiki 当 Evidence Engine。

自己重点做：

```text
Knowledge Planner
Knowledge Extractor
Knowledge IR
Knowledge Validator
Knowledge Compiler
```

## 8.12 V0.1 Knowledge Object

只做：

- Architecture
- Module
- Flow
- Rule
- TechStack

后续再加：

V0.2：

- Decision
- API
- Data Model
- Convention

V0.3：

- Commit Intent
- Incident
- PR
- Issue
- Experience

## 8.13 Knowledge IR 不能等于 Wiki

```text
               Knowledge IR
                     │
        ┌────────────┼─────────────┐
        ↓            ↓             ↓
      Wiki       Knowledge Card   AGENTS.md
 Human view       Agent view     Instruction
```

同一 Knowledge 不同 Compilation Target。

## 8.14 三层核心

```text
Evidence → Knowledge → Context
```

分别回答：

### Evidence Engine
代码到底是什么？

### Knowledge Engine
这些代码意味着什么？

### Context Compiler
当前 Agent 做这个任务，需要知道哪些？

## 8.15 与 Qoder 的区别

| Qoder | 我们 |
|---|---|
| Repo Wiki | Wiki View |
| Knowledge Card | Knowledge View |
| Memory | Experience View |
| Code Index | Evidence Engine |
| `/knowledge` | Knowledge Governance |
| wiki_plan | Knowledge Planner |
| Agent Context | Context Compiler |
| 隐式内部结构 | 开放 Knowledge IR |
| Qoder IDE | Agent-agnostic / MCP |

目标：

```text
                     Knowledge Engine
                            │
                 ┌──────────┼──────────┐
                 ↓          ↓          ↓
              Codex      Claude      Cursor
```

## 8.16 最值得复用的项目

| 项目 | 价值 | 优先级 |
|---|---|---:|
| CodeWiki | AST / Graph / Evidence / MCP / Incremental | ★★★★★ |
| Microsoft deep-wiki | Research / Evidence / Citation Skill | ★★★★★ |
| Qwen CodeScope | Code Graph + Evolution Graph | ★★★★★ |
| Sourcegraph | Agentic Retrieval | ★★★★☆ |
| GitHub Memory | Evidence-backed Memory | ★★★★☆ |
| Qoder | Knowledge Lifecycle / UX | ★★★★☆ |
| DeepWiki | Wiki Planner / Generator | ★★★☆☆ |
| Cursor | Context Rules / Memory | ★★★☆☆ |

## 8.17 V0.1 模块

```text
01 Evidence Engine
02 Knowledge Planner
03 Knowledge Extractor
04 Knowledge IR
05 Knowledge Validator
06 Knowledge Compiler
07 Context Retriever
```

A/B Test：

```text
repo
 ↓
自动发现 Architecture / Module / Flow / Rule
 ↓
生成 Knowledge IR
 ↓
生成 Wiki
 ↓
生成 Agent Card
 ↓
问 Agent 10 个问题
```

Baseline：

```text
纯 grep / RAG / Agent search
```

指标：

- Accuracy
- Context Tokens
- Tool Calls

---

# 9. 用户：同意进入技术设计

用户：

> 好的，同意进行下一步。

---

# 10. 助手：Knowledge Compiler V0.1 技术设计

产品定义：

> 输入一个 Git Repository，自动萃取经过源码证据验证的工程知识，并编译成 Wiki、Agent Knowledge Cards 和任务级 Context，供 Codex / Claude Code / Cursor / Qoder 等 Agent 使用。

核心假设：

> 预先萃取 Knowledge，是否能让 Coding Agent 用更少 Token、更少 Tool Calls、更准确地完成复杂代码任务。

## 10.1 总体架构

```text
┌─────────────────────────────────────────────────────────┐
│                    Coding Agents                        │
│       Codex / Claude Code / Cursor / Qoder              │
└──────────────────────────┬──────────────────────────────┘
                           │
                    MCP / Skill API
                           │
┌──────────────────────────▼──────────────────────────────┐
│  07 Context Compiler / Retriever                        │
│  当前任务究竟应该提供哪些 Knowledge + Evidence？        │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  06 Knowledge Compiler                                  │
│  Knowledge IR → Wiki / Card / AGENTS / Context          │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  05 Knowledge Validator                                 │
│  Evidence / Confidence / Conflict / Freshness           │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                     Knowledge IR                        │
│ Architecture / Module / Flow / Rule / TechStack         │
└──────────────────────────▲──────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│  03 Knowledge Extractor                                 │
│  Evidence → Semantic Knowledge                          │
└──────────────────────────▲──────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│  02 Knowledge Planner                                   │
│  决定“这个 Repository 值得萃取哪些知识”                 │
└──────────────────────────▲──────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│  01 Evidence Engine                                     │
│ AST / Symbols / Calls / Imports / Git / Source          │
└──────────────────────────▲──────────────────────────────┘
                           │
                     Git Repository
```

## 10.2 设计原则

```text
Evidence != Knowledge != Context
```

### Evidence

```text
src/order/service.ts
createOrder()
line 118-164
calls reserveInventory()
```

### Knowledge

```text
创建订单时必须先锁定库存。
```

### Context

```text
你正在修改 OrderService。

相关规则：
1. 创建 payment 前必须完成 inventory reservation。
2. 修改 createOrder 时同时检查 rollback flow。

相关实现：
- src/order/service.ts:createOrder
- src/inventory/reservation.ts:reserve
```

## 10.3 五类 Knowledge Object

### Architecture

描述高层系统结构。

```yaml
type: architecture
id: architecture.backend

title: Backend Architecture

components:
  - order-service
  - inventory-service
  - payment-service

relationships:
  - source: order-service
    relation: depends_on
    target: inventory-service
```

### Module

```yaml
type: module
id: module.order-service

name: Order Service

responsibilities:
  - order lifecycle management
  - order validation
  - orchestration of inventory and payment

public_interfaces:
  - createOrder
  - cancelOrder

dependencies:
  - module.inventory-service
  - module.payment-service
```

### Flow

```yaml
type: flow
id: flow.create-order

title: Create Order

trigger:
  POST /orders

steps:
  - validate_order
  - reserve_inventory
  - create_payment
  - persist_order
  - publish_order_created

participants:
  - module.order
  - module.inventory
  - module.payment
```

真实顺序：

```text
API
 ↓
OrderController
 ↓
OrderService
 ↓
Inventory.reserve()
 ↓
Payment.create()
 ↓
OrderRepository.save()
```

### Rule

```yaml
type: rule
id: rule.inventory-before-payment

statement:
  Inventory must be reserved before payment creation.

severity:
  invariant

applies_to:
  - flow.create-order

exceptions: []

evidence:
  - src/order/service.ts:createOrder
```

### TechStack

```yaml
type: tech_stack
id: tech.backend

runtime:
  language: TypeScript
  version: "5.x"

framework:
  - NestJS

database:
  - PostgreSQL

infrastructure:
  - Redis
  - Kafka

testing:
  - Jest
```

## 10.4 初步 Knowledge IR Schema

```yaml
id: string
type: architecture | module | flow | rule | tech_stack

title: string

summary: string

scope:
  repository: string
  branch: string

evidence:
  - path: string
    symbol: string?
    start_line: int?
    end_line: int?
    commit: string

relations:
  - predicate: string
    target: string

confidence:
  score: 0.0-1.0
  basis: string

provenance:
  extractor: string
  generated_at: datetime
  model: string?

validity:
  status: verified | stale | conflicted | human_verified
  verified_commit: string
```

## 10.5 目录结构

```text
.knowledge/
│
├── manifest.yaml
│
├── objects/
│   ├── architecture/
│   ├── modules/
│   ├── flows/
│   ├── rules/
│   └── tech-stack/
│
├── evidence/
│   └── index.sqlite
│
├── views/
│   ├── wiki/
│   ├── cards/
│   └── agents/
│
├── plans/
│   └── knowledge-plan.yaml
│
└── state/
    ├── last-scan.yaml
    └── dependency-map.json
```

推荐：

- Knowledge IR → YAML
- Evidence / Index → SQLite

## 10.6 Knowledge Planner

流程：

```text
Repository
 ↓
Structure Survey
 ↓
Identify Important Areas
 ↓
Generate Knowledge Plan
```

示例：

```yaml
repository:
  name: ecommerce-backend

architecture:
  - backend-overview

modules:
  - order
  - payment
  - inventory
  - customer

flows:
  - create-order
  - cancel-order
  - refund-order

rules:
  - payment
  - inventory
  - cancellation

tech_stack:
  - backend
```

Planner Skill：

```text
knowledge-planner/
└── SKILL.md
```

职责：

> 分析 Repository 的结构和 Evidence 索引，输出 knowledge-plan.yaml，不生成最终知识。

## 10.7 Knowledge Extractor Skill

```text
knowledge-extractor/
└── SKILL.md
```

流程：

```text
Knowledge Plan Item
       ↓
Collect Evidence
       ↓
Follow Call / Import / Dependency
       ↓
Cross-check
       ↓
Generate Knowledge Object
```

禁止根据命名猜。

例如不能：

```text
PaymentManager probably manages payments.
```

必须基于真实实现。

## 10.8 Knowledge Validator

```text
knowledge-validator/
└── SKILL.md
```

检查：

```text
Claim
 ↓
Evidence
 ↓
Does evidence support claim?
```

例如若存在另一条代码路径违反当前总结，状态应：

```yaml
status: conflicted
```

## 10.9 Knowledge Compiler

输入：

```text
Knowledge IR
```

输出：

- Wiki View
- Agent Card
- AGENTS / Rules View

Compiler 只负责转换，不产生新知识。

## 10.10 Context Compiler

针对任务：

> 给 OrderService 增加 COD 支付。

生成：

```text
Task
 ↓
Task Analysis
 ↓
Relevant Knowledge
 ↓
Relevant Evidence
 ↓
Context Package
```

例如：

```yaml
task_context:

  modules:
    - module.order
    - module.payment

  flows:
    - flow.create-order

  rules:
    - rule.inventory-before-payment
    - rule.payment-failure-rollback

  evidence:
    - OrderService.createOrder
    - PaymentService.createPayment
```

## 10.11 MCP API

第一版核心工具：

```text
knowledge.repo_overview
knowledge.search
knowledge.get_object
knowledge.get_related
knowledge.get_evidence
knowledge.context_for_task
knowledge.status
```

核心：

```text
knowledge.context_for_task
```

## 10.12 Incremental Update

```text
Git diff
 ↓
Changed Files
 ↓
Affected Symbols
 ↓
Related Knowledge Objects
 ↓
Mark stale
 ↓
Selective Re-extraction
 ↓
Validation
```

通过 Evidence 索引反查受影响对象。

## 10.13 Human Override

```yaml
provenance:
  source: human

validity:
  status: human_verified

protection:
  overwrite: false
```

机器发现冲突时不覆盖，产生：

```text
human_machine_conflict
```

## 10.14 四个核心 Skills

```text
knowledge-planner
knowledge-extractor
knowledge-validator
knowledge-maintainer
```

Compiler 应 deterministic，不必做 Skill。

边界：

```text
LLM Reasoning
├── Planner
├── Extractor
├── Validator
└── Maintainer

Deterministic
├── Evidence Engine
├── IR Storage
├── Compiler
├── Git Diff
└── MCP
```

原则：

> 能 deterministic 的地方尽量不用 Agent。

## 10.15 技术栈

| 模块 | 推荐 |
|---|---|
| Language | Python |
| CLI | Typer |
| Evidence Engine | CodeWiki Lite / tree-sitter |
| Storage | SQLite + YAML |
| Schema | Pydantic / JSON Schema |
| Git | native Git CLI |
| LLM Workflow | Agent Skills |
| Agent Integration | MCP |
| Wiki | Markdown |
| Diagram | Mermaid |
| Testing | pytest |

## 10.16 CLI

```bash
knowledge init
knowledge scan
knowledge plan
knowledge extract
knowledge validate
knowledge compile
knowledge update
knowledge serve
```

## 10.17 端到端流程

```text
git clone repo

      ↓

knowledge init

      ↓

knowledge scan
      │
      └─ AST / Symbol / Call / Import

      ↓

knowledge plan
      │
      └─ What should we know?

      ↓

knowledge extract
      │
      └─ Evidence-grounded Knowledge

      ↓

knowledge validate

      ↓

Knowledge IR

      ↓

knowledge compile

      ↓

┌────────┬────────┬──────────┐
│ Wiki   │ Cards  │ AGENTS   │
└────────┴────────┴──────────┘

      ↓

knowledge serve

      ↓

Codex / Claude / Cursor
```

## 10.18 验证方式

A/B Test：

### Baseline A
Agent + 原 Repository

### Experimental B
Agent + Repository + Knowledge Compiler

任务示例：

1. Explain order creation flow
2. Add an API parameter
3. Modify payment behavior
4. Find impact of changing inventory
5. Fix a deliberate bug
6. Add a new integration

核心指标：

### Accuracy
Task Success Rate

### Context Cost
Input Tokens + Retrieved Source Tokens

### Exploration Cost
grep/search/read/tool calls

以及：

### Knowledge Fidelity

```text
Knowledge Claim
     ↓
Can evidence prove it?
```

例如：

```text
96 / 100 supported by source
```

则：

```text
Knowledge Fidelity = 96%
```

## 10.19 V0.1 不做

- 企业文档
- Jira
- Confluence
- Slack
- 完整 Ontology
- Neo4j
- 复杂 UI
- IDE Plugin
- 团队权限
- SaaS

只打透：

```text
Repository → Evidence → Knowledge → Agent
```

## 10.20 开发顺序

### Sprint 1 — Evidence

```text
repo → symbols / dependencies / source
```

### Sprint 2 — Knowledge IR

完成五类 Schema + YAML Storage。

### Sprint 3 — Extract

实现 Planner + Extractor。

### Sprint 4 — Validate

加入 Evidence validation / Conflict / Confidence。

### Sprint 5 — Compile

生成 Repo Wiki / Knowledge Card / AGENTS.md。

### Sprint 6 — Agent Integration

实现 MCP / context_for_task，并做 A/B Test。

## 10.21 V0.1 完成定义

```text
✓ 自动分析 Repository
✓ 自动规划 Knowledge
✓ 自动生成 5 类 Knowledge Object
✓ 每条 Knowledge 有 Evidence
✓ 支持 validation
✓ 支持 Git Diff 增量更新
✓ 生成 Wiki
✓ 生成 Agent Card
✓ MCP 对 Agent 暴露 Knowledge
✓ 在真实 Coding Tasks 上完成 A/B Test
```

---

# 11. 用户：继续

用户：

> 继续

---

# 12. 助手：Knowledge IR Technical Specification

Knowledge IR 是整个 Knowledge Compiler 的：

> Canonical Knowledge Model

它不等于 Wiki，不等于 Knowledge Card，也不等于 Agent Context。

```text
Evidence
   ↓
Knowledge Extraction
   ↓
Knowledge IR
   ↓
┌────────────┬─────────────┬──────────────┐
│ Wiki View  │ Agent Card  │ Task Context │
└────────────┴─────────────┴──────────────┘
```

设计目标：

1. Evidence-backed
2. Machine-readable
3. Human-editable
4. Version-aware
5. Composable
6. Agent-friendly
7. Extensible

## 12.1 核心对象模型

```text
KnowledgeObject
│
├── ArchitectureKnowledge
├── ModuleKnowledge
├── FlowKnowledge
├── RuleKnowledge
└── TechStackKnowledge
```

基础模型：

```python
class KnowledgeObject(BaseModel):
    id: str
    type: KnowledgeType

    title: str
    summary: str

    scope: Scope

    evidence: list[Evidence]

    relations: list[Relation] = []

    confidence: Confidence

    provenance: Provenance

    validity: Validity

    governance: Governance

    tags: list[str] = []

    metadata: dict[str, Any] = {}
```

## 12.2 ID 规范

```text
<type>.<domain>.<name>
```

例如：

```text
architecture.backend
module.order
module.inventory
flow.order.create
rule.order.inventory-before-payment
techstack.backend
```

不要把纯 UUID 作为主要语义 ID。

## 12.3 Scope Model

```python
class Scope(BaseModel):
    repository: str

    branch: str = "main"

    root_path: str | None = None

    commit: str | None = None

    modules: list[str] = []
```

示例：

```yaml
scope:
  repository: ecommerce-backend
  branch: main
  root_path: services/order
  commit: a82c119
```

## 12.4 Evidence Model

```python
class Evidence(BaseModel):
    id: str

    kind: EvidenceKind

    path: str

    symbol: str | None = None

    start_line: int | None = None
    end_line: int | None = None

    commit: str

    relation: EvidenceRelation

    strength: EvidenceStrength

    excerpt_hash: str | None = None
```

EvidenceKind V0.1：

```text
source_code
config
manifest
test
git_commit
documentation
```

对于系统实际行为，推荐证据优先级：

```text
source_code
   >
test
   >
config
   >
documentation
```

## 12.5 Evidence Relation

```python
class EvidenceRelation(str, Enum):
    SUPPORTS = "supports"
    IMPLEMENTS = "implements"
    CONSTRAINS = "constrains"
    CONTRADICTS = "contradicts"
    EXAMPLE_OF = "example_of"
```

示例：

```yaml
evidence:
  - id: ev-001
    kind: source_code
    path: src/order/service.ts
    symbol: createOrder
    start_line: 118
    end_line: 162
    relation: supports
    strength: direct
```

## 12.6 Evidence Strength

```python
class EvidenceStrength(str, Enum):
    DIRECT = "direct"
    STRONG = "strong"
    INDIRECT = "indirect"
```

`Indirect Evidence` 不允许单独支持 verified invariant。

## 12.7 Relation Model

```python
class Relation(BaseModel):
    predicate: RelationType
    target: str

    evidence_ids: list[str] = []

    confidence: float | None = None
```

RelationType V0.1：

```text
contains
depends_on
calls
implements
participates_in
governed_by
constrained_by
triggers
produces
consumes
precedes
follows
related_to
```

## 12.8 Confidence Model

不要让 LLM 随意输出神秘分数。

```python
class Confidence(BaseModel):
    score: float

    level: ConfidenceLevel

    basis: list[ConfidenceBasis]

    explanation: str | None = None
```

ConfidenceLevel：

```text
high
medium
low
```

建议：

```text
0.85–1.00 → high
0.65–0.84 → medium
< 0.65     → low
```

ConfidenceBasis：

```text
direct_code_path
multiple_code_paths
test_confirmation
config_confirmation
cross_file_confirmation
single_source
naming_only
documentation_only
human_verified
```

## 12.9 Provenance Model

```python
class Provenance(BaseModel):
    source: ProvenanceSource

    extractor: str | None = None

    model: str | None = None

    generated_at: datetime

    updated_at: datetime

    parent_object_id: str | None = None
```

ProvenanceSource：

```text
machine
human
machine_with_human_edit
imported
```

## 12.10 Validity Model

```python
class Validity(BaseModel):
    status: ValidityStatus

    verified_commit: str | None = None

    verified_at: datetime | None = None

    stale_since_commit: str | None = None

    stale_reason: str | None = None

    conflicts: list[Conflict] = []
```

状态：

```text
draft
unverified
verified
stale
conflicted
human_verified
deprecated
```

生命周期：

```text
draft
  ↓
unverified
  ↓
verified
  ↓
Git Change
  ↓
stale
  ↓
Re-extract
  ↓
verified
```

或者：

```text
verified
  ↓
Contradicting Evidence
  ↓
conflicted
```

## 12.11 Conflict Model

```python
class Conflict(BaseModel):
    id: str

    type: ConflictType

    description: str

    evidence_ids: list[str]

    severity: ConflictSeverity

    resolution: str | None = None
```

类型：

```text
evidence_conflict
human_machine_conflict
branch_conflict
rule_violation
version_conflict
```

## 12.12 Governance Model

```python
class Governance(BaseModel):
    owner: str | None = None

    locked: bool = False

    overwrite_policy: OverwritePolicy = "machine_allowed"

    review_required: bool = False
```

OverwritePolicy：

```text
machine_allowed
human_review
human_only
```

机器发现新代码与人工知识冲突时不覆盖，产生：

```text
human_machine_conflict
```

## 12.13 Architecture Knowledge

```python
class ArchitectureKnowledge(KnowledgeObject):
    type: Literal["architecture"]

    components: list[ArchitectureComponent]

    boundaries: list[Boundary] = []

    entrypoints: list[EntryPoint] = []

    data_flows: list[str] = []

    architectural_patterns: list[str] = []
```

Validator Rules：

```text
ARCH-001
所有 component target 必须存在。

ARCH-002
Architecture 中关键 dependency 必须存在 Evidence。

ARCH-003
不能仅根据目录结构推断 service dependency。

ARCH-004
如果发现 circular dependency，需要显式记录。

ARCH-005
Architecture summary 中的关键组件必须出现在 components。
```

## 12.14 Module Knowledge

```python
class ModuleKnowledge(KnowledgeObject):
    type: Literal["module"]

    responsibilities: list[str]

    boundaries: list[str] = []

    public_interfaces: list[Interface] = []

    dependencies: list[str] = []

    entrypoints: list[str] = []

    owns_data: list[str] = []
```

重要约束：

> Responsibility 必须来自行为，不得从文件夹或类名猜。

## 12.15 Flow Knowledge

```python
class FlowKnowledge(KnowledgeObject):
    type: Literal["flow"]

    trigger: Trigger | None

    participants: list[str]

    steps: list[FlowStep]

    outcomes: list[Outcome] = []

    alternate_paths: list[FlowPath] = []

    failure_paths: list[FlowPath] = []

    invariants: list[str] = []
```

FlowStep：

```python
class FlowStep(BaseModel):
    id: str

    order: int

    action: str

    actor: str | None

    target: str | None

    evidence_ids: list[str]

    optional: bool = False

    condition: str | None = None
```

必须支持 Alternate / Failure Path。

例如：

```yaml
failure_paths:
  - name: payment_failure

    starts_after: create_payment

    steps:
      - release_inventory
      - mark_order_failed
```

## 12.16 Rule Knowledge

```python
class RuleKnowledge(KnowledgeObject):
    type: Literal["rule"]

    statement: str

    rule_type: RuleType

    severity: RuleSeverity

    applies_to: list[str]

    conditions: list[str] = []

    exceptions: list[str] = []

    consequences: list[str] = []
```

RuleType：

```text
invariant
ordering
validation
security
data_integrity
integration
configuration
convention
```

Severity：

```text
critical
high
normal
advisory
```

critical invariant 的 Evidence 更严格：

```text
Direct Evidence
OR
Strong Evidence + Test Confirmation
```

documentation-only 不能自动升级为 critical verified rule。

## 12.17 TechStack Knowledge

```python
class TechStackKnowledge(KnowledgeObject):
    type: Literal["tech_stack"]

    languages: list[Technology]

    runtimes: list[Technology] = []

    frameworks: list[Technology] = []

    databases: list[Technology] = []

    infrastructure: list[Technology] = []

    build_tools: list[Technology] = []

    test_tools: list[Technology] = []

    package_managers: list[Technology] = []
```

Technology：

```python
class Technology(BaseModel):
    name: str

    version: str | None

    source: str | None

    required: bool = True
```

TechStack 应优先 deterministic 提取：

```text
package.json
pyproject.toml
go.mod
pom.xml
Cargo.toml
Dockerfile
docker-compose
.github/workflows
```

## 12.18 Claim Layer

建议增加 Claim 抽象：

```python
class Claim(BaseModel):
    id: str

    statement: str

    evidence_ids: list[str]

    confidence: Confidence

    status: ClaimStatus
```

原因：

一个 Object 中可能有多个 statement，不是所有 Evidence 都能证明所有 statement。

因此：

> Evidence Validation 应发生在 Claim Level。

推荐最终基础对象：

```python
class KnowledgeObject(BaseModel):

    id: str
    type: KnowledgeType

    title: str
    summary: str

    scope: Scope

    claims: list[Claim]

    evidence: list[Evidence]

    relations: list[Relation]

    confidence: Confidence

    provenance: Provenance

    validity: Validity

    governance: Governance
```

## 12.19 Flow 完整示例

```yaml
id: flow.order.create

type: flow

title: Create Order

summary: >
  Order creation validates the request,
  reserves inventory, creates payment,
  persists the order and emits an event.

scope:
  repository: ecommerce-backend
  branch: main
  commit: a812cc4

trigger:
  type: http
  value: POST /orders

participants:
  - module.order
  - module.inventory
  - module.payment

steps:

  - id: validate
    order: 1
    action: validate order request
    actor: module.order
    evidence_ids:
      - ev-001

  - id: reserve_inventory
    order: 2
    action: reserve inventory
    actor: module.inventory
    evidence_ids:
      - ev-002

  - id: create_payment
    order: 3
    action: create payment
    actor: module.payment
    evidence_ids:
      - ev-003

claims:

  - id: claim.order.create.001

    statement: >
      Inventory reservation occurs before
      payment creation.

    evidence_ids:
      - ev-002
      - ev-003

    confidence:
      score: 0.98
      level: high
      basis:
        - direct_code_path

    status: verified

evidence:

  - id: ev-002
    kind: source_code
    path: src/order/service.ts
    symbol: createOrder
    start_line: 126
    end_line: 136
    commit: a812cc4
    relation: supports
    strength: direct

  - id: ev-003
    kind: source_code
    path: src/order/service.ts
    symbol: createOrder
    start_line: 138
    end_line: 151
    commit: a812cc4
    relation: supports
    strength: direct

relations:

  - predicate: governed_by
    target: rule.order.inventory-before-payment

confidence:
  score: 0.96
  level: high
  basis:
    - direct_code_path
    - multiple_code_paths

provenance:
  source: machine
  extractor: knowledge-extractor@0.1
  generated_at: 2026-08-24T06:00:00Z
  updated_at: 2026-08-24T06:00:00Z

validity:
  status: verified
  verified_commit: a812cc4

governance:
  locked: false
  overwrite_policy: machine_allowed
```

## 12.20 Validator 架构

建议拆：

```text
Deterministic Validator
+
Semantic Validator
```

### Deterministic Validation

```text
V001 Evidence path 必须存在。
V002 Evidence commit 必须存在。
V003 symbol 如果声明，则必须能够解析。
V004 start_line <= end_line。
V005 Relation target 必须存在。
V006 Flow Step order 不得重复。
V007 所有 Claim 引用的 evidence_id 必须存在。
V008 verified Object 不允许没有 verified Claim。
V009 critical Rule 不允许只有 indirect evidence。
V010 stale Evidence 不允许输出 active Agent Rule。
```

### Semantic Validation

LLM 只判断机器无法可靠判断的问题：

```text
Claim:
Inventory must be reserved before payment.

Evidence:
真实源码片段

Question:
Does this evidence actually support the claim?
```

输出：

```yaml
supported: true
strength: direct
reason: ...
```

Extractor 与 Validator 必须不同 Skill，避免同源幻觉。

未来甚至可以：

```text
Extractor Model A
Validator Model B
```

## 12.21 Knowledge Plan Schema

```yaml
repository:
  name: ecommerce-backend

targets:

  - id: architecture.backend
    type: architecture
    priority: high
    rationale: >
      Repository contains multiple independent services.

  - id: module.order
    type: module
    priority: high

  - id: flow.order.create
    type: flow
    priority: high
    entrypoint_hint:
      - POST /orders

  - id: rule.order.inventory-before-payment
    type: rule
    priority: high

  - id: techstack.backend
    type: tech_stack
    priority: medium
```

Planner 只决定：

> 值得调查什么。

不能决定：

> 最终结论是什么。

Planning Confidence 与 Knowledge Confidence 必须分离。

## 12.22 增量更新

每条 Evidence 包含：

```text
path
symbol
commit
```

因此：

```text
Changed File
     ↓
Evidence Index
     ↓
Affected Claim
     ↓
Affected Knowledge Object
```

未来支持 Claim-level invalidation：

```text
Object:
Module.order

Claim A → valid
Claim B → stale
Claim C → valid
```

V0.1 可先做 Object-level invalidation，但 Schema 必须预留 Claim-level。

## 12.23 Compiler 原则

Compiler 不产生新事实，只允许：

```text
Select
Reorder
Compress
Render
```

不允许：

```text
Invent
Infer new architecture
Add unsupported recommendations
```

## 12.24 Context Compilation

ContextRequest 可设计：

```python
class ContextRequest(BaseModel):
    task: str

    token_budget: int = 8000

    include_evidence: bool = True

    evidence_depth: Literal[
        "none",
        "summary",
        "source"
    ]
```

推荐 Ranking：

```text
Score =
0.35 semantic relevance
+
0.25 relation distance
+
0.20 object importance
+
0.10 evidence confidence
+
0.10 freshness
```

但 Task Relevance 应优先，避免每次都塞架构总览。

## 12.25 Storage

```text
YAML   = Source of Knowledge Truth
SQLite = Retrieval Infrastructure
```

## 12.26 Manifest

```yaml
version: "0.1"

repository:
  name: ecommerce-backend

knowledge_schema:
  version: "0.1"

last_scan:
  commit: a812cc4

objects:
  total: 37

  architecture: 1
  module: 9
  flow: 12
  rule: 11
  tech_stack: 4

status:
  verified: 31
  stale: 4
  conflicted: 2
```

## 12.27 Knowledge Health Score

建议从 V0.1 就定义：

```text
Coverage
30%

Evidence Fidelity
30%

Freshness
20%

Conflict Rate
10%

Human Verification
10%
```

例如：

```text
Knowledge Health = 86/100
```

Coverage：

```text
完成 Targets / Planner Targets
```

Evidence Fidelity：

```text
有直接/强 Evidence 的 Claims / 总 Claims
```

Freshness：

```text
当前 commit 上仍 verified 的 Objects / 总 Objects
```

## 12.28 最终抽象

```text
Repository
   │
   ↓
Knowledge Object
   │
   ├── contains → Claim
   │              │
   │              └── supported_by → Evidence
   │
   ├── relates_to → Knowledge Object
   │
   ├── governed_by → Governance
   │
   └── valid_at → Commit
```

这是一个轻量 Ontology，但 V0.1 不需要 Neo4j。

SQLite + YAML 足够。

## 12.29 V0.1 Schema 范围

核心模型：

```text
KnowledgeObject
Scope
Claim
Evidence
Relation
Confidence
Provenance
Validity
Conflict
Governance

ArchitectureKnowledge
ModuleKnowledge
FlowKnowledge
FlowStep
RuleKnowledge
TechStackKnowledge
Technology

KnowledgePlan
KnowledgePlanTarget
```

目标控制在：

```text
15–20 个 Pydantic Model
```

## 12.30 下一步：Agent Workflow Design

下一阶段应该设计四个 Skills：

```text
knowledge-planner
knowledge-extractor
knowledge-validator
knowledge-maintainer
```

每个 Skill 要明确：

```text
Inputs
Allowed Tools
Reasoning Procedure
Output Schema
Stop Conditions
Failure Handling
Anti-hallucination Rules
```

并把它们连接到：

```text
Evidence Engine
+
Knowledge IR
+
MCP
```

最终形成真正可执行的 `SKILL.md`。

---

# 13. 用户：要求归档当前会话

用户：

> 给我把当前会话的全部内容都归档到一个md文件中，要完整和详实，后面的开发和实现过程我要转入到codex中去进行

---

# 14. 给 Codex 的接续说明

本次 ChatGPT 会话到此为止，后续建议在 Codex 中继续。

## 14.1 建议 Codex 下一步任务

从以下任务开始，不再继续做广泛调研。

### Task 1：建立项目骨架

建议目录：

```text
knowledge-compiler/
├── pyproject.toml
├── README.md
├── src/
│   └── knowledge_compiler/
│       ├── cli/
│       ├── models/
│       ├── evidence/
│       ├── planner/
│       ├── extractor/
│       ├── validator/
│       ├── compiler/
│       ├── maintainer/
│       ├── retrieval/
│       └── mcp/
├── skills/
│   ├── knowledge-planner/
│   │   └── SKILL.md
│   ├── knowledge-extractor/
│   │   └── SKILL.md
│   ├── knowledge-validator/
│   │   └── SKILL.md
│   └── knowledge-maintainer/
│       └── SKILL.md
├── schemas/
├── tests/
└── examples/
```

### Task 2：首先实现 Pydantic Models

优先顺序：

1. enums
2. Scope
3. Evidence
4. Confidence
5. Claim
6. Relation
7. Provenance
8. Conflict
9. Validity
10. Governance
11. KnowledgeObject
12. ArchitectureKnowledge
13. ModuleKnowledge
14. FlowKnowledge
15. RuleKnowledge
16. TechStackKnowledge
17. KnowledgePlan

### Task 3：实现 deterministic Validator

先实现：

```text
V001–V010
```

不接 LLM。

### Task 4：实现 YAML serialization + manifest

做到：

```text
KnowledgeObject
→ YAML
→ reload
→ schema validation
```

### Task 5：实现最小 Evidence Engine Adapter

第一版优先考虑：

- CodeWiki Lite adapter
- 如集成成本过高，则先 tree-sitter + ripgrep/git 组合
- Engine 对上层只暴露统一 Evidence API

### Task 6：设计四个 SKILL.md

依次：

1. knowledge-planner
2. knowledge-extractor
3. knowledge-validator
4. knowledge-maintainer

严格落实：

- 不根据名称猜实现
- 结论必须有 Evidence
- Planner 不生成最终知识
- Validator 不重写 Knowledge
- Maintainer 不覆盖 human_locked knowledge

### Task 7：MCP

第一版只实现：

```text
knowledge.repo_overview
knowledge.search
knowledge.get_object
knowledge.get_related
knowledge.get_evidence
knowledge.context_for_task
knowledge.status
```

### Task 8：选择一个公开 Repo 做实验

推荐中等规模、有测试、有明显模块边界的 TypeScript/Python 项目。

做：

```text
Baseline:
Codex + repo

Experimental:
Codex + repo + Knowledge Compiler
```

测：

- Task Success Rate
- Input / Context Tokens
- Tool Calls
- Search / grep / read 次数
- Knowledge Fidelity

---

# 15. Codex 开发时应坚持的核心原则

## 原则 1

```text
Evidence != Knowledge != Context
```

绝不合并三层。

## 原则 2

> Evidence is truth; Knowledge is a semantic projection of evidence.

## 原则 3

> Compiler must never invent new facts.

## 原则 4

> Planner decides what to investigate, not what is true.

## 原则 5

> Extractor must trace actual code paths; names/comments alone are insufficient.

## 原则 6

> Validation should be claim-level whenever possible.

## 原则 7

> Human knowledge is governed, not silently overwritten.

## 原则 8

> Use deterministic tooling wherever possible; reserve LLMs for semantic reasoning.

## 原则 9

> Knowledge must be repository-, branch-, and commit-aware.

## 原则 10

> V0.1 only needs Repository → Evidence → Knowledge → Agent.

---

# 16. 当前状态

已经完成：

- Qoder Knowledge Card 研究
- Qoder Repo Wiki 研究
- Qoder Knowledge Engine 抽象
- Sourcegraph / Cursor / GitHub Copilot Memory / DeepWiki / CodeWiki / Microsoft deep-wiki / Qwen CodeScope 调研
- 行业能力矩阵
- Knowledge Compiler 产品定位
- V0.1 总体架构
- V0.1 技术栈建议
- V0.1 CLI 设计
- V0.1 MCP API 草案
- V0.1 5 类 Knowledge Object
- Knowledge IR 基础模型
- Evidence / Claim / Relation / Confidence / Provenance / Validity / Governance / Conflict 模型
- Incremental invalidation 设计
- Context Compiler 初步设计
- Knowledge Health 指标设计
- 开发 Sprint 建议
- A/B Test 方案

尚未实现：

- 代码项目骨架
- Pydantic Models
- JSON Schema
- SQLite schema
- Evidence Engine adapter
- Knowledge Planner Skill
- Knowledge Extractor Skill
- Knowledge Validator Skill
- Knowledge Maintainer Skill
- Compiler
- Context Retriever
- MCP Server
- A/B benchmark

下一阶段应直接进入 Codex 开发。

---

# 17. 一句话项目定义

> Knowledge Compiler 是一个面向 Coding Agents 的工程知识编译层：它从 Git Repository 中提取可验证 Evidence，将 Evidence 萃取为版本化、可治理的 Knowledge IR，并按任务实时编译为 Wiki、Knowledge Cards 和 Agent Context，从而降低 Coding Agent 的代码探索成本并提高任务准确率。

---

# 18. 最终目标演化路线

```text
V0.1
Engineering Knowledge from Repository
      ↓
V0.2
Git History / PR / Decision
      ↓
V0.3
Issue / Incident / Experience
      ↓
V0.4
Product Docs / Business Rules
      ↓
V1.0
Enterprise Knowledge Compiler
```

最终：

```text
Code
Docs
DB
Git
PR
Issue
Meeting
Experience
       ↓
Enterprise Knowledge IR
       ↓
Ontology / Wiki / Cards / Skills
       ↓
Agents
```

---

**End of archive.**

---

# 第三编：已批准的 Knowledge Compiler V0.1 正式规格（原文）

> 本编是 V0.1 的权威产品与技术规格。若历史讨论与本编冲突，以本编为准。

# Knowledge Compiler V0.1 Design

**Status:** Spec review approved; awaiting final user review
**Date:** 2026-08-24
**Product horizon:** Local repository first; Git URL support next; multi-repository workspaces later

## 1. Product definition

Knowledge Compiler is a local-first engineering knowledge compiler for coding agents. It reads one local Git repository, obtains deterministic code facts and bounded source evidence through CodeWiki, extracts evidence-backed knowledge into a canonical Knowledge IR, and compiles that IR into:

1. a Repo Wiki for human browsing;
2. typed Knowledge Cards for agent consumption;
3. task-specific context exposed through CLI and MCP.

The core product hypothesis is that precompiled, evidence-backed repository knowledge allows coding agents to complete repository tasks more accurately or with less exploratory work than using the repository alone.

## 2. Goals and non-goals

### 2.1 V0.1 goals

- Analyze one local Git repository, including a monorepo under one Git root.
- Use CodeWiki as the default code-evidence provider without forking it or reading its internal database.
- Generate five typed knowledge objects: Architecture, Module, Flow, Rule, and TechStack.
- Bind every factual field to source evidence through claim granularity.
- Support both Codex Skill and built-in LLM execution modes through one orchestrator.
- Validate objects structurally and semantically before publication.
- Persist canonical, version-aware Knowledge IR as reviewable YAML.
- Compile Markdown Repo Wiki pages, Markdown Knowledge Cards, and a standalone interactive HTML Wiki.
- Retrieve budgeted task context through CLI and seven MCP tools.
- Detect affected knowledge after source changes and selectively rebuild it.
- Provide a repeatable Agent A/B benchmark.

### 2.2 V0.1 non-goals

- Remote Git URL cloning, authentication, caching, or cleanup.
- Cross-repository knowledge or service topology.
- A long-running Web UI or SaaS service.
- Manual card editing, human locking, approval, or publishing workflows.
- A custom AST parser, code graph, vector database, or repository watcher.
- Background generation, Git hooks, automatic commits, or code execution inside the target repository.
- Multiple synchronized output languages. One build uses either Chinese or English.
- A general enterprise knowledge platform or ingestion of tickets, chats, meetings, incidents, or external documents.

## 3. Stable product decisions

| Area | Decision |
|---|---|
| Primary input | One local Git repository |
| Future input | Git URLs through a RepositoryProvider extension |
| Evidence engine | CodeWiki through a versioned adapter |
| Canonical store | Independent Knowledge IR, not CodeWiki Wiki pages |
| Human view | Markdown Repo Wiki plus standalone interactive HTML |
| Agent view | Typed YAML/Markdown Knowledge Cards plus task context |
| Knowledge types | Architecture, Module, Flow, Rule, TechStack |
| Execution modes | Codex Skill and built-in LLM through one RunOrchestrator |
| Editing | Generated content is read-only in V0.1 |
| Primary success metric | Agent task effectiveness |
| Secondary success metric | Human-readable, source-grounded Wiki quality |

## 4. System boundary and architecture

```text
Local Git Repository
        |
        v
External CodeWiki
  scan / AST / graph / source chunks
        |
        v
CodeWikiEvidenceProvider (versioned JSON contract)
        |
        v
Repository Survey -> Knowledge Plan -> Bounded Evidence Packs
        |                                  |
        |                    +-------------+-------------+
        |                    |                           |
        |                    v                           v
        |              Codex Skill                Built-in LLM
        |                    |                           |
        |                    +-------------+-------------+
        |                                  |
        v                                  v
                     Draft Knowledge Objects
                                  |
                                  v
                   Structural + Semantic Validator
                                  |
                                  v
                      Canonical Knowledge IR
                         /          |          \
                        v           v           v
                  Repo Wiki   Knowledge Cards   Task Context
                 MD + HTML       YAML + MD       CLI + MCP
```

CodeWiki owns code facts. Knowledge Compiler owns knowledge semantics, claim-to-evidence binding, validity, storage, view compilation, and task selection.

CodeWiki's existing Wiki generator is a reference implementation and benchmark baseline. It is not the canonical source for V0.1 outputs because independently generated CodeWiki pages and Knowledge Cards could disagree. Both product views must be compiled from the same Knowledge IR.

## 5. Component boundaries

### 5.1 RepositoryProvider

Resolves an input into an immutable repository snapshot identity.

```python
class RepositoryProvider(Protocol):
    def resolve(self, path: Path) -> RepositorySnapshot: ...
    def diff(self, baseline: FileInventory, current: FileInventory) -> ChangeSet: ...
```

`RepositorySnapshot` contains the absolute root, stable repository ID, branch, commit, remote URL when present, dirty flag, eligible-file inventory, and working-tree hash when dirty. V0.1 implements only `LocalGitRepositoryProvider`.

The eligible-file inventory permanently excludes `.knowledge/`, `.codewiki/`, `.git/`, ignored files, dependency directories, binary files, and configured oversize files. The dirty flag and working-tree hash use this filtered inventory rather than raw `git status`, so generated knowledge and CodeWiki indexes never make their own source snapshot dirty. The same exclusion is passed to CodeWiki indexing.

### 5.2 EvidenceProvider

Provides code facts without exposing the provider's internal storage.

```python
class EvidenceProvider(Protocol):
    def inspect(self, repo: RepositorySnapshot) -> RepositorySurvey: ...
    def ensure_index(self, repo: RepositorySnapshot) -> IndexStatus: ...
    def build_pack(
        self,
        repo: RepositorySnapshot,
        target: PlanTarget,
        budget: EvidenceBudget,
    ) -> EvidencePack: ...
    def get_evidence(self, repo: RepositorySnapshot, evidence_id: str) -> EvidenceItem: ...
```

V0.1 implements `CodeWikiEvidenceProvider` through CodeWiki's machine-readable CLI surface. It does not import CodeWiki internals or query its SQLite/PostgreSQL tables. Repository change detection belongs to `RepositoryProvider`, is computed before CodeWiki sync, and remains available when the CodeWiki cache is missing.

The first implementation targets the CodeWiki 0.6 minor series. Before feature implementation, a blocking adapter spike must run these capabilities against a committed fixture repository and capture their JSON as contract fixtures:

| Provider need | CodeWiki 0.6 command family | Required result |
|---|---|---|
| Register repository | `codewiki repos add <path> --json` | Stable provider repository identifier |
| Full index | `codewiki analyze <repo> --json` | Successful run plus indexed snapshot metadata |
| Incremental index | `codewiki update <repo> --json` | Successful catch-up after Knowledge Compiler computes its own `ChangeSet` |
| Repository survey | `codewiki repos scan <repo> --json`, graph search, and indexed files | Files, languages, symbols, routes, graph communities, and configuration facts |
| Target exploration | `codewiki graph explore <topic> --json` and graph query/trace commands | Bounded nodes, edges, and source references |
| Affected symbols | `codewiki graph affected --stdin --json` | Provider hints for a supplied changed-file list |

The adapter normalizes captured provider JSON into project-owned Pydantic DTOs. Raw source snippets are read locally from the resolved repository only after CodeWiki returns an allowed source reference; they do not depend on a CodeWiki evidence ID. If any required command lacks usable machine-readable data, the spike tries the equivalent documented CodeWiki MCP/HTTP surface. If neither public surface satisfies the contract, implementation stops and reports the missing capability instead of importing internals. The design must then be revised before feature work continues.

Knowledge Compiler evidence IDs are content-addressed and provider-independent:

```text
sha256(repository_id, snapshot_id, path, symbol, start_line, end_line, source_content_hash)
```

They are stable for unchanged source within the same repository snapshot and are rebuilt when source content or range changes.

### 5.3 Planner

Consumes `RepositorySurvey` and produces a `KnowledgePlan`. It selects investigation targets and evidence seeds; it never creates final claims. Planning can use the selected semantic worker, but deterministic repository facts are always supplied first.

### 5.4 RunOrchestrator and semantic workers

```python
class SemanticWorker(Protocol):
    def plan(self, request: PlanRequest) -> KnowledgePlan: ...
    def extract(self, request: ExtractionRequest) -> ExtractionResult: ...
    def verify(self, request: VerificationRequest) -> VerificationResult: ...
```

`RunOrchestrator` owns target queues, leases, idempotency, structural validation, semantic work scheduling, repair counters, publication, and final run status. Semantic workers only transform a versioned request into a versioned result.

Two execution modes use the same request and result schemas but different transport:

- Agent mode: Codex leases a target from the orchestrator, submits extraction or verification results with a lease token and idempotency key, and may resume an interrupted run.
- Built-in mode: `LiteLLMWorker` consumes the same queue in-process. One configured extraction profile and one optional validation profile produce structured JSON. V0.1 has no model-routing UI or complex routing policy.

Every semantic request/result contains `contract_version`, `run_id`, `target_id`, `operation`, `attempt`, `snapshot_id`, and `idempotency_key`. Duplicate submissions with the same idempotency key return the recorded result without repeating publication or model work.

### 5.5 Validator

Performs deterministic structural checks and semantic-worker-backed entailment checks. Only objects passing both stages become `verified`.

### 5.6 KnowledgeStore

Loads, validates, and transactionally writes canonical YAML objects, `plan.yaml`, and default Agent surfaces. Drafts are written to run staging first. A publish transaction backs up replaced files/directories, writes a journal, swaps canonical objects, the latest plan/target results, the verified-only Cards directory, and the generation-stamped FTS database, writes the manifest last as the commit marker, and then removes the journal. Startup restores backups for any journal without a commit marker. Failed updates preserve the previous object but mark it stale.

### 5.7 Compiler

Transforms active canonical IR into Wiki Markdown, Cards Markdown, deterministic Mermaid diagrams, and standalone HTML. Wiki compilation accepts verified and stale objects so humans can see expiry warnings. Agent Cards, FTS, and task context accept only verified objects. The compiler cannot call an LLM or introduce new claims.

### 5.8 ContextRetriever

Indexes verified objects in a local SQLite FTS5 cache, expands one hop through explicit Knowledge relations, ranks type-aware results, and compiles a context package under a token budget. Before every default Agent read, it requires the repository snapshot, `active_generation`, `agent_views_generation`, and FTS generation stamp to match; a mismatch fails closed with `knowledge_update_required`. It excludes stale objects by default. Invalid, conflicted, and insufficient-evidence target results are never canonical objects.

### 5.9 MCP server

Exposes read-only knowledge and evidence retrieval over stdio. It does not perform builds or mutate the target repository.

## 6. Canonical Knowledge IR

### 6.1 Base object

```yaml
schema_version: "0.1"
id: flow.order.create
type: flow
title: Create Order Flow
summary:
  text: Creates an order after inventory reservation and payment initiation.
  claim_ids:
    - flow.order.create.claim.inventory-first
scope:
  repository: ecommerce
  branch: main
  commit: abc123
  dirty: false
claims:
  - id: flow.order.create.claim.inventory-first
    statement: Inventory is reserved before payment creation.
    evidence:
      - ev.order-service.create-order.01
    confidence: 0.96
relations:
  - predicate: involves
    target: module.inventory
    claim_ids:
      - flow.order.create.claim.inventory-first
validity:
  status: verified
  verified_commit: abc123
provenance:
  execution_mode: codex-skill
  model: null
  generated_at: 2026-08-24T00:00:00Z
```

Stable semantic IDs use `<type>.<domain>.<name>` rather than opaque database identifiers.

### 6.2 Shared models

- `Scope`: repository, branch, commit, root path, dirty flag, and working-tree hash.
- `Claim`: stable ID, statement, evidence IDs, confidence, and verification result.
- `EvidenceRef`: provider, kind, path, symbol, line range, commit, original source hash, redacted excerpt hash, relationship, and strength.
- `ClaimBackedText`: text plus the verified Claim IDs that support it.
- `Relation`: predicate, target object, and supporting Claim IDs.
- `Confidence`: normalized score and basis.
- `Provenance`: execution mode, semantic worker/model, prompt/schema versions, and generation time.
- `Validity`: status, verified commit, stale reason, and validation report.

### 6.3 Typed payloads

- `ArchitectureKnowledge`: components, boundaries, and relationships, each referencing supporting Claim IDs.
- `ModuleKnowledge`: responsibilities, public interfaces, and dependencies, each referencing supporting Claim IDs.
- `FlowKnowledge`: trigger, ordered steps, participants, and failure paths, each referencing supporting Claim IDs.
- `RuleKnowledge`: statement, severity, applicability, and exceptions, each referencing supporting Claim IDs.
- `TechStackKnowledge`: technologies, versions, categories, and configuration evidence, each referencing supporting Claim IDs.

A factual field is any statement about repository structure, behavior, dependency, constraint, technology, version, configuration, or flow. Every factual field must either reference one or more verified Claims or be a deterministic projection of Claim-backed fields. Titles, IDs, ordering labels, and presentation headings are non-factual metadata. Summaries use `ClaimBackedText`; they are not unverified prose.

Mermaid edges, Wiki statements, Card statements, and task-context statements are generated only from verified Claim-backed payload fields. The compiler cannot render an unsupported typed-payload fact.

### 6.4 Validity states

Published canonical objects have only two validity states:

```text
verified -> stale
```

Run targets, which are stored in the plan and run report rather than as canonical objects, have these terminal results:

- `verified`: a canonical object was published;
- `invalid`: schema, reference, or validation failure;
- `conflicted`: supplied evidence supports incompatible conclusions;
- `insufficient_evidence`: the worker declined to create an object;
- `retired`: a deterministic retirement check removed a previously published object;
- `skipped`: an optional target was deliberately omitted by policy.

For object aggregation, every required factual Claim must be `supported`. A `partial` or `unsupported` required Claim makes the draft invalid and eligible for repair. A `conflicted` Claim makes the target conflicted. Optional factual fields with partial or unsupported Claims must be removed during repair before publication; they cannot remain in a verified object.

V0.1 has no human-verified or human-locked state.

## 7. Evidence Pack contract

Every extraction target receives a versioned, bounded pack:

```yaml
contract_version: "0.1"
repository:
  id: ecommerce
  root: /absolute/path
  branch: main
  commit: abc123
  dirty: false
target:
  id: flow.order.create
  type: flow
  topic: create order
evidence:
  - id: ev.order-service.create-order.01
    kind: source
    path: src/order/service.ts
    symbol: createOrder
    start_line: 118
    end_line: 164
    commit: abc123
    content_hash: sha256:...
    excerpt_hash: sha256:...
    excerpt: ...
    strength: direct
graph_facts:
  - source: OrderService.createOrder
    predicate: calls
    target: InventoryService.reserve
    confidence: deterministic
```

`content_hash` verifies the original local source range. Credential redaction produces the model-visible excerpt and `excerpt_hash`; semantic verification uses exactly that redacted excerpt. Structural validation compares the original source hash locally without returning secret text to a model.

The pack has explicit item, character, and token budgets. A worker may request a bounded expansion using named seeds, but it cannot silently ingest an unlimited GraphRAG context. When available evidence cannot support the requested knowledge, the worker returns `insufficient_evidence` instead of guessing from names, comments, or conventions.

## 8. Storage layout

```text
.knowledge/
├── config.yaml
├── manifest.yaml
├── plan.yaml
├── baseline/
│   └── eligible-files.json
├── objects/
│   ├── architecture/
│   ├── modules/
│   ├── flows/
│   ├── rules/
│   └── tech-stack/
├── views/
│   ├── wiki/
│   └── cards/
├── exports/
│   └── repo-wiki.html
├── cache/
│   ├── evidence/
│   └── knowledge-index.sqlite3
└── state/
    └── runs/<run-id>/
```

Tracked by default:

- `config.yaml` without secrets;
- `manifest.yaml` and `plan.yaml`;
- `baseline/eligible-files.json` so incremental comparison survives cache deletion and machine changes;
- canonical `objects/**/*.yaml`;
- compiled `views/wiki/**/*.md` and `views/cards/**/*.md`.

Ignored by default:

- `cache/` and `state/`;
- `exports/repo-wiki.html` because it is reproducible;
- the CodeWiki local index.

Users may explicitly commit the standalone HTML export.

The generated target-repository ignore rules always exclude `.knowledge/` and `.codewiki/` from evidence scanning and snapshot hashes even though selected `.knowledge/` files are tracked by Git. This exclusion is enforced in `RepositoryProvider` and the CodeWiki adapter, not delegated only to `.gitignore`.

`manifest.yaml` separates:

- `observed_snapshot`: the most recent eligible-file inventory examined by a run;
- `active_generation`: the canonical object generation committed by a publish transaction;
- `agent_views_generation`: the verified-only Cards and FTS generation committed in the same transaction as `active_generation`;
- `wiki_generation`: the generation for which human Wiki/HTML views were successfully compiled;
- `pending_targets`: stale or failed required targets that must run again even when no new file diff exists.

The tracked eligible-file inventory contains path, Git blob ID when available, content hash, size, and language classification. It never stores source content.

`plan.yaml` persists the latest target set, required/optional priority, last terminal result, published object ID when any, and retry/pending status. Run reports add detailed attempts and diagnostics, but deleting ignored run reports does not remove the state required by `knowledge status` or the next update.

## 9. Planning, extraction, validation, and publication

### 9.1 Preflight

Before model use, the tool verifies the Git repository, repository identity, supported CodeWiki version, CodeWiki index, schema compatibility, and execution-mode configuration. Unsupported or unavailable prerequisites stop before any LLM call.

### 9.2 Planning

The survey includes directory structure, languages, entry points, high-connectivity modules, public routes and interfaces, configuration files, graph communities, and test structure. The planner produces typed targets with priorities and evidence seeds. It cannot create final claims.

### 9.3 Agent flow

The user invokes `/knowledge-build` or `/knowledge-update`. `RunOrchestrator` persists this target state machine:

```text
queued
  -> evidence_ready
  -> extraction_leased
  -> draft_submitted
  -> structural_validated
  -> semantic_pending
  -> verification_leased
  -> verified
```

Repairable failures move to `repair_pending` and then back to `extraction_leased`; terminal results are `invalid`, `conflicted`, `insufficient_evidence`, `retired`, or `skipped`. A lease contains a run ID, target ID, operation, expiry, attempt, and idempotency key. Expired leases return to their prior queue without losing submitted results.

The Skill uses:

```text
knowledge prepare
knowledge next --operation extraction
knowledge evidence <target>
knowledge submit-extraction <draft.json> --lease <token>
knowledge verify-next
knowledge submit-verification <result.json> --lease <token>
knowledge finalize
```

The orchestrator, not the Skill, increments repair attempts, schedules semantic verification, decides publication eligibility, and computes the final run status. Agent semantic verification uses a fresh verification request containing only Claim-backed fields and their cited redacted evidence; it does not reuse extraction conversation context.

### 9.4 Built-in LLM flow

```bash
knowledge build --executor llm
knowledge update --executor llm
```

The built-in worker consumes the same persisted queue and receives the same plan target, Evidence Pack, JSON Schema, budgets, operation-specific request, and anti-hallucination rules as the Skill path. If no validation profile is configured, it reuses the extraction model profile with the separate verification prompt and request contract; preflight reports this choice.

### 9.5 Structural validation

Mandatory checks include:

- Pydantic and JSON Schema validity;
- stable ID and type correctness;
- referenced Evidence IDs exist in the input pack;
- paths, line ranges, symbols, commits, and content hashes are valid;
- every factual field is Claim-backed or deterministically derived from Claim-backed fields;
- every required Claim has evidence;
- relation targets exist or are explicitly unresolved;
- typed references such as Flow steps and Rule applicability are valid;
- compiler-required fields are present.

### 9.6 Semantic validation

A separate verification phase classifies each Claim-backed fact as `supported`, `partial`, `unsupported`, or `conflicted` using only the fact and its cited redacted evidence. Only fully supported required facts can enter a verified object. Extraction and verification use separate requests, prompts, idempotency keys, and contracts even when they use the same configured model.

### 9.7 Repair and publication

Each target receives at most two repair attempts after its initial submission. Continued failure leaves a run-target result and does not publish a new object. Other verified objects may publish.

A run is `complete` when all required targets are verified or deterministically retired, no previously published object remains stale, and all requested views compiled. Optional targets may end as insufficient or skipped with warnings. A run is `partial` when any required target is neither verified nor retired, any previous object remains stale, or any requested view failed to compile. A run is `failed` when preflight fails or no usable canonical generation exists.

Drafts live under `.knowledge/state/runs/<run-id>/drafts/`. Publication uses the transaction journal described in `KnowledgeStore`; canonical object files and `active_generation` commit together. A failed update preserves the previous content but marks it stale in the canonical object and adds its target to `pending_targets`.

Verified-only Markdown Cards and the FTS database are part of the same recoverable publish transaction as canonical objects. An invalidation transaction runs before semantic regeneration: affected objects become stale, staged Agent Cards omit them, staged FTS omits them, the directories/database swap under the transaction journal, and the manifest commits matching `active_generation` and `agent_views_generation`. A later successful extraction transaction replaces stale objects with verified ones and republishes matching Agent surfaces.

Human Wiki/HTML compilation occurs after that transaction because it may include stale diagnostic content. A Wiki compiler failure does not roll back valid IR or safe Agent surfaces; it leaves `wiki_generation` behind `active_generation`, returns `partial`, and allows `knowledge compile` to retry deterministically.

All default CLI/MCP Agent reads also compare the current filtered repository snapshot with the manifest snapshot and verify generation equality. If a publish transaction fails or source changes without a successful `knowledge update`, reads return `knowledge_update_required` rather than serving the previous Cards/FTS. Explicit stale-diagnostic reads are separate and visibly marked.

## 10. Compiled views

### 10.1 Repo Wiki

```text
views/wiki/
├── index.md
├── architecture.md
├── modules/*.md
├── flows/*.md
├── rules.md
├── tech-stack.md
└── sources.md
```

Deterministic templates organize claims, relations, object links, and Evidence references into readable pages. Mermaid diagrams are derived from Architecture relationships, Module dependencies, and Flow steps. The compiler never calls an LLM.

Wiki pages include both verified and stale canonical objects. Stale sections show the previous verified snapshot, stale reason, last verified commit/hash, and pending target; they are never rendered without an expiry banner.

The standalone HTML contains catalog navigation, heading navigation, full-text search, rendered Mermaid diagrams, object links, collapsible evidence, freshness, commit, and generation metadata. Source links target a fixed remote commit when a remote URL exists; otherwise the page displays local path, symbol, line range, and excerpt.

`knowledge open` compares `wiki_generation` with `active_generation`. When the Wiki is behind, it displays a global stale-view warning before opening the existing HTML and directs the user to run `knowledge compile`; an old Wiki is never presented as current merely because individual stale banners were not compiled.

### 10.2 Knowledge Cards

Each verified canonical object YAML is the machine-readable source for a Knowledge Card; the compiler produces one dense Markdown rendering for convenient inspection. There is no second derived Card YAML. Published Agent Card views include only verified objects. When an object becomes stale, its Markdown Card and FTS row are removed in the invalidation transaction, while its canonical YAML remains available for diagnostics and Wiki warnings. Cards retain the ID, type, Claim-backed summary, key claims, relations, relevant constraints, evidence pointers, and version identity. They omit large source excerpts.

### 10.3 Task context

```bash
knowledge context "Add cash on delivery to the order flow" \
  --format markdown \
  --budget 6000
```

Selection uses SQLite FTS5 over verified objects, one-hop explicit relation expansion, type-aware ranking that favors applicable Rules and Flows, and token-budget compilation. Source bodies are fetched on demand rather than included by default. Stale objects are excluded unless explicitly requested for diagnosis; invalid, conflicted, and insufficient-evidence results are not canonical objects and therefore cannot enter retrieval.

`knowledge context <task> --include-stale` is a diagnostic-only mode. It bypasses default ranking, labels every stale object and stale reason, and never presents the result as safe coding context.

## 11. MCP interface

The stdio server exposes exactly seven V0.1 tools:

```text
knowledge_repo_overview
knowledge_search
knowledge_get_object
knowledge_get_related
knowledge_get_evidence
knowledge_context_for_task
knowledge_status
```

Tools return structured JSON and compact Markdown. The MCP server is read-only and never runs builds.

`knowledge_get_object` and `knowledge_status` accept an explicit `include_stale` diagnostic flag. `knowledge_context_for_task` defaults to verified-only and accepts `include_stale=true` only as a visibly marked diagnostic response. All other calls fail closed on snapshot or generation mismatch.

## 12. Incremental update

```text
Load tracked eligible-file baseline
  -> Resolve current filtered RepositorySnapshot
  -> Compare inventories before CodeWiki sync
  -> CodeWiki full index or incremental update
  -> Provider affected-symbol hints
  -> Evidence reverse index
  -> affected Claims and Objects
  -> mark stale
  -> rebuild bounded Evidence Packs
  -> re-extract and validate
  -> recompile affected views and FTS records
```

The tracked `baseline/eligible-files.json` is authoritative for file-level change detection. Comparison handles committed changes, dirty-to-dirty runs, new untracked eligible files, deletion, and rename; a rename is normalized to delete plus add unless both Git and content hash prove identity. It does not require the previous CodeWiki cache or Git history, so it works after cache deletion, on shallow clones, and after switching commits.

Change detection always runs before CodeWiki sync so provider index mutation cannot erase the comparison baseline. CodeWiki then performs an incremental update when its compatible cache exists or a full index when the cache is absent/incompatible. Provider affected-symbol output enriches the already-computed file change set; it does not replace it.

If CodeWiki indexing fails during update, the tool still commits an invalidation transaction for every object whose Evidence paths intersect the file ChangeSet and every verified object one relation hop from those objects. Those targets enter `pending_targets`; no semantic regeneration runs, new targets are not claimed as discovered, and the command returns `partial`. If no prior canonical generation exists, indexing failure returns `failed`.

A full planner refresh occurs when the manifest, baseline, or schema is missing/corrupt; repository identity changes; the current repository has no usable eligible files; or CodeWiki must rebuild an incompatible index and cannot reproduce prior graph identities. The planner refreshes affected areas when entry points, module directories, routes, dependency/configuration topology, or graph communities change. Ordinary implementation changes only reprocess objects referencing affected files, symbols, or content hashes.

At run end, `observed_snapshot` and the eligible-file baseline advance to the current scan even for a partial run, while every unresolved required target is retained in `pending_targets`. Therefore a later update retries stale work even when no additional files changed. `active_generation` advances only through a successful canonical publish transaction.

### 12.1 Deterministic object retirement

Planner omission never deletes or retires an existing object. Source deletion first marks the object stale and creates a `retirement_pending` target. Retirement is allowed only when all of these checks pass:

1. every Evidence source for the object is absent from the current eligible-file inventory or its referenced symbol/range no longer exists;
2. a deterministic provider-wide exact-symbol, path, graph-node, and lexical FTS search using stored former anchors finds no current candidate evidence. Vector search, LLM summaries, and semantic-worker output are forbidden in this decision;
3. no verified object retains an inbound relation to the candidate. Inbound objects are refreshed first and must either verify without that relation or independently become retirement candidates;
4. every provider query completed successfully on the current snapshot. Unsupported languages, provider errors, truncated results, or inconclusive limits keep the object stale rather than authorizing deletion.

Passing all checks yields target result `retired`. The core publish transaction journals and atomically commits deletion of the object YAML, deletion of its Markdown Card, removal of its FTS row, the updated `plan.yaml`, and the manifest generation. Only the human Wiki section/page and Wiki object links are removed by subsequent Wiki compilation. If any check cannot complete, the object remains stale and pending; it is never silently deleted.

A semantic re-extraction may run before the deterministic check to discover replacement knowledge. A verified replacement cancels retirement, but `insufficient_evidence` or any other model result never authorizes deletion.

If regeneration fails, previous content remains visible as stale, default task context excludes it, the Wiki renders an expiry warning, and the command returns `partial`. V0.1 updates only on an explicit command or Skill action; there is no watcher or Git hook.

## 13. CLI and configuration

Primary commands:

```text
knowledge init --language zh|en
knowledge build --executor llm
knowledge update --executor llm
knowledge status
knowledge validate
knowledge compile
knowledge context <task> [--format json|markdown] [--budget N] [--include-stale]
knowledge open
knowledge serve
```

Agent-only queue commands are the stable internal Skill interface and may be hidden from the primary help group:

```text
knowledge prepare
knowledge next --operation extraction
knowledge evidence <target>
knowledge submit-extraction <draft.json> --lease <token>
knowledge verify-next
knowledge submit-verification <result.json> --lease <token>
knowledge finalize
```

`config.yaml` stores repository/evidence provider types, output language, semantic-worker profile names, and default context budget. Model names, endpoints, and API keys come from environment variables or user-level configuration and never enter the repository.

Exit codes:

- `0`: complete;
- `1`: failed with no usable result;
- `2`: partial with one or more unpublished or stale objects.

Every mutating run writes a structured report under `state/runs/<run-id>/`. Status reports two separate groups: published canonical objects (`verified`, `stale`) and current/latest plan-target results (`verified`, `invalid`, `conflicted`, `insufficient_evidence`, `retired`, `skipped`).

## 14. Security and privacy

- Never execute repository code, installation scripts, build scripts, or tests.
- Respect `.gitignore`, CodeWiki ignore rules, binary exclusions, size limits, dependency-directory exclusions, and common credential-file exclusions.
- Run credential-pattern detection and redaction before an Evidence Pack is sent to a model.
- Never persist API keys in logs, reports, prompts, or `.knowledge/`.
- Send only target-bounded evidence to a model.
- Escape Markdown, source excerpts, and diagram inputs when producing HTML.
- Restrict MCP evidence access to the resolved repository root and known Evidence IDs.
- Treat repository text as data rather than instructions during extraction and validation.

## 15. Error handling

| Failure | Behavior |
|---|---|
| Not a Git repository | Stop preflight with a corrective message |
| CodeWiki missing or unsupported | Stop before LLM use and report the supported 0.6 series |
| Indexing failure | Preserve prior knowledge and return failed or partial |
| Model/provider failure | Apply bounded retry; publish nothing from the failed target |
| Malformed model output | Attempt schema repair at most twice |
| Missing or changed evidence | Mark affected objects stale |
| Conflicting evidence | Publish no verified replacement; record conflicted result |
| Compiler failure | Keep canonical IR; return partial and allow deterministic retry |
| Interrupted run | Leave staging and report for diagnosis; canonical objects remain intact |

## 16. Edge-case behavior

| Repository condition | V0.1 behavior |
|---|---|
| Empty repository or no eligible source | Stop build before model use; create no misleading empty knowledge base |
| Git repository with no commit | Stop preflight and require an initial commit so scope can be versioned |
| Detached HEAD | Allow build using the commit; record branch as `null` and state as detached |
| Shallow clone | Allow inventory-based build/update without requiring unavailable history |
| Dirty working tree | Allow it; persist filtered working-tree hash and per-file hashes |
| Branch or non-descendant commit switch | Compare eligible-file inventories and refresh affected planning areas |
| Missing CodeWiki cache | Rebuild the provider index; use tracked inventory for change detection |
| Unsupported source language | Exclude unsupported files from semantic evidence, report coverage, and fail if no supported code remains |
| Repository exceeds configured file/byte limits | Stop with `scope_limit_exceeded` and require explicit path exclusions; do not silently publish partial coverage as complete |
| Symlink resolving outside repository root | Exclude it from scan and evidence access |
| Deleted evidence source | Mark every referencing canonical object stale until repaired or deliberately retired by a refreshed plan |

## 17. Implementation slices

The implementation plan must preserve this vertical order so the V0.1 scope does not become several parallel unfinished subsystems:

1. Blocking CodeWiki Adapter Spike with captured public-interface JSON fixtures and a go/no-go result.
2. Fake Provider vertical slice: one Module object through plan, extraction result, validation, canonical YAML, Markdown Card, and Wiki page.
3. CodeWiki adapter plus built-in LiteLLM mode for the same vertical slice.
4. All five object types, Claim-backed payload rules, and semantic verification.
5. Persisted RunOrchestrator plus Codex Skill execution mode and interruption recovery.
6. Tracked inventory, stale marking, pending-target retries, and selective update.
7. HTML export, FTS task context, seven read-only MCP tools, and security boundary tests.
8. Agent A/B benchmark and product-gate report.

Failure of slice 1 blocks the remaining CodeWiki-based plan and returns the design for revision; it does not authorize importing CodeWiki internals.

## 18. Testing strategy

1. Unit tests for models, validators, ranking, budgets, and serializers.
2. YAML round-trip and schema compatibility tests.
3. EvidenceProvider contract tests with a fake provider and CodeWiki fixture adapter.
4. Golden tests for Wiki Markdown, Cards, Mermaid, and standalone HTML.
5. Incremental fixture tests for modified, added, deleted, renamed, dirty files, provider-index failure, stale-view policy, model-independent deterministic retirement, and inconclusive retirement checks.
6. CLI tests for the exact Agent lease/submission commands, progress summaries, exit codes, partial runs, idempotency, and interruption recovery.
7. MCP tests for all seven tools, repository-boundary enforcement, generation/snapshot mismatch fail-closed behavior, and explicit stale diagnostics.
8. Shared RunOrchestrator request/result contract tests using deterministic fake semantic workers and simulated Agent submissions.
9. Publish-journal crash tests at each canonical/plan/Card/FTS/manifest swap point, including startup recovery.
10. Opt-in live tests for Codex Skill and LiteLLM; CI does not require paid model calls.

## 19. Agent A/B benchmark

Run baseline and experimental agents on the same fixed repository commit, model, task, timeout, and tool permissions.

Baseline:

```text
Agent + repository
```

Experimental:

```text
Agent + repository + Knowledge Compiler
```

Tasks cover module explanation, end-to-end flow tracing, impact analysis, API parameter changes, business-rule changes, and a seeded bug fix.

Record task success, resulting code/tests, tool calls, read/search/grep counts, input and retrieved tokens, time to first valid edit, objects consumed, and knowledge-caused errors.

## 20. Acceptance criteria

### 20.1 Technical Definition of Done

- One local Git repository can complete build and update.
- Both execution modes satisfy the shared request/result contracts and RunOrchestrator state machine.
- All five object types can be generated.
- Every factual field is backed by verified Claims, and every required Claim contains Evidence references.
- Structural and semantic validation run successfully.
- Repo Wiki Markdown, standalone HTML, Cards, and task context compile.
- Incremental invalidation and selective rebuild work on fixtures.
- CLI and all seven MCP tools are usable.
- Automated tests pass.
- The benchmark and its report are repeatable.

### 20.2 Product hypothesis gate

- Structural validity of Evidence IDs, paths, and line ranges is 100%.
- A manual sample of at least 50 claims has at least 90% source support.
- Critical Wiki conclusions have source citations.
- Agent task success improves, or success remains equivalent while repository-exploration tool calls decrease by at least 25%.
- Stale and conflicted knowledge never enters default task context.

Meeting the technical definition without meeting the product gate yields a completed experiment, not evidence to expand product scope. The next iteration must first address Evidence quality, IR design, validation, or context selection.

## 21. Evolution path

- V0.1: one local Git repository and the complete evidence-to-context loop.
- V0.1.x: Git URL RepositoryProvider, clone cache, branch selection, and private-repository credentials.
- V0.2: multi-repository workspaces and cross-repository flows.
- Later: human edits and governance, Git/PR decisions, issues/incidents, and non-code enterprise knowledge.

These future items influence interface boundaries but add no speculative implementation to V0.1.

---

# 第四编：Phase 0 CodeWiki Adapter Spike 实施计划（原文）

> 本编是下一阶段唯一已批准的执行计划。它是 Go/No-Go Gate，不是完整产品实现计划。

# CodeWiki Public-Surface Adapter Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove whether CodeWiki 0.6.x public CLI, MCP, or HTTP surfaces can supply every fact required by the Knowledge Compiler `EvidenceProvider` contract without importing CodeWiki internals or reading its database.

**Architecture:** Build a disposable probe around a committed miniature Python repository. The probe records raw public-surface observations, normalizes capability evidence, and writes a deterministic Go/No-Go report. CLI is tested first; MCP is tested only for capabilities missing from CLI. Product feature work is blocked until this plan yields `decision: go`.

**Tech Stack:** Python 3.12, uv, Pydantic 2, pytest, Typer, official MCP Python SDK, Git CLI, CodeWiki 0.6.x

**Spec:** `docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md`

## Global Constraints

- Target Python 3.12 and CodeWiki `>=0.6,<0.7`.
- Use only documented CodeWiki CLI, MCP, or HTTP surfaces.
- Never import `backend.*`, `codewiki.*` implementation modules, or query CodeWiki SQLite/PostgreSQL tables.
- Never execute source code, tests, build scripts, or dependency installation from the probe repository.
- Keep `.knowledge/`, `.codewiki/`, `.git/`, dependencies, binaries, and oversize files outside the eligible source inventory.
- Raw observations go under ignored `work/codewiki-spike/`; only sanitized contract fixtures and the decision report enter Git.
- Do not begin Knowledge IR, compiler, orchestration, or MCP product implementation in this plan.
- A missing or ambiguous capability produces `decision: no_go`; it must not be patched by accessing CodeWiki internals.

---

## Planned file structure

```text
pyproject.toml                              # Package metadata and spike-only dependencies
src/knowledge_compiler/__init__.py         # Package version
src/knowledge_compiler/spikes/
├── __init__.py                            # Spike package marker
├── fixture_repo.py                        # Materialize and commit the deterministic probe repository
├── observations.py                        # Command/MCP observation data models and sanitization
├── cli_probe.py                           # CodeWiki CLI runner
├── mcp_probe.py                           # Public MCP fallback runner
├── evaluator.py                           # Required-capability evaluation and decision model
└── main.py                                # Typer entry point and report orchestration
tests/
├── fixtures/probe_repo/                   # Static source tree copied into a temporary Git repo
│   ├── pyproject.toml
│   └── src/shop/
│       ├── __init__.py
│       ├── api.py
│       ├── checkout.py
│       └── inventory.py
├── spikes/
│   ├── test_fixture_repo.py
│   ├── test_observations.py
│   ├── test_cli_probe.py
│   ├── test_mcp_probe.py
│   └── test_evaluator.py
└── support/fake_codewiki.py               # Deterministic fake executable for unit tests
tests/fixtures/codewiki/0.6/               # Sanitized live public-surface JSON fixtures
docs/spikes/codewiki-public-surface.md      # Generated Go/No-Go evidence report
work/codewiki-spike/                        # Ignored raw live observations
```

## Required capability matrix

The evaluator must require all rows before returning `go`:

| Capability | Minimum observable evidence |
|---|---|
| Version | Parseable CodeWiki version in the 0.6 minor series |
| Repository registration | Public surface returns a stable repository identifier or unambiguous path identity |
| Full indexing | Public surface reports successful analysis for the committed probe snapshot |
| Repository survey | Eligible file paths and detected Python language are machine-readable |
| Symbols | `CheckoutService.checkout` and `Inventory.reserve` are machine-readable with source paths/ranges |
| Imports | The local import from checkout to inventory is observable |
| Calls | The call from checkout to `Inventory.reserve` is observable, with confidence/provenance when supplied |
| Source references | At least path, start line, and end line are available for a selected symbol |
| Topic exploration | A bounded query for `checkout inventory` returns relevant nodes or source references |
| Affected files/symbols | Supplying `src/shop/inventory.py` returns an affected result that includes checkout or its caller relationship |
| Incremental catch-up | After a non-executed source edit, public update succeeds and the new snapshot is queryable |
| Bounded machine output | The selected surface returns parseable JSON or MCP structured content without scraping human terminal text |

---

### Task 1: Bootstrap the spike harness and deterministic Git fixture

**Files:**
- Create: `pyproject.toml`
- Create: `src/knowledge_compiler/__init__.py`
- Create: `src/knowledge_compiler/spikes/__init__.py`
- Create: `src/knowledge_compiler/spikes/fixture_repo.py`
- Create: `tests/fixtures/probe_repo/pyproject.toml`
- Create: `tests/fixtures/probe_repo/src/shop/__init__.py`
- Create: `tests/fixtures/probe_repo/src/shop/api.py`
- Create: `tests/fixtures/probe_repo/src/shop/checkout.py`
- Create: `tests/fixtures/probe_repo/src/shop/inventory.py`
- Create: `tests/spikes/test_fixture_repo.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: none
- Produces: `materialize_probe_repo(template: Path, destination: Path) -> ProbeRepository`
- Produces: `ProbeRepository(root: Path, commit: str, eligible_files: tuple[str, ...])`

- [ ] **Step 1: Add the minimal package configuration**

```toml
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
name = "knowledge-compiler"
version = "0.1.0.dev0"
requires-python = ">=3.12"
dependencies = [
  "mcp>=1.0",
  "pydantic>=2.10",
  "typer>=0.15",
]

[project.optional-dependencies]
dev = [
  "codewiki>=0.6,<0.7",
  "pytest>=8.3",
  "pytest-cov>=6.0",
]

[project.scripts]
knowledge-codewiki-spike = "knowledge_compiler.spikes.main:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.hatch.build.targets.wheel]
packages = ["src/knowledge_compiler"]
```

Add `__version__ = "0.1.0.dev0"` to `src/knowledge_compiler/__init__.py`, and leave `spikes/__init__.py` empty.

- [ ] **Step 2: Add the static probe repository**

`tests/fixtures/probe_repo/src/shop/inventory.py`:

```python
class Inventory:
    def reserve(self, sku: str, quantity: int) -> bool:
        return bool(sku) and quantity > 0
```

`tests/fixtures/probe_repo/src/shop/checkout.py`:

```python
from shop.inventory import Inventory


class CheckoutService:
    def __init__(self, inventory: Inventory) -> None:
        self.inventory = inventory

    def checkout(self, sku: str, quantity: int) -> str:
        if not self.inventory.reserve(sku, quantity):
            raise ValueError("inventory reservation failed")
        return "order-created"
```

`tests/fixtures/probe_repo/src/shop/api.py`:

```python
from shop.checkout import CheckoutService
from shop.inventory import Inventory


def checkout_order(sku: str, quantity: int) -> str:
    return CheckoutService(Inventory()).checkout(sku, quantity)
```

`tests/fixtures/probe_repo/src/shop/__init__.py` is empty. The fixture `pyproject.toml` contains:

```toml
[project]
name = "codewiki-probe-shop"
version = "0.0.0"
requires-python = ">=3.12"
```

- [ ] **Step 3: Write the failing fixture-materialization test**

```python
from pathlib import Path
import subprocess

from knowledge_compiler.spikes.fixture_repo import materialize_probe_repo


def test_materialize_probe_repo_creates_committed_snapshot(tmp_path: Path) -> None:
    template = Path("tests/fixtures/probe_repo")
    repo = materialize_probe_repo(template, tmp_path / "probe")

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo.root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()

    assert repo.commit == head
    assert repo.eligible_files == (
        "pyproject.toml",
        "src/shop/__init__.py",
        "src/shop/api.py",
        "src/shop/checkout.py",
        "src/shop/inventory.py",
    )
```

- [ ] **Step 4: Run the test and verify it fails**

Run: `uv run pytest tests/spikes/test_fixture_repo.py -v`

Expected: FAIL because `knowledge_compiler.spikes.fixture_repo` does not exist.

- [ ] **Step 5: Implement repository materialization**

```python
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


@dataclass(frozen=True)
class ProbeRepository:
    root: Path
    commit: str
    eligible_files: tuple[str, ...]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def materialize_probe_repo(template: Path, destination: Path) -> ProbeRepository:
    shutil.copytree(template, destination)
    _git(destination, "init", "-q")
    _git(destination, "config", "user.name", "Knowledge Compiler Spike")
    _git(destination, "config", "user.email", "spike@example.invalid")
    _git(destination, "add", ".")
    _git(destination, "commit", "-q", "-m", "fixture: initial repository")
    files = tuple(
        line
        for line in _git(destination, "ls-files").splitlines()
        if line and not line.startswith((".knowledge/", ".codewiki/"))
    )
    return ProbeRepository(destination, _git(destination, "rev-parse", "HEAD"), files)
```

- [ ] **Step 6: Ignore raw spike output and verify the test passes**

Add to `.gitignore`:

```gitignore
work/
.coverage
.pytest_cache/
__pycache__/
*.pyc
```

Run: `uv run pytest tests/spikes/test_fixture_repo.py -v`

Expected: PASS.

- [ ] **Step 7: Commit the fixture harness**

```bash
git add pyproject.toml src/knowledge_compiler tests/fixtures tests/spikes/test_fixture_repo.py .gitignore
git commit -m "test: add deterministic CodeWiki probe repository"
```

---

### Task 2: Model and sanitize public-surface observations

**Files:**
- Create: `src/knowledge_compiler/spikes/observations.py`
- Create: `tests/spikes/test_observations.py`

**Interfaces:**
- Consumes: `ProbeRepository`
- Produces: `CommandObservation`, `McpObservation`, `ProbeBundle`
- Produces: `sanitize_text(text: str, repo_root: Path) -> str`
- Produces: `write_bundle(bundle: ProbeBundle, path: Path) -> None`

- [ ] **Step 1: Write failing tests for path and secret sanitization**

```python
from pathlib import Path

from knowledge_compiler.spikes.observations import sanitize_text


def test_sanitize_text_replaces_repo_path_and_api_key() -> None:
    root = Path("/private/tmp/probe")
    value = "path=/private/tmp/probe/src/app.py api_key=<REDACTED-SYNTHETIC-FIXTURE>"

    sanitized = sanitize_text(value, root)

    assert sanitized == "path=<REPO>/src/app.py api_key=<REDACTED>"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/spikes/test_observations.py -v`

Expected: FAIL because `observations.py` does not exist.

- [ ] **Step 3: Implement the observation models and sanitizer**

```python
from pathlib import Path
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field


class CommandObservation(BaseModel):
    name: str
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    json_value: Any | None = None


class McpObservation(BaseModel):
    name: str
    tool_name: str
    arguments: dict[str, Any]
    is_error: bool
    structured_content: Any | None = None
    text_content: list[str] = []


class ProbeBundle(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    codewiki_version: str | None
    repository_commit: str
    commands: list[CommandObservation]
    mcp: list[McpObservation] = Field(default_factory=list)


SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s]+)")


def sanitize_text(text: str, repo_root: Path) -> str:
    sanitized = text.replace(str(repo_root), "<REPO>")
    return SECRET_PATTERN.sub(r"\1<REDACTED>", sanitized)


def write_bundle(bundle: ProbeBundle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
```

- [ ] **Step 4: Add round-trip tests and run them**

Add a test that constructs a `ProbeBundle`, writes it with `write_bundle`, reloads the JSON, and asserts `schema_version == "0.1"` and no absolute repository path remains.

Run: `uv run pytest tests/spikes/test_observations.py -v`

Expected: PASS.

- [ ] **Step 5: Commit observation capture**

```bash
git add src/knowledge_compiler/spikes/observations.py tests/spikes/test_observations.py
git commit -m "feat: add sanitized CodeWiki probe observations"
```

---

### Task 3: Probe the documented CodeWiki CLI surface

**Files:**
- Create: `src/knowledge_compiler/spikes/cli_probe.py`
- Create: `tests/support/fake_codewiki.py`
- Create: `tests/spikes/test_cli_probe.py`

**Interfaces:**
- Consumes: `ProbeRepository`, CodeWiki executable path
- Produces: `run_cli_probe(executable: str, repo: ProbeRepository) -> list[CommandObservation]`

- [ ] **Step 1: Write a fake CodeWiki executable**

The fake script must inspect `sys.argv[1:]` and emit JSON for these command families: version, repository add, analyze, scan, graph search/explore/affected, and update. It returns exit code 2 for unknown commands. Use only fixture paths supplied in arguments; do not read production files.

```python
#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("codewiki 0.6.5")
elif args[:2] == ["repos", "add"]:
    print(json.dumps({"repository": {"id": "probe-repo", "path": args[2]}}))
elif args and args[0] == "analyze":
    print(json.dumps({"status": "completed", "repository_id": "probe-repo"}))
elif args[:2] == ["repos", "scan"]:
    print(json.dumps({"files": [
        {"path": "src/shop/checkout.py", "language": "python"},
        {"path": "src/shop/inventory.py", "language": "python"}
    ]}))
elif args[:2] == ["graph", "search"]:
    print(json.dumps({"nodes": [{"name": "CheckoutService", "path": "src/shop/checkout.py"}]}))
elif args[:2] == ["graph", "explore"]:
    print(json.dumps({"nodes": [], "edges": [], "sources": []}))
elif args[:2] == ["graph", "affected"]:
    print(json.dumps({"affected": ["src/shop/checkout.py"]}))
elif args and args[0] == "update":
    print(json.dumps({"status": "completed"}))
else:
    print(json.dumps({"error": "unsupported", "args": args}))
    raise SystemExit(2)
```

- [ ] **Step 2: Write the failing CLI probe test**

```python
from pathlib import Path

from knowledge_compiler.spikes.cli_probe import run_cli_probe
from knowledge_compiler.spikes.fixture_repo import materialize_probe_repo


def test_run_cli_probe_records_every_documented_command(tmp_path: Path) -> None:
    repo = materialize_probe_repo(Path("tests/fixtures/probe_repo"), tmp_path / "repo")
    observations = run_cli_probe("tests/support/fake_codewiki.py", repo)

    names = {item.name for item in observations}
    assert {
        "version", "repos_add", "analyze", "repos_scan",
        "graph_search", "graph_explore", "graph_affected", "update",
    } <= names
    assert all(item.json_value is not None or item.name == "version" for item in observations)
```

- [ ] **Step 3: Run the test and verify it fails**

Run: `chmod +x tests/support/fake_codewiki.py && uv run pytest tests/spikes/test_cli_probe.py -v`

Expected: FAIL because `cli_probe.py` does not exist.

- [ ] **Step 4: Implement the CLI runner**

Implement one private `_run()` that executes with `shell=False`, a 120-second timeout, captured text output, and an explicit environment. It must parse stdout as JSON when possible and always record failure observations rather than raising for non-zero CodeWiki exit codes.

The public probe runs these documented candidates in order:

```python
commands = [
    ("version", ["--version"]),
    ("repos_add", ["repos", "add", str(repo.root), "--json"]),
    ("analyze", ["analyze", str(repo.root), "--json"]),
    ("repos_scan", ["repos", "scan", str(repo.root), "--json"]),
    ("graph_search", ["graph", "search", "CheckoutService", "--repo", str(repo.root), "--json"]),
    ("graph_explore", ["graph", "explore", "checkout inventory", "--repo", str(repo.root), "--json"]),
]
```

For affected analysis, send `src/shop/inventory.py\n` to stdin using:

```python
["graph", "affected", "--repo", str(repo.root), "--stdin", "--json"]
```

Then append a comment-only line to `src/shop/inventory.py`, run:

```python
["update", str(repo.root), "--json"]
```

and repeat graph search as `graph_search_after_update`. Do not import or execute any code from the probe repository.

- [ ] **Step 5: Run CLI tests and verify behavior**

Run: `uv run pytest tests/spikes/test_cli_probe.py -v`

Expected: PASS with the fake executable. A non-zero fake response must remain in the observation list with its stderr and return code.

- [ ] **Step 6: Commit the CLI probe**

```bash
git add src/knowledge_compiler/spikes/cli_probe.py tests/support/fake_codewiki.py tests/spikes/test_cli_probe.py
git commit -m "feat: probe CodeWiki public CLI capabilities"
```

---

### Task 4: Add MCP fallback discovery without coupling to CodeWiki internals

**Files:**
- Create: `src/knowledge_compiler/spikes/mcp_probe.py`
- Create: `tests/spikes/test_mcp_probe.py`

**Interfaces:**
- Consumes: CodeWiki executable, `ProbeRepository`, missing CLI capability names
- Produces: `run_mcp_probe(executable: str, repo: ProbeRepository, required: set[str]) -> list[McpObservation]`

- [ ] **Step 1: Write a failing tool-selection test**

```python
from knowledge_compiler.spikes.mcp_probe import select_tools


def test_select_tools_matches_public_capabilities() -> None:
    tools = [
        "codewiki_graph_search",
        "codewiki_graph_explore",
        "codewiki_graph_affected",
        "codewiki_files",
    ]
    selected = select_tools(tools, {"symbols", "topic_exploration", "affected"})

    assert selected == {
        "symbols": "codewiki_graph_search",
        "topic_exploration": "codewiki_graph_explore",
        "affected": "codewiki_graph_affected",
    }
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/spikes/test_mcp_probe.py -v`

Expected: FAIL because `mcp_probe.py` does not exist.

- [ ] **Step 3: Implement deterministic public-tool selection**

```python
TOOL_CANDIDATES = {
    "survey": ("codewiki_files", "codewiki_indexed_files"),
    "symbols": ("codewiki_graph_search", "codewiki_search"),
    "topic_exploration": ("codewiki_graph_explore", "codewiki_context"),
    "affected": ("codewiki_graph_affected", "codewiki_affected"),
    "source_references": ("codewiki_node", "codewiki_graph_search"),
}


def select_tools(available: list[str], required: set[str]) -> dict[str, str]:
    available_set = set(available)
    return {
        capability: next(name for name in TOOL_CANDIDATES[capability] if name in available_set)
        for capability in sorted(required)
        if any(name in available_set for name in TOOL_CANDIDATES[capability])
    }
```

- [ ] **Step 4: Implement MCP list/call orchestration**

Use the official SDK's stdio client with server command `codewiki` and arguments `mcp --lite --path <repo>`. Call `session.initialize()`, then `session.list_tools()`. Only call selected tools for CLI-missing capabilities. Use these bounded arguments:

```python
arguments = {
    "survey": {"path": str(repo.root)},
    "symbols": {"query": "CheckoutService", "limit": 10},
    "topic_exploration": {"query": "checkout inventory", "max_hops": 2},
    "affected": {"files": ["src/shop/inventory.py"]},
    "source_references": {"query": "Inventory.reserve", "limit": 10},
}
```

If a discovered tool rejects an argument shape, record the structured MCP error and retry once using only fields declared by the tool's `inputSchema`. Never scrape text to invent missing fields.

- [ ] **Step 5: Test with a fake MCP session**

Create an in-test fake session exposing `list_tools()` and `call_tool()`; assert the probe calls only required capabilities, applies `limit <= 10`, and records structured content and errors.

Run: `uv run pytest tests/spikes/test_mcp_probe.py -v`

Expected: PASS.

- [ ] **Step 6: Commit MCP fallback discovery**

```bash
git add src/knowledge_compiler/spikes/mcp_probe.py tests/spikes/test_mcp_probe.py
git commit -m "feat: add CodeWiki MCP capability fallback"
```

---

### Task 5: Evaluate capabilities and generate the Go/No-Go report

**Files:**
- Create: `src/knowledge_compiler/spikes/evaluator.py`
- Create: `src/knowledge_compiler/spikes/main.py`
- Create: `tests/spikes/test_evaluator.py`

**Interfaces:**
- Consumes: `ProbeBundle`
- Produces: `CapabilityResult`, `SpikeDecision`
- Produces: `evaluate(bundle: ProbeBundle) -> SpikeDecision`
- Produces: CLI `knowledge-codewiki-spike run --repo-template ... --work-dir ... --report ...`

- [ ] **Step 1: Define evaluator examples as failing tests**

```python
from knowledge_compiler.spikes.evaluator import evaluate
from knowledge_compiler.spikes.observations import ProbeBundle


def test_evaluate_returns_no_go_when_calls_are_missing(complete_bundle_dict: dict) -> None:
    bundle = ProbeBundle.model_validate(complete_bundle_dict)
    for command in bundle.commands:
        if command.name == "graph_explore":
            command.json_value = {"nodes": [], "edges": [], "sources": []}
    decision = evaluate(bundle)

    assert decision.decision == "no_go"
    assert "calls" in decision.missing_capabilities


def test_evaluate_returns_go_for_complete_public_contract(complete_bundle_dict: dict) -> None:
    decision = evaluate(ProbeBundle.model_validate(complete_bundle_dict))

    assert decision.decision == "go"
    assert decision.missing_capabilities == []
```

The `complete_bundle_dict` fixture must contain explicit machine-readable files, symbols, imports, calls, source ranges, topic hits, affected results, and post-update results. Do not use a blanket `success: true` fixture.

- [ ] **Step 2: Run the evaluator tests and verify they fail**

Run: `uv run pytest tests/spikes/test_evaluator.py -v`

Expected: FAIL because `evaluator.py` does not exist.

- [ ] **Step 3: Implement capability evidence extraction**

Create one evaluator function per capability. Each returns evidence references into the bundle, not prose guesses:

```python
CAPABILITIES = (
    "version",
    "repository_registration",
    "full_index",
    "repository_survey",
    "symbols",
    "imports",
    "calls",
    "source_references",
    "topic_exploration",
    "affected",
    "incremental_update",
    "bounded_machine_output",
)
```

`SpikeDecision.decision` is `go` only when every `CapabilityResult.status == "supported"`. `ambiguous`, `missing`, provider error, or human-text-only output all map to `no_go`.

- [ ] **Step 4: Implement the CLI orchestration**

The `run` command must:

1. materialize a fresh committed probe repository under the work directory;
2. execute the CLI probe;
3. evaluate preliminary missing capabilities;
4. execute MCP fallback only for those missing capabilities;
5. evaluate the merged bundle;
6. write sanitized raw bundle JSON under the work directory;
7. write a Markdown decision report with version, command table, capability table, missing capabilities, selected public surface, and exact decision;
8. exit `0` for `go`, `2` for `no_go`, and `1` for probe infrastructure failure.

Use this report header and ensure every section is populated from models:

```markdown
# CodeWiki Public-Surface Spike

- CodeWiki version: `<sanitized value>`
- Probe repository commit: `<fixture commit>`
- Decision: `go|no_go`

## CLI observations
## MCP fallback observations
## Capability matrix
## Missing or ambiguous capabilities
## Adapter recommendation
```

- [ ] **Step 5: Run all unit tests**

Run: `uv run pytest tests/spikes -v`

Expected: PASS with no real CodeWiki process required.

- [ ] **Step 6: Commit the evaluator and entry point**

```bash
git add src/knowledge_compiler/spikes/evaluator.py src/knowledge_compiler/spikes/main.py tests/spikes/test_evaluator.py
git commit -m "feat: evaluate CodeWiki adapter go-no-go gate"
```

---

### Task 6: Run the live CodeWiki 0.6 spike and freeze the public contract

**Files:**
- Create: `tests/fixtures/codewiki/0.6/cli-observations.json`
- Create: `tests/fixtures/codewiki/0.6/mcp-observations.json` when MCP fallback is used
- Create: `docs/spikes/codewiki-public-surface.md`
- Modify: `tests/spikes/test_cli_probe.py`
- Modify: `tests/spikes/test_mcp_probe.py` when MCP fallback is used

**Interfaces:**
- Consumes: Tasks 1-5 and an installed CodeWiki 0.6.x executable
- Produces: sanitized compatibility fixtures and a definitive `go` or `no_go` report
- Gate: product implementation planning proceeds only for `go`

- [ ] **Step 1: Install the isolated development environment**

Run:

```bash
uv sync --extra dev
uv run codewiki --version
```

Expected: CodeWiki reports a version in the 0.6 minor series. If installation or version validation fails, record an infrastructure failure and stop this task.

- [ ] **Step 2: Run the live probe**

```bash
uv run knowledge-codewiki-spike run \
  --repo-template tests/fixtures/probe_repo \
  --work-dir work/codewiki-spike/live-0.6 \
  --report docs/spikes/codewiki-public-surface.md
```

Expected: exit `0` with `Decision: go`, or exit `2` with a complete `Decision: no_go` report. Both are valid spike outcomes; only `go` authorizes the next product plan.

- [ ] **Step 3: Inspect raw observations for secrets and unstable paths**

Run:

```bash
rg -n "/Users/|/private/|api[_-]?key|sk-[A-Za-z0-9]" work/codewiki-spike/live-0.6 docs/spikes/codewiki-public-surface.md
```

Expected: no secret value and no absolute user path. Sanitized labels such as `<REPO>` and `<REDACTED>` are allowed.

- [ ] **Step 4: Freeze sanitized public contract fixtures**

Copy only the sanitizer-approved CLI and MCP observation models into `tests/fixtures/codewiki/0.6/`. Add regression tests that load these fixtures and assert `evaluate(...)` returns the same decision recorded in the report.

Run: `uv run pytest tests/spikes -v`

Expected: PASS against both fake and captured public-surface fixtures.

- [ ] **Step 5: Verify the public-boundary rule mechanically**

Run:

```bash
rg -n "from (backend|codewiki)\.|import (backend|codewiki)|sqlite3|aiosqlite|SELECT .*code_(node|edge|chunk)" src tests
```

Expected: no matches in implementation code. Mentions inside captured help/output fixtures may be reviewed manually and must not correspond to executable imports or queries.

- [ ] **Step 6: Run the full verification suite**

```bash
uv run pytest -v
git diff --check
git status --short
```

Expected: all tests pass, diff check is clean, and only intended spike fixtures/report changes remain.

- [ ] **Step 7: Commit the live decision**

For a Go result:

```bash
git add tests/fixtures/codewiki/0.6 docs/spikes/codewiki-public-surface.md tests/spikes
git commit -m "test: verify CodeWiki 0.6 public adapter contract"
```

For a No-Go result:

```bash
git add tests/fixtures/codewiki/0.6 docs/spikes/codewiki-public-surface.md tests/spikes
git commit -m "docs: record CodeWiki public adapter no-go"
```

- [ ] **Step 8: Apply the gate**

If the report says `go`, create the next implementation plan from the captured normalized DTO shapes, beginning with the Fake Provider vertical slice in design section 17.

If it says `no_go`, stop. Present the exact missing capabilities to the user and return the approved design for revision. Do not import CodeWiki internals, read its database, or start Knowledge IR implementation.

---

## [HISTORICAL / COMPLETED] Plan completion checks

> 这是 Phase 0 计划中的历史验收清单，已由当前仓库的 Spike 报告取代，不是待执行任务。

- [ ] Every required CodeWiki capability has direct public-surface evidence or is listed missing.
- [ ] The decision is derived from the evaluator and reproducible from committed sanitized fixtures.
- [ ] Absolute paths, credentials, raw caches, and databases are absent from Git.
- [ ] No CodeWiki implementation import or database query exists.
- [ ] `pytest`, `git diff --check`, and the boundary scan pass.
- [ ] The next plan is created only after a `go` decision.

---

# 第五编：[HISTORICAL / COMPLETED] 迁移验证清单

> 以下是跨电脑迁移时使用的旧清单，迁移与 Phase 0 均已完成。保留它是为了审计历史，不要执行。

当时要求在新电脑上开始工作前逐项确认：

- [ ] 已保存本归档原文件，没有通过聊天窗口复制导致截断；
- [ ] 已从第三编还原正式规格，并确认其标题、结论和完成定义完整；
- [ ] 已从第四编还原 Phase 0 计划；
- [ ] 已明确当前没有产品代码，不能假设 Adapter 已实现；
- [ ] 已重新核验 CodeWiki 当前版本与公开接口；
- [ ] 已确保 Spike 不导入 CodeWiki 内部模块、不读内部数据库；
- [ ] 已为 Spike 建立隔离环境和 fixture repository；
- [ ] 已按计划捕获原始公开接口响应、归一化 DTO 和失败案例；
- [ ] 已形成明确的 Go/Conditional Go/No-Go 报告（Conditional Go 为早期候选，最终合同仅保留 Go/No-Go）；
- [ ] 只有 Go 后才编写并执行 Phase 1 以后的实施计划。

## 归档完整性说明

本文件按以下固定顺序机械合并：

1. 跨电脑接续摘要与规则；
2. 当前 Codex 会话的用户/助手可见消息；
3. 前序 ChatGPT 完整研究归档原文；
4. 已批准 V0.1 正式规格原文；
5. Phase 0 CodeWiki Adapter Spike 实施计划原文；
6. 迁移验证清单。

原始 Markdown 中的链接、代码块和标题保持原文，因此内嵌文档的标题级别可能与总归档重复；这是为了保真，不代表优先级发生变化。
