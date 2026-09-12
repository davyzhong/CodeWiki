---
status: maintained
last-reviewed: 2026-09-12
sources:
  - src/knowledge_compiler/cli.py、cli_agent_queue.py、mcp_server.py、retrieval/context.py（as-built）
  - scripts/verify.sh
  - 根 README 快速上手
---

# 运行时行为参考（Behavior Reference）

命令、工具与门禁的实际语义。以 `--help` 与源码为最终权威，本文是速查。

## 入口点（pyproject scripts）

| 命令 | 入口 | 用途 |
|---|---|---|
| `knowledge` | `cli:app` | 主命令面 |
| `knowledge-mcp <repo-root>` | `mcp_server:main` | 七个只读 MCP 工具（stdio JSON-RPC） |
| `knowledge-codewiki-spike` | Phase 0 探针 | 公开面验证（历史工具） |
| `knowledge-realslice` / `knowledge-fake-module-slice` | M2/M1 演示 harness | 非生产 |

## 主命令面（`knowledge …`）

| 命令 | 语义 | 退出码 |
|---|---|---|
| `init --language zh\|en` | 幂等初始化配置与 .gitignore，不覆盖用户配置 | 0/1 |
| `build --executor llm\|agent` | 完整构建（preflight→快照→证据→规划→编排→发布→视图）；报告在 `.knowledge/state/runs/last-build.json` | 0 complete / 1 failed / 2 partial |
| `update --executor llm\|agent` | 增量更新（本地 ChangeSet 先行→原子失效→pending 重试→选择性重建→确定性退役） | 0/1/2 同上 |
| `status` | canonical 对象状态 + 视图代际 + 最新 run 目标结果（分组展示） | 0/1 |
| `validate` | manifest 一致性清单驱动校验（canonical/Card/Wiki 与代际/索引一致） | 0/1 |
| `compile` | 幂等重编译 Wiki/HTML + 重建 FTS（逐字节一致；推进 wiki_generation） | 0/1 |
| `context "<task>" [--format md\|json] [--budget N] [--include-stale]` | 预算化检索；`--include-stale` 为醒目标记的诊断模式 | 0/1 |
| `open` | 打开 HTML Wiki；`wiki_generation` 落后时先全局告警 | 0/1 |
| `serve` | 回环地址、只读、单文档 Wiki 服务 | 0/1 |
| `edit <object-id>` | 创建/编辑人工 overlay（保存时校验，不改 canonical） | 0/1 |

Agent 队列命令（隐藏，供 `/knowledge-build`、`/knowledge-update` Skill 使用）：`prepare / next --operation extraction / evidence <target> / submit-extraction <file> --lease <token> / verify-next / submit-verification <file> --lease <token> / finalize`——租约 + 幂等键 + 新鲜验证上下文，Skill 不自带调度。

## 七个只读 MCP 工具（`knowledge-mcp`）

`knowledge_repo_overview` / `knowledge_search` / `knowledge_get_object` / `knowledge_get_related` / `knowledge_get_evidence` / `knowledge_context_for_task` / `knowledge_status`

- 只读：永不构建、变更 canonical、写状态或执行仓库代码（有整树字节不变测试）；
- 默认读取 fail closed：快照或代际不匹配 → `knowledge_update_required`；
- `get_object`/`status`/`context_for_task` 接受 `include_stale`，仅作醒目标记的诊断；
- `get_evidence` 只回答已提交包中记录的已知 Evidence ID，路径经仓库根/符号链接校验；
- 协议 `2024-11-05`（initialize/tools/list/call；通知静默；解析错误 `-32700`）。

## 检索门禁（每次默认读取必须全部满足）

当前过滤快照 == manifest `observed_snapshot`（repository_id/commit/dirty/工作树哈希逐字段，脏树要求非空匹配哈希）∧ `active_generation` == `agent_views_generation` == FTS 索引戳。任一不满足 → `knowledge_update_required`（不是旧数据）。干净树被改动一个合格字节同样触发拒绝。

## 验证闭环（`bash scripts/verify.sh`）

1. 离线套件双遍（计数级一致检查；`VERIFY_FAST=1` 跳过第二遍）；
2. `compileall`（仅 src）；
3. `git diff --check`；
4. `pip-audit` 依赖审计；
5. live 冒烟自动探测：`codewiki` 0.6.x 在 PATH ∧ `KNOWLEDGE_EXTRACTION_MODEL` ∧ `KNOWLEDGE_LIVE_REPOSITORY` 齐备即执行真实端到端，否则列明缺失项跳过；`REQUIRE_LIVE=1` 强制失败闭合。

当前基线：752 passed + 1 skipped（live）双遍一致。

## Revision History

- 2026-09-12 按 `origin/main 000e962` 的 CLI/MCP/检索实现建卷。
