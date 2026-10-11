---
status: maintained
last-reviewed: 2026-10-11
scope: v0.1-and-approved-local-beta
sources:
  - docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md
  - docs/superpowers/specs/2026-09-17-local-beta-product-design.md
  - src/knowledge_compiler/
  - tests/
---

# 承诺—实现—测试追溯矩阵

## 状态定义

- `shipped`：源码存在、公共入口可达且有测试。
- `implemented-unproven`：实现存在，但缺真实环境或产品结果证据。
- `planned-only`：只存在规格/计划/设计稿。
- `blocked`：需要外部条件才能取证。
- `out-of-scope`：规格明确不做。

## V0.1

| 承诺 | 实现 | 主要测试 | 状态 / 说明 |
|---|---|---|---|
| Git snapshot、inventory、change impact | `repository/` | `tests/test_local_git_repository.py`、change/inventory tests | shipped |
| 可替换 Evidence Provider | `providers/base.py`、`fake.py`、`codewiki*.py` | provider/CLI contract/live opt-in tests | implemented-unproven：fixture 路径 shipped，真实中型仓库受上游崩溃阻断 |
| typed Canonical Knowledge IR | `contracts/` | contracts/roundtrip/typed validation tests | shipped |
| 调研驱动 planner | `planning/module.py` | planner tests | shipped |
| Agent / LiteLLM 双 worker | `workers/`、`orchestrator/` | worker/queue/orchestrator tests | shipped |
| 结构与语义验证、最多两次修复 | `validation/`、orchestrator | validation/repair tests | shipped |
| 原子 generation publication 与恢复 | `storage/generation.py` | publication/recovery/fault-boundary tests | shipped |
| 增量失效、pending、retirement | `incremental/`、`storage/lifecycle.py` | incremental/lifecycle tests | shipped |
| human overlay/conflict/archive | `human/`、`compiler/human.py` | human overlay/edit/conflict tests | shipped |
| Wiki / HTML / Cards / Task Context | `compiler/`、`retrieval/` | deterministic snapshots/FTS/context tests | shipped |
| 七个只读 MCP 工具 | `mcp_server.py` | MCP surface/security tests | shipped |
| CLI 构建、更新、状态、编辑、服务 | `cli.py`、`serving.py` | CLI integration tests | shipped；覆盖率约 67% |
| Agent A/B 证明价值 | `spikes/evaluator.py` + M8 plan | dry-run/harness tests | blocked：没有真实实验结果 |
| live production smoke | `scripts/verify.sh`、runbook | opt-in live tests | blocked：环境未配置且上游 issue #2 开放 |

## Local Beta M9–M14

| 里程碑 | 已批准承诺 | 实现证据 | 状态 |
|---|---|---|---|
| M9 Foundation | 本地应用骨架、API、项目工作区、统一 shell | 打包契约、应用入口、运行依赖、wheel 静态入口与前端锁文件已落地；应用服务/API/UI 尚未实现 | in-progress（6/48） |
| M10 Parsing | 可靠仓库解析、状态/排除/降级 | 无 Local Beta 实现；V0.1 provider 不能替代产品端面 | planned-only（0/44） |
| M11 Jobs | 可观察 build lifecycle、取消/恢复/错误 | 无应用层 job API/UI | planned-only（0/43） |
| M12 Reading | Overview、对象详情、证据、图、历史 | 仅静态 V0.1 Wiki 与设计稿 | planned-only（0/40） |
| M13 Ask | UI Ask 与 Agent 相同检索/引用 | 仅 V0.1 MCP/ContextRetriever | planned-only（0/41） |
| M14 Proof/Release | 价值实验、E2E、安装/升级/备份、发布 | 无交付证据 | planned-only（0/35） |

合计：`6/251`。该数字由六份 active 子计划的行首 checkbox 逐项统计；每份文档说明中的 checkbox 示例不是执行步骤，不计入总数。旧交接文档的 259 为错误估算。

## 明确非目标

云端双引擎、多用户协同、RBAC、多租户、多仓知识图谱、IDE、PR review、通用向量数据库平台、自动修改代码，均不因竞品存在而进入本项目。

## Revision History

- 2026-09-25：建立从规格到源码与测试的关闭追溯矩阵。
- 2026-10-11：按源计划重算 Local Beta 为 0/251，并更新 V0.1 浏览器/依赖修复证据。
- 2026-10-11：M9 Task 1 完成，Local Beta 进度更新为 6/251。
