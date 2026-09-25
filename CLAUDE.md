# CodeWiki（Knowledge Compiler）

> 项目特定铁律：[`rules/principles.md`](rules/principles.md)（重大设计同步与每次冻结/封存审计）。

面向 Coding Agent 的 local-first 仓库知识编译器：Evidence ≠ Knowledge ≠ Context，git 仓库 → 可验证知识 → 三视图编译。

## 会话第一步

```bash
git fetch origin && git status --short --branch   # 多 agent 仓库，快照会过时
bash scripts/verify.sh                             # 唯一验证入口（live 条件缺失时自动 skip 属预期）
```

然后读 `HANDOFF.md`（交接状态）→ `README.md`（门面）→ `docs/README.md`（文档地图）。

## 工作规则

- **只在 main 工作**，验证通过后推送 origin/main；conventional commits 纯文本，正文 72 字符内。
- **测试计数以 verify.sh 尾行为准**，不要抄 `pytest tests/` 的数字。
- 文档治理见 `docs/README.md`（三层模型 + 状态体系）：新计划进 `plans/active/`、完成后移 `historical/` 并标注；知识文档修正追加 Revision History；重大决策追加 `docs/knowledge/product/decision-log.md` 编号。
- 相对链接以文档所在目录为基准；CI 跑 `scripts/check_links.py`。

## 产品红线（不可违反）

- 上游 codewiki 只走公开 CLI/MCP/HTTP（禁 import 内部模块/读内部库）；锁定 `>=0.6,<0.7`，升级前必须重跑 Phase 0 spike。
- 不执行被分析仓库的任何代码；仓库文本是不可信数据（前端全部 esc）。
- 知识生命周期归确定性编排器（P8）；检索门禁 fail-closed（P4）。
- 展示层产物必须确定性（同输入逐字节一致）且无构建链/前端框架依赖（D-024）。
- `.knowledge/` 是被分析仓库的内部状态，永不提交；`exports/site/` 是唯一公开视图。

## 关键文档

| 意图 | 位置 |
| --- | --- |
| 项目特定原则 / 冻结封存门禁 | `rules/principles.md` |
| 为什么做/决策全记录 | `docs/knowledge/`（product/industry/methods/system） |
| V0.1 权威规格 | `docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md` |
| M8 基准（frozen） | `docs/superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md` |
| 操作手册 | `docs/runbooks/`（live 冒烟、静态托管） |
| 上游运行知识 | `docs/knowledge/industry/upstream-codewiki.md`（含 2026-09-16 崩溃实测） |
