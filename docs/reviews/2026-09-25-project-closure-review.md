---
status: active
last-reviewed: 2026-10-11
scope: project-freeze-and-closure-readiness
sources:
  - rules/principles.md
  - docs/knowledge/product/traceability.md
  - docs/materials/validation/project-freeze-2026-09-25/
  - docs/superpowers/plans/active/
---

# CodeWiki 项目冻结与关闭审查

## 结论先行

| 判断对象 | 结论 | 原因 |
|---|---|---|
| V0.1 技术基线 | **有条件可冻结** | 离线主链、CLI/MCP/静态产物、安全审计与 790 项测试通过；真实 live、M8 价值实验和 CI 锁文件门仍未闭合 |
| Local Beta M9–M14 | **未开始** | 六份已批准计划共有 251 个执行步骤，完成 0 个 |
| 整个项目 | **不可关闭** | Local Beta 仍是 active 承诺，且用户已要求从中断处继续，不是取消或延期 |
| GitHub 仓库归档 | **不执行** | 公开归档属于外部生效动作，且项目关闭条件尚未满足 |

项目当前不是“所有能做的都做完了”，而是完成了可信知识编译器 V0.1 的大部分技术交付，随后完成了下一阶段设计，但尚未开始把引擎做成个人开发者可操作的 Local Beta。

## 已验证交付

- Git 快照/变化识别、公开 Evidence Provider、五类 Canonical IR、规划/抽取/独立验证、原子发布、增量失效/退役、human overlay。
- Markdown Wiki、Knowledge Cards、Task Context、单文件 HTML、静态多页站点、本地回环只读服务、FTS 检索。
- CLI 主命令面与七个只读 MCP 工具；默认 snapshot/validity/evidence fail-closed。
- 2026-10-11 `VERIFY_FAST=1 bash scripts/verify.sh`：790 passed、1 opt-in live skipped，compile/diff/pip-audit PASS。
- 隔离临时仓库真实浏览器验收覆盖入口、Ask、详情、Evidence、History、移动端；截图见[产品端面审查](../materials/validation/project-freeze-2026-09-25/product-surface-review.md)。

## 本轮发现并关闭

1. History 页在转义 helper 声明前执行，导致运行时空白。
2. 单文件 Wiki 的全局 `nav` 样式污染多页站点顶部导航。
3. 单文件 Wiki 的全局 `body{display:flex}` 污染多页站点布局。
4. `multidict`、`pyjwt`、`urllib3` 共 18 条已知漏洞，通过兼容升级关闭。
5. Playwright 临时日志/截图目录补入忽略规则，避免污染仓库。
6. 旧交接中的 259 步修正为按源计划行首 checkbox 统计的 251 个执行步骤。

对应代码与依赖修复提交：`12c92cc`。

## 未完成但仍在既定范围内

### 外部或证据阻断

- PorunC/CodeWiki `0.6.5` 在真实中型 Python 仓库可 SIGSEGV/SIGBUS；上游 issue #2 截至 2026-10-11 仍开放、无回复。
- Live smoke 缺模型配置和目标仓库，本轮只能 SKIP，不能记为 PASS。
- M8 harness/dry-run 已就绪，但真实 A/B 尚未运行。
- 键盘全流程、屏幕阅读器和自动对比度实测仍缺证据。

### 需要先获批准的仓库治理

- `.github/workflows/ci.yml` 未按 `uv.lock` frozen 安装，也未执行 lock/pip-audit 门禁。
- `.github/workflows/screenshot.yml` 仍监听不存在的 `README.zh.md`，且每日自动写回截图会给冻结项目制造提交漂移。

这两项都是 CI/CD 配置，受全局红线约束，本轮只能给出精确建议，不能未经批准修改。

### 已批准但未实现

| 里程碑 | 执行步骤 | 当前完成 | 下一入口 |
|---|---:|---:|---|
| M9 本地产品基座 | 48 | 0 | Task 1：应用打包契约 |
| M10 可靠仓库解析 | 44 | 0 | M9 公共合同完成后 |
| M11 构建任务生命周期 | 43 | 0 | M9/M10 完成后 |
| M12 知识阅读 Beta | 40 | 0 | M11 读 API 稳定后 |
| M13 Ask / Agent 一致性 | 41 | 0 | M10/M12 完成后 |
| M14 价值证明与 Beta 发布 | 35 | 0 | M9–M13 全部过门后 |
| **合计** | **251** | **0** | **从 M9 Task 1 连续推进** |

## 竞品横评后的范围裁决

完整来源与矩阵见[竞品来源与能力核验](../materials/validation/project-freeze-2026-09-25/competitor-sources.md)。

- `close before freeze`：依赖漏洞、真实浏览器运行缺陷、文档状态冲突——本轮已关闭。
- `retain current design`：Claim 级证据、Canonical IR、人工 overlay、fail-closed、只读 MCP、静态可重建视图。
- `planned only`：新用户生成→阅读→Ask、进度/错误/恢复、历史差异和移动端产品体验——已在 M9–M14，不能另开路线。
- `blocked evidence`：真实上游解析、live smoke、M8 A/B、辅助技术实测。
- `out of scope`：云托管、多租户、团队 RBAC、多仓门户、PR review、IDE、把向量库变成权威事实源。

竞品没有揭示必须扩大范围的新产品线；当前问题是执行已批准路线，而不是再设计一轮。

## 清理与知识沉淀

- 无必须删除或重命名的 tracked 文件，不为“整齐”破坏历史追溯。
- materials / knowledge / workflow 三层保留；设计稿明确标成 design evidence，不冒充 shipped UI。
- 已补齐演进时间线、来源目录、承诺追溯、as-built 架构、行为参考、竞品模式、上游状态与归档清单。
- 清理台账、迁移判断和浏览器证据均保存在本轮 validation 目录。

## 恢复与继续执行

1. `git pull --ff-only`，确认 `main == origin/main`。
2. 运行 `bash scripts/verify.sh`，确认 790+1 或后续明确记录的新基线。
3. 阅读 [Local Beta 总计划](../superpowers/plans/active/2026-09-17-local-beta-master-plan.md) 与 [M9 详细计划](../superpowers/plans/active/2026-09-17-m9-local-product-foundation.md)。
4. 从 M9 Task 1 的失败测试开始；不得把设计 HTML 当成已交付应用。
5. 每个里程碑同步 README、docs 索引、决策日志、验证证据与 HANDOFF。

## 关闭门禁

只有在以下条件同时满足后，整个项目才可重新评估关闭：

- M9–M14 完成，或用户逐项明确取消/延期并转为历史状态；
- live/M8 缺口有真实证据，或被明确接受为冻结限制；
- CI/CD 两项治理获得决策并闭合；
- 完整 `bash scripts/verify.sh`、链接检查、安全审计通过；
- README、HANDOFF、文档索引、追溯表、归档清单与代码一致；
- 工作树干净，`HEAD == origin/main`。

## Revision History

- 2026-10-11：完成 2026-09-25 启动的冻结审查，给出 V0.1 与整个项目的独立结论。
