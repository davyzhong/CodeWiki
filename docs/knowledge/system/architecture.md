---
status: maintained
last-reviewed: 2026-09-12
sources:
  - src/knowledge_compiler/（as-built 源码结构）
  - superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md §4–§5、§11.1（偏差）
---

# 系统架构（as-built）

## 组件地图（`src/knowledge_compiler/`）

```
仓库输入              证据层                语义层                     生命周期
─────────            ─────────            ─────────                 ─────────
repository/          providers/           workers/                  orchestrator/
  local_git.py         codewiki.py          litellm_worker.py         contracts/store/
  inventory.py         codewiki_cli.py      queue_executor.py         queue/runner/
  changes.py           fake.py(测试)        skills/(协议)             fixture_worker(测试)
                      planning/            validation/
                        module.py            module.py + typed.py
合同层                编译层                存储/检索                 接口层
─────────            ─────────            ─────────                 ─────────
contracts/           compiler/             storage/                  cli.py（主命令面）
  repository/evidence  yaml/markdown        generation.py(发布事务)    cli_agent_queue.py
  knowledge/semantic    wiki/typed_views    lifecycle.py(tracked态)   mcp_server.py
  canonical/planning    mermaid/human     incremental/               serving.py
  human/relations       行为=纯函数          invalidation/pending/     config.py/preflight.py
                                          retirement/updating       building.py/real_slice.py
                                          retrieval/(FTS+context)    vertical_slice.py(M1 演示)
                                          human/(overlays/conflicts) spikes/(Phase 0 探针)
```

## 端到端数据流

```
knowledge build --executor llm
  → preflight（Git→commit→eligible→scope→config→CodeWiki 版本→模型 profile，全部先于任何模型调用）
  → LocalGit 解析 RepositorySnapshot（合格文件清单 + 快照身份）
  → CodeWiki 公开面（repos add/analyze/scan/graph）→ 归一化 DTO → 调研驱动的多目标 KnowledgePlan
  → 持久化 RunOrchestrator（每目标：build_pack(有界+脱敏) → 抽取 → 结构验证 → 独立语义验证 → 修复≤2）
  → 批量发布事务（canonical/Agent 面 + tracked plan/manifest 状态，manifest 最后替换）
  → 视图编译（Wiki/HTML/FTS 重建；失败=partial，wiki_generation 落后）
knowledge update：本地 ChangeSet 先行 → 原子失效（stale 移出 Agent 面）→ pending 重试 → 选择性重建 → 确定性退役
消费：knowledge context（FTS+一跳+预算）/ serve（回环只读）/ knowledge-mcp（七个只读工具）
```

## 与规格的三处已记录偏差（详见规格 §11.1，决策 D-017/018/019）

1. MCP 传输用零依赖 stdio JSON-RPC（非 MCP SDK）——工具语义与只读保证照旧；
2. FTS 索引在 canonical 提交后由 compile/编排器重建（非事务内换库）——读取门禁保证安全性质不损失；
3. 视图编译失败返回 partial 并保留落后 wiki_generation（不回滚有效 IR）——`knowledge compile` 幂等重试。

## 关键持久化位置（目标仓库内）

| 路径 | tracked | 内容 |
|---|---|---|
| `.knowledge/manifest.yaml` | 是 | observed_snapshot、三代际戳、pending_targets |
| `.knowledge/plan.yaml` | 是 | 最新计划与目标状态/结果 |
| `.knowledge/objects/**/*.yaml` | 是 | canonical IR（五类型分目录） |
| `.knowledge/views/{wiki,cards}/` | 是 | 编译的人类/Agent 视图 |
| `.knowledge/human/` | 是 | 人工 overlay（含 archive/） |
| `.knowledge/baseline/eligible-files.json` | 是 | 跨机器增量基线 |
| `.knowledge/cache/knowledge-index.sqlite3` | 否 | FTS（可重建） |
| `.knowledge/state/runs/`、`state/transactions/` | 否 | 运行状态与发布事务（恢复用） |
| `.knowledge/exports/repo-wiki.html` | 否 | 可复现产物（可显式提交） |

## Revision History

- 2026-09-12 按 `origin/main 000e962` 的源码结构建卷。
