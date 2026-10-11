---
status: maintained-audit
last-reviewed: 2026-10-11
scope: v0.1-as-built
sources:
  - src/knowledge_compiler/
  - tests/
  - scripts/verify.sh
  - pyproject.toml
---

# 工程与仓库审计

## 结论

V0.1 的离线工程门禁通过，核心合同有高密度测试覆盖；未发现密钥入库、`shell=True`、动态 `eval` 或不受控仓库代码执行。续审发现并关闭了静态站点三项实际缺陷与 18 条传递依赖漏洞。仍有两个不能虚报的缺口：真实上游运行因 PorunC/CodeWiki 崩溃问题未闭环，CI 没有以 `uv.lock` 为唯一安装来源。

## 验证结果

| 维度 | 结果 | 证据 / 处置 |
|---|---|---|
| 离线测试 | PASS | 790 passed、1 skipped |
| 覆盖率 | PASS with debt | 总体约 88%；CLI 约 67%，不是发布阻断但应如实保留 |
| 编译 | PASS | `compileall src` |
| 依赖一致性 | PASS | `uv lock --check`、`uv pip check` |
| 依赖漏洞 | PASS | `pip-audit`；`multidict`、`pyjwt`、`urllib3` 漏洞已通过兼容升级关闭；本地包因未发布 PyPI 被合理跳过 |
| Live smoke | SKIP | 缺模型/目标仓库且上游真实仓库崩溃仍开放 |
| Wheel/sdist | PASS with note | wheel 约 172 KiB、83 files；sdist 约 13 MiB；Skills 已打包，无 Local Beta app |
| 静态链接 | PASS（本轮最终门复验） | `python scripts/check_links.py` |
| 敏感信息 | PASS | 仅测试 fixture 中有显式假 token |

## 架构完整性

已实现并有测试的主链：Git 快照与差异 → CodeWiki/Fake Evidence Provider → typed planner/workers → 结构/语义验证 → 可恢复 generation publication → 增量失效/退役 → human overlay → Wiki/Card/Task Context → FTS/ContextRetriever → 七个只读 MCP 工具。Local Beta 规格中的 `application/`、`app/`、`web/` 目录不存在，证明其仍是计划而非产品。

## 代码质量观察

- 模块边界总体与 V0.1 规格一致，确定性、原子发布、恢复、symlink/路径安全均有专门测试。
- 高复杂度集中在 `compiler/wiki.py`（约 2,059 行）、`storage/generation.py`（约 1,250 行）、`storage/lifecycle.py`（约 989 行）、`contracts/knowledge.py`（约 913 行）和 `cli.py`（约 765 行）。这些是维护风险，但在封存阶段拆分会带来回归面，判为“保留现状”。
- 诊断性 Ruff 扫描发现 293 项（223 项可自动修复），多数是 import 排序、未使用 import/局部变量。项目当前没有 Ruff 配置或 lint 门禁，批量格式化不属于“遗漏修复”；不得在封存提交里制造大噪声 diff。
- `workers/litellm_worker.py` 有延迟注解 `PlanRequest` 未直接导入；因 `from __future__ import annotations` 当前运行安全，但运行时反射 `get_type_hints` 可能失败。当前公共路径与测试未触发，记录为 P2 维护债务。
- `LocalGitRepositoryProvider.diff()` 保留 `NotImplementedError`，而真实变化计算走专用 change inventory；测试明确锁定此行为。它是接口陈旧而非已复现缺陷，封存时不扩合同。

## 2026-10-11 浏览器审计关闭的缺陷

1. `history.html` 在 `esc()` 声明前执行渲染，浏览器抛出 `ReferenceError`，历史表空白；已先增加失败测试，再调整脚本顺序。
2. 单文件侧栏的全局 `nav` 规则误伤多页站点顶部导航；已将规则收敛到 `.wiki-sidebar`。
3. 单文件布局的全局 `body{display:flex}` 误伤多页站点，使导航与正文横向并列；已用 `.wiki-standalone` / `.wiki-site` 分离布局语义。

三项修复均在 `12c92cc` 推送，并由新的确定性 HTML 测试和本轮 Playwright 截图共同取证。

## 供应链与自动化缺口

1. **已关闭**：`pytest 8.4.2` 漏洞锁定；升级至 9.1.1并重锁。
2. **待批准**：`.github/workflows/ci.yml` 仍以 `pip install -e ".[dev]"` 解析最新依赖，未执行 frozen sync、lock check 或 pip-audit。修改 CI 属全局红线，不能擅自执行。
3. **待批准**：README screenshot workflow 仍监听已不存在的 `README.zh.md`，并在每次 README 变化后自动写回二进制图片；归档项目若继续保留定时/自动写回会造成无业务价值的提交漂移。
4. **上游阻断**：PorunC/CodeWiki `0.6.5` 的真实中型 Python 仓库分析可触发 SIGSEGV/SIGBUS；[上游 issue #2](https://github.com/PorunC/CodeWiki/issues/2) 截至 2026-10-11 仍 OPEN、0 comments，GitHub 最新正式 release 仍为 v0.6.3。

## 处置分类

| 项目 | 分类 | 理由 |
|---|---|---|
| 安全依赖与锁文件一致性 | close before freeze | 可安全修复，已完成 |
| CI frozen lock / audit | close before final archive | 已有安全目标的执行缺口；需用户批准改 CI |
| Live smoke | blocked evidence | 需要凭据/模型且受上游崩溃影响 |
| 拆分超大模块、全量 Ruff | retain current design | 没有功能缺陷证据，封存前重构风险高 |
| Local Beta application/web | planned only | 属 M9–M14，不得混入 V0.1 完成度 |
| 多租户、云服务、团队权限 | out of scope | 与个人开发者 local-first 决策冲突 |

## Revision History

- 2026-09-25：完成封存工程审计并关闭依赖安全缺口。
- 2026-10-11：补充真实浏览器审计，关闭历史页/导航/页面布局缺陷和新发现的传递依赖漏洞。
