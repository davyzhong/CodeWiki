---
status: maintained-audit
last-reviewed: 2026-10-11
scope: shipped-v0.1-surfaces
sources:
  - src/knowledge_compiler/cli.py
  - src/knowledge_compiler/mcp_server.py
  - src/knowledge_compiler/compiler/wiki.py
  - docs/materials/validation/project-freeze-2026-09-25/ui/
---

# 产品端面审查

## 事实边界

当前已交付产品端面是 CLI、七个只读 MCP 工具、确定性静态 Wiki/HTML、Knowledge Cards 与 Task Context。`docs/design/` 的 HTML 是获批的 Local Beta 设计基线，不是已交付 Web 应用；M9–M14 的 API、服务、浏览器应用和 Ask UI 尚未实现。

## 已确认优点

- 人类阅读与 Agent 读取共享 Canonical IR，避免两套知识事实漂移。
- 默认检索执行 snapshot、validity 与 evidence 门禁，可信度高于“只生成漂亮文档”。
- 静态 Wiki 可离线保存，支持源码回链、关系图、FTS 与确定性重建。
- CLI/MCP 的机器边界清晰；MCP 保持只读，降低 Agent 接入风险。

## 已确认缺口

- 首次使用路径仍偏工程化：环境准备、模型配置、上游 CLI、生成与查看分散在命令和 runbook 中。
- CLI 代码覆盖约 67%，相较核心库偏低；错误信息和恢复路径虽有测试，但缺少一次真实新用户端到端证据。
- 没有已经交付的构建进度、失败恢复、知识状态总览、Ask 引用面板、历史差异与移动端界面；这些恰好是 M9–M14 的范围，不能写成 V0.1 回归。
- 当前 README 截图是 GitHub README 的自动截图，不是产品运行界面证据。

## 本轮真实视觉证据

2026-10-11 在隔离临时 Git 仓库中通过公开编译入口生成静态站点，以本地只读 HTTP 服务和 Playwright Chromium 重新采集、逐张检查：

| 画面 | 文件 | 结论 |
|---|---|---|
| 目录入口 | [`ui/01-entry.png`](ui/01-entry.png) | 层级清楚、信任状态与对象入口可见 |
| Ask 结果 | [`ui/02-ask-results.png`](ui/02-ask-results.png) | 引用式结果可用；结果较长且缺少排序解释，属于 Local Beta 可用性债务 |
| 对象详情 | [`ui/03-object-detail.png`](ui/03-object-detail.png) | Claim、状态、关系与来源在同一页 |
| Evidence 展开 | [`ui/04-evidence-expanded.png`](ui/04-evidence-expanded.png) | 证据可追溯；不是只给文档级链接 |
| 历史页 | [`ui/05-history.png`](ui/05-history.png) | 修复前因 `esc` 未定义空白，修复后正常显示 |
| 移动端 | [`ui/06-mobile.png`](ui/06-mobile.png) | 主内容单列；宽目录表依赖横向滚动 |

浏览器取证直接发现并关闭了历史页脚本顺序、顶部导航样式污染和多页站点 body flex 污染三项缺陷。静态 Ask 会先探测 `/api/preview`，在纯静态服务下产生一次预期 404 后回落内嵌索引；功能正常但控制台噪声应在 M12/M13 体验阶段消除。`favicon.ico` 也会 404，不影响核心功能。空结果可由搜索触发，但构建失败/恢复流属于尚未实现的 Local Beta 应用，不伪造截图。

键盘完整遍历、屏幕阅读器实测和自动对比度扫描未在本轮完成，保留为 `blocked evidence`，不得由现有 ARIA 单元断言替代。

## 封存判断

- 对 V0.1：CLI/MCP/静态产物是合法交付面；缺少 GUI 不构成规格遗漏。
- 对 Local Beta：界面和服务端面为 `planned only`，不能关闭为完成。
- 若决定取消 Local Beta，应把设计与计划转为“deferred/cancelled historical”，而不是删除；若决定继续，则必须按 M9–M14 实施并取得真实截图和端到端证据。

## Revision History

- 2026-09-25：区分 shipped surface、设计稿和未交付 Local Beta。
- 2026-10-11：补入隔离仓库真实浏览器截图、已关闭缺陷与仍缺的辅助技术证据。
