# 来源目录与处置记录

记录日期：2026-08-24。

## 项目自有材料

| 来源 | SHA-256 / 版本 | 处置 | 仓库位置 |
|---|---|---|---|
| `knowledge_compiler_complete_transfer_archive_2026-08-24.md` | 原文件 `ac6d9ad09c6a886ad2a18dc231e1d45daa250eefd137570c2509862614671db4`；公开版 `f3cba5f2cd74c5054776573153f2aa858dd42f08802339454c7cd5895df8bc98` | 保存公开安全版；移除旧绝对路径、会话 ID、测试凭据字面量和失效 localhost 链接，并增加状态覆盖勘误 | `archives/knowledge-compiler-transfer-archive-public.md` |
| `knowledge-compiler-v0-1-design.md` | `efa29dce97367613aa389fd8f1312a287cdf4717a742c4fef24687d8b847c7c2` | 与正式规格逐字相同，去重 | `docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md` |
| `codewiki-adapter-spike-plan.md` | `355a3c23b09ffedee8de2b12b226d9c2eef6b09979f6515e1b0052814dd2ce3b` | 与正式计划逐字相同，去重 | `docs/superpowers/plans/2026-08-24-codewiki-adapter-spike.md` |
| Phase 0 实测 fixture | CodeWiki `0.6.5` | 原始结构化观测，已做路径/敏感信息清理 | `tests/fixtures/codewiki/0.6/cli-observations.json` |
| Phase 0 实验报告 | 当前分支 | 保留为公共合同研究结论 | `docs/spikes/codewiki-public-surface.md` |
| 2026-08-25 M1 实施会话归档 | 当天用户可见请求、提交、测试和审查记录的公开安全重建 | 保留实施与暂停上下文；不包含系统提示、内部推理、会话 ID 或凭据 | `archives/2026-08-25-m1-implementation-session.md` |
| 2026-08-25 完整接续 To-do | M1 剩余验收及 M2–M7 详细任务清单 | 作为跨 Agent 当前执行入口 | `docs/superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md` |
| 2026-08-25 归档清单 | 项目资料、代码证据和可视化资产清点 | 作为下一位 Agent 的资料导航 | `archives/2026-08-25-archive-manifest.md` |

## 本机关联项目

| 来源项目 | 阅读的资料类别 | 提取内容 | 未复制内容 |
|---|---|---|---|
| ATLAS（private） | 治理规范、跨库边界、来源映射、演进时间线、归档基线 | 状态、证据层级、来源追踪、稳定 ID、历史保留、跨库裁决方法 | 业务/组织事实、规划正文、原始素材、图片、内部路径与仓库快照 |
| Enterprise Intelligence（private） | 重建设计、AI 检索/维护指南、front matter schema、覆盖报告 | 事实层级、源码锚点、确定性合同、canonical-first 检索、发布门禁、覆盖诚实性 | 企业事实、代码对象、应用/数据库清单、业务指标、原始素材与机器索引 |

公开安全的提炼结果见 [跨项目方法沉淀](01-local-practice/cross-project-lessons.md)。两个私有项目只作为思想来源，不成为本项目运行时数据依赖。

本机还发现 Enterprise Intelligence 的主计划副本、根导航副本和完整压缩包。它们属于私有项目的重复或打包资产，可能包含企业事实和大量可生成内容，因此不复制到公开仓库；其方法层信息已经由私有工作区中的当前治理文档交叉核对后纳入上述摘要。ATLAS 的原始母本、演示资产和历史归档同理不复制。

## 第三方材料

| 来源 | 类型 | 核验日期 | 处置 |
|---|---|---|---|
| Google Code Wiki 官方博客 | 产品说明 | 2026-08-24 | 摘要 + 官方链接 |
| Qoder Repo Wiki 文档 | 产品文档 | 2026-08-24 | 页面级内容记录、抓取哈希、配置与行为整理 + 官方链接 |
| Qoder Knowledge Cards 文档 | 产品文档 | 2026-08-24 | 页面级内容记录、抓取哈希、类型/生成/共享整理 + 官方链接 |
| Qoder Repo Wiki 产品博客 | 官方博客 | 2026-08-24 | 多 Agent 生成、隐性知识和维护共享叙事整理 + 官方链接 |
| GitHub Copilot Memory 文档 | 产品文档 | 2026-08-24 | 摘要 + 官方链接 |
| PorunC/CodeWiki | MIT 开源仓库 | 2026-08-24 | 摘要、实测报告、固定提交 Skill + MIT 许可快照 |

早期归档还包含 Sourcegraph、Cursor、DeepWiki、Microsoft deep-wiki Skill 和 Qwen CodeScope 的概念性研究。由于原始材料没有完整保留每项的精确官方页面版本，它们被列为[次级研究线索](02-external-research/reference-products.md)，不伪装成已固定、可复现的来源快照。

## 公开仓库安全边界

下列信息即使存在于本机原始资料中，也不进入当前公开仓库：

- API Key、Token、密码、Cookie、私钥、连接串和签名 URL；
- 用户主目录、旧工作区绝对路径、任务/会话 ID 和只在本机有效的链接；
- ATLAS / Enterprise Intelligence 的真实业务数据、源码、系统清单、人员信息和内部结论；
- 未获再分发许可的第三方文档全文；
- 可重新生成的大型缓存、数据库、压缩包和二进制资产。

完整未清理原件继续留在其原始本机位置，不由本仓库复制或发布。

## 2026-08-25 图片与可视化清点

- 检查当前 Codex visualization 工作目录：未发现文件。
- 检查 Downloads 在 2026-08-24—25 形成的 PNG、JPG、JPEG、SVG、WebP、GIF：未发现本项目相关文件。
- 2026-08-24 早期会话曾引用 localhost 可视化伴侣，但没有可恢复的静态资产；链接已经失效。
- 可视化表达的产品决策与架构已在 V0.1 设计、公开安全会话归档和 2026-08-25 实施归档中以文本保留。
