---
status: maintained-audit
last-reviewed: 2026-10-11
scope: freeze-cleanup
sources:
  - git ls-files
  - rg and du inventory
---

# 清理台账

| 对象 | 发现 | 分类 | 处置 |
|---|---|---|---|
| `node_modules/`、Playwright reports、`.playwright-cli/`、`output/playwright/` | 本地生成且未跟踪 | safe hygiene | 已加入 `.gitignore`；本地副本不影响封存 |
| `__pycache__/`、`.venv/` | 本地生成且已忽略 | safe hygiene | 不入库；不需要删除才能封存 |
| README screenshots | 约 5.5 MiB，均被 README 引用 | retained asset | 保留；不以大小为理由删除 |
| Local Beta design assets | 有规格与 README 引用 | retained evidence | 保留并标注“设计而非 shipped UI” |
| 旧计划/会话归档 | 历史事实，不是 active truth | retained history | 保留，不重复为当前计划 |
| active M9–M14 | 251 个执行步骤均未完成 | unresolved plan | 用户已要求从中断处继续，下一入口为 M9 Task 1；不能删除 |
| 错误计划路径引用 | `docs/superpowers/plans/...` 旧路径 | stale reference | 更新为 `historical/...` |
| README 许可状态 | 写成 MIT planned | stale metadata | 已改为 MIT |
| M8 状态 | 文档曾写 draft | stale status | 已统一为 frozen-blocked |
| `README.zh.md` workflow path | 文件不存在 | automation drift | 需批准后修改 CI workflow |
| Ruff 293 项 | 未建立 lint 规范，多数风格项 | maintenance debt | 不做无证据的大规模自动改写 |

## 删除与重命名结论

没有必须删除或重命名的 tracked 文件。用户要求“完整清理”不应被解释成抹掉历史；最安全完整状态是保留历史、修正状态和索引、隔离生成物。若未来要压缩二进制或撤销自动化，应另列精确批次并先获批准。

## Revision History

- 2026-09-25：建立封存清理台账。
- 2026-10-11：加入浏览器临时产物忽略项，并按行首 checkbox 重算 M9–M14 为 251 个执行步骤。
