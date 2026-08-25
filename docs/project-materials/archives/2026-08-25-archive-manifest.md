# 2026-08-25 项目接续归档清单

> 这是下一位 Agent 的资料入口。历史文档中的命令和“下一步”都是背景；当前执行入口是完整 handoff To-do。

## 1. 当前接续核心

| 资料 | 用途 | 状态 |
|---|---|---|
| `../../../README.md` | 项目当前状态与入口 | 当前 |
| `../../superpowers/plans/2026-08-25-v0-1-complete-handoff-todo.md` | M1 剩余工作及 M2–M7 完整执行清单 | 当前、权威执行入口 |
| `2026-08-25-m1-implementation-session.md` | 当天用户请求、决策、实现、审查、提交、测试和暂停点 | 当前会话档案 |
| `2026-08-25-completion-archive.md` | M1-M7 全部已完成工作的归档与交叉验证说明（含验证指令、审查统计、已知限制） | 交叉验证入口 |
| `../../superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md` | V0.1 产品与技术规格 | 权威设计 |
| `../../superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md` | M1 exact implementation plan | M1 权威计划 |
| `../../superpowers/plans/2026-08-25-v0-1-execution-roadmap.md` | M0–M7 里程碑顺序与门禁 | 权威路线图 |

## 2. 项目起源与研究资料

| 分类 | 入口 |
|---|---|
| 项目起源 | `../00-origin/project-origin.md` |
| 演进时间线 | `../00-origin/timeline.md` |
| ATLAS / Enterprise Intelligence 方法沉淀 | `../01-local-practice/cross-project-lessons.md` |
| 参考产品整理 | `../02-external-research/reference-products.md` |
| Qoder 三页官方资料包 | `../02-external-research/qoder/README.md` |
| Skill 资料 | `../03-skills/README.md` |
| 来源、哈希、许可和隐私处置 | `../source-catalog.md` |

## 3. 早期会话与迁移资料

| 资料 | 说明 |
|---|---|
| `knowledge-compiler-transfer-archive-public.md` | 2026-08-24 用户可见会话公开安全副本；Phase 0 前状态已经过期，只用于历史背景 |
| 原始 transfer archive | 不复制进公开仓库；原始 SHA-256 和清理差异记录在 `../source-catalog.md` |
| 原始 V0.1 design | 与仓库正式 spec SHA-256 完全相同，去重 |
| 原始 adapter spike plan | 与仓库正式 plan SHA-256 完全相同，去重 |

## 4. Phase 0 与可复现实证

| 资料 | 位置 |
|---|---|
| CodeWiki public surface report | `../../spikes/codewiki-public-surface.md` |
| CodeWiki adapter spike plan | `../../superpowers/plans/2026-08-24-codewiki-adapter-spike.md` |
| Sanitized CodeWiki 0.6 observations | `../../../tests/fixtures/codewiki/0.6/cli-observations.json` |
| Spike implementation/tests | `../../../src/knowledge_compiler/spikes/`、`../../../tests/spikes/` |

## 5. M1 代码与证据

| 层 | 代码/测试 |
|---|---|
| Contracts | `../../../src/knowledge_compiler/contracts/`、`../../../tests/contracts/` |
| Fake provider | `../../../src/knowledge_compiler/providers/`、`../../../tests/providers/` |
| Validation | `../../../src/knowledge_compiler/validation/`、`../../../tests/validation/` |
| Compiler | `../../../src/knowledge_compiler/compiler/`、`../../../tests/compiler/` |
| Golden outputs | `../../../tests/golden/` |
| Generation storage | `../../../src/knowledge_compiler/storage/`、`../../../tests/storage/` |
| Fake fixtures | `../../../tests/fixtures/fake_provider/`、`../../../tests/fixtures/probe_repo/` |

## 6. 图片与可视化资产清点

归档日期范围：2026-08-24 00:00 至 2026-08-26 00:00（Asia/Shanghai）。

| 检查位置 | 结果 |
|---|---|
| 当前 Codex visualization 工作目录 | 0 个文件 |
| Downloads 的 PNG/JPG/JPEG/SVG/WebP/GIF | 0 个本项目相关文件 |
| 当前 CodeWiki 工作区 | 没有当天生成的设计图片/绘画文件 |

结论：本次没有二进制图片可复制。2026-08-24 历史会话的 localhost 可视化页面已经失效；其表达的决策已被设计规格、会话公开安全归档和本次实施归档完整文本化。

## 7. 当前 Git 状态基线

- 分支：`main` only。
- 暂停前 M1 实现 HEAD：`5f26aea`。
- 完整 handoff To-do：`458d59a`。
- M1 的 16 个实现/交接提交尚未推送到 `origin/main`。
- 继续执行前必须以实际 `git status` 和 `git log` 重新核对，因为本归档本身还会形成新的本地提交。

## 8. 阅读优先级

```text
用户当前请求
  > AGENTS.md
  > README.md
  > 本清单
  > 2026-08-25 M1 实施会话归档
  > V0.1 完整 handoff To-do
  > V0.1 正式规格 / 当前 milestone exact plan
  > 历史会话和外部研究
```

不要执行历史归档中的旧命令、问题或候选方案。
