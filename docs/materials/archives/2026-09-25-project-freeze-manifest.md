---
status: frozen-evidence
last-reviewed: 2026-10-11
scope: project-freeze-archive-manifest
sources:
  - docs/materials/validation/project-freeze-2026-09-25/
  - docs/reviews/2026-09-25-project-closure-review.md
---

# 2026-09-25 项目冻结审计归档清单

本清单记录 2026-09-25 启动、2026-10-11 续审的静态归档包。它归档审查事实，不代表整个项目已关闭。

## 提交指针

| 用途 | 提交 |
|---|---|
| 冻结原则与审计计划建立 | `cea7c4b` |
| 首轮文档/依赖基线修复 | `853f025` |
| 浏览器缺陷与传递依赖安全修复 | `12c92cc` |
| 审查文档与归档首次入库 | `d26a7a1` |

## 归档树

```text
docs/reviews/2026-09-25-project-closure-review.md
docs/materials/validation/project-freeze-2026-09-25/
├── environment.md
├── engineering-audit.md
├── product-surface-review.md
├── competitor-sources.md
├── cleanup-ledger.md
├── path-migration-map.md
└── ui/
    ├── 01-entry.png
    ├── 02-ask-results.png
    ├── 03-object-detail.png
    ├── 04-evidence-expanded.png
    ├── 05-history.png
    └── 06-mobile.png
docs/knowledge/product/evolution.md
docs/knowledge/product/traceability.md
docs/materials/origin/timeline.md
docs/materials/source-catalog.md
```

## 验证快照

| 命令 | 2026-10-11 结果 |
|---|---|
| `bash scripts/verify.sh` | PASS；双遍均为 790 passed、1 live skipped；compile/diff/pip-audit PASS |
| `uv pip check` | PASS |
| `python scripts/check_links.py` | 最终提交前复验 |
| `git diff --check` | 最终提交前复验 |
| Playwright Chromium | 6 张 accepted 截图；入口/Ask/详情/Evidence/History/移动端 |

## 关键文件 SHA-256

| 文件 | SHA-256 |
|---|---|
| `docs/reviews/2026-09-25-project-closure-review.md` | `f5e1bd62a8bcd83d3ab25f9655e89117cad763833d074b8c412aea450f2d65ac` |
| `docs/knowledge/product/evolution.md` | `65ddfee1b7f184aae3e18f4369229c777046c724309fb974b12422ed8ce8b2ca` |
| `docs/knowledge/product/traceability.md` | `c1357cdc0dc352edb1fade866e4de0374450032982d8a1493c0dfde786e74ae7` |
| `ui/01-entry.png` | `e9f239fca1dd268d90321423ed279dde65192d780c50e2d42112e818d559587d` |
| `ui/02-ask-results.png` | `412958705c7d351568e6a1d3b0c39c5ce342abae93eb64b3c1525ee85790092c` |
| `ui/03-object-detail.png` | `4a8fed37d0bd3a6f1e61b92ca578773779c0f1a67519ea903dcdf03184b9115c` |
| `ui/04-evidence-expanded.png` | `a768d3ab25cf9667544637067dbeff81e06b4646f9bf0af5b8d185fc3a5ae2e4` |
| `ui/05-history.png` | `1eaefcf520a3db299aa80a11b3beaf5d49edd7e2c7152f92037d2e5bdd7f32dc` |
| `ui/06-mobile.png` | `9efa4afed6d330068ae7d43246d57ae274002ae207dffd07058b9b8ebd42dd4c` |

## 外部状态

- PorunC/CodeWiki issue #2：2026-10-11 仍 OPEN、0 comments。
- PorunC/CodeWiki 最新 GitHub release：v0.6.3；本项目依赖并实测 0.6.5。
- Live smoke：环境条件不足，SKIP，不是 PASS。
- M8：harness/dry-run ready，真实实验未运行。

## 恢复说明

```bash
git clone https://github.com/davyzhong/CodeWiki.git
cd CodeWiki
uv sync --frozen --extra dev
bash scripts/verify.sh
```

随后阅读根 `HANDOFF.md`、本清单、项目关闭审查和 Local Beta 总计划。不要从 `docs/design/` 反推 shipped 状态；实现事实以源码、测试、追溯矩阵和当前验证结果为准。

## 完整性说明

- 原始/历史材料未被覆盖；私有 ATLAS 与 Enterprise Intelligence 只保留公开安全的方法提炼。
- 本轮没有删除、重命名、数据库迁移、强制推送或公开归档。
- CI/CD 建议因审批边界尚未执行，并在关闭审查中保留为治理缺口。
- 关键知识文档与截图的 SHA-256 已按 2026-10-11 M9 Task 1 状态字节记录；后续修改这些文件必须同步更新本表。

## Revision History

- 2026-10-11：建立冻结审计归档树、恢复方式和外部阻断快照。
