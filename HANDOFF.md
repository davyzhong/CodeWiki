---
status: active
last-reviewed: 2026-10-20
scope: cross-session-handoff
---

# HANDOFF — CodeWiki 当前交接

> 交接日期：2026-10-20
>
> 工作仓库：`/Users/qiming/workspace/CodeWiki`
>
> 交接前远端 HEAD：`ff1437b`（README 自动截图）；最近功能提交：`dfa267d`
>
> 分支策略：只在 `main` 工作，验证后 commit，并立即 push 到 `origin/main`
>
> 本文提交：以 `git log -1 -- HANDOFF.md` 为准

## 1. 当前任务

项目已结束“是否可以关闭”的冻结审查，结论是：

- V0.1 核心技术链有条件可冻结；
- 整个项目不可关闭；
- Local Beta 已恢复执行；
- 当前执行里程碑是 M9“本地产品基座”；
- M9 Task 1 已完成，下一功能任务是 Task 2“AppPaths 与版本化 App DB”。

权威执行入口：

1. [Local Beta 总计划](docs/superpowers/plans/active/2026-09-17-local-beta-master-plan.md)
2. [M9 详细计划](docs/superpowers/plans/active/2026-09-17-m9-local-product-foundation.md)
3. [承诺—实现—测试追溯矩阵](docs/knowledge/product/traceability.md)
4. [项目冻结与关闭审查](docs/reviews/2026-09-25-project-closure-review.md)

## 2. 当前进度

| 范围 | 进度 | 状态 |
|---|---:|---|
| V0.1 核心引擎 | 主链已交付 | 有条件可技术冻结 |
| M8 真实价值实验 | harness/dry-run 已完成 | 真实 A/B 未执行 |
| M9 本地产品基座 | 6/48 | Task 1 完成，Task 2 待开始 |
| M10–M14 | 0/203 | 尚未开始 |
| Local Beta 总计划 | 6/251 | 约 2.4% |
| 整个项目 | — | 不可关闭 |

251 的统计口径是六份子计划中行首 checkbox 的总数；不要恢复旧交接中的 259。

## 3. 已经完成

### 3.1 冻结审查与知识归档

- 建立项目冻结铁律 P-002 和完整关闭审查。
- 完成内部工程审计、真实浏览器审计、竞品横评、清理台账、演进时间线、来源目录和归档清单。
- 明确区分“V0.1 核心完成”“Local Beta 设计批准”“整个项目完成”。
- 主要提交：
  - `12c92cc`：修复静态知识站点布局、History 运行时错误和传递依赖漏洞；
  - `d26a7a1`：冻结审查、截图和知识归档入库；
  - `7c5b0a3`：固定审查提交指针。

证据入口：

- [冻结审查](docs/reviews/2026-09-25-project-closure-review.md)
- [审计证据目录](docs/materials/validation/project-freeze-2026-09-25/)
- [冻结归档清单](docs/materials/archives/2026-09-25-project-freeze-manifest.md)
- [项目演进](docs/knowledge/product/evolution.md)

### 3.2 M9 Task 1：打包和运行时契约

提交：`dfa267d build: 固化本地应用打包契约`

已完成：

- 增加有界运行依赖：FastAPI、Uvicorn、platformdirs；
- 增加开发依赖 httpx；
- 注册 `knowledge app` 和 `knowledge-app`；
- 建立 `src/knowledge_compiler/app/` 包和 wheel 静态入口；
- 建立 `web/` 的 React、TypeScript、Vite、Vitest、Playwright 工具链；
- 生成并验证 `pnpm-lock.yaml`；
- 实际构建 wheel，确认包含 `knowledge_compiler/app/static/index.html`；
- 增加 3 项打包契约测试；
- `knowledge-app` 当前是 Task 1 的占位入口，会清晰输出“尚未实现”并返回 1；真正生命周期在 M9 Task 6 实现。

### 3.3 README 自动截图

README 更新后，GitHub Actions 追加了两个截图提交：

- `f2c9b3d`
- `ff1437b`

它们只更新 `assets/screenshots/readme-desktop.png` 和 `readme-mobile.png`，没有功能代码变化。

## 4. 当前卡点与风险

### 4.1 当前安全门禁失败：必须先处理

2026-10-20 在 `ff1437b` 运行：

```bash
VERIFY_FAST=1 bash scripts/verify.sh
```

结果：

- tests：793 passed、1 skipped；
- compileall：PASS；
- diff-check：PASS；
- live smoke：SKIP；
- pip-audit：FAIL；
- 总结果：`VERIFY: FAILED`。

失败原因是锁文件中的 `aiohttp 3.14.3` 新出现 3 条已知漏洞：

- CVE-2026-111064；
- GHSA-2g87-pp6c-29x5；
- CVE-2026-111063。

修复版本均为 `aiohttp 3.14.4`。因此 `793+1` 只能表述为测试结果，不能表述为当前完整门禁 PASS。

### 4.2 上游 CodeWiki 崩溃

- [PorunC/CodeWiki issue #2](https://github.com/PorunC/CodeWiki/issues/2) 在 2026-10-20 仍为 OPEN、0 comments；
- 最新 GitHub release 仍为 v0.6.3；
- 本项目使用并实测的 PyPI 版本为 0.6.5；
- 真实中型 Python 仓库可能触发 SIGSEGV/SIGBUS；
- 该问题阻塞真实 live 与 M8，但不阻塞 M9 的本地应用基础工作。

### 4.3 外部输入仍缺失

- `KNOWLEDGE_EXTRACTION_MODEL` 未配置；
- `KNOWLEDGE_LIVE_REPOSITORY` 未配置；
- `codewiki` 未暴露在 shell PATH；
- M8 真实实验仍需模型凭据。

Live smoke 的 SKIP 不是 PASS。

### 4.4 需要用户批准的红线

以下动作不能直接执行：

1. M9 Task 2 会创建 App SQLite schema 和迁移机制，命中“数据库 schema/迁移”红线；开始前必须给用户一个结构化选择题取得批准。
2. 修改 `.github/workflows/ci.yml`，让 CI 使用 frozen lock 和 pip-audit，属于 CI/CD 修改红线。
3. 修改 `.github/workflows/screenshot.yml`，清理不存在的 `README.zh.md` 和每日自动写回策略，也属于 CI/CD 修改红线。

三个决策必须一个一个问，不得合并成一道题。

## 5. 下一步计划

### 第一步：恢复并关闭安全门禁

```bash
cd /Users/qiming/workspace/CodeWiki
git pull --ff-only
uv lock --upgrade-package aiohttp
uv sync --frozen --extra dev
uv pip check
VERIFY_FAST=1 bash scripts/verify.sh
python scripts/check_links.py
git diff --check
```

预期：

- `aiohttp >= 3.14.4`；
- pip-audit PASS；
- tests 至少 793 passed、1 live skipped；
- `VERIFY: PASS`。

完成后更新验证基线、commit，并立即 push。

### 第二步：取得 Task 2 数据库红线批准

只问一个选择题：

- A：批准执行 M9 Task 2 的本地 App SQLite schema 与版本化迁移（推荐）；
- B：暂不执行数据库部分，只停留在 Task 1。

未获批准前，不创建 migration SQL、不改变 schema。

### 第三步：执行 M9 Task 2

批准后严格按 TDD 实现：

- `AppPaths`：macOS/Linux 路径解析、注入式测试目录、symlink 防护；
- `AppDatabase`：空库迁移、重复迁移幂等、版本拒绝、升级前备份；
- 表范围只允许 `schema_version`、`repositories`、`jobs`、`job_events`、`preferences`；
- 测试只能使用隔离临时目录，不连接常驻数据库；
- 通过 focused tests 和项目验证后提交推送。

随后依次执行 M9 Task 3–8：仓库注册服务 → 状态/诊断服务 → Loopback API → 启动器 → Web onboarding → clean-wheel 验收。

## 6. 踩过的坑

1. **真实仓库目录是 `/Users/qiming/workspace/CodeWiki`。** 环境上下文中的 `CoDoMoWiki` 是旧路径，不能在旧目录工作。
2. **每次开工先 pull。** README 更新会触发自动截图提交，本地可能在几分钟内落后远端。
3. **测试数不等于完整门禁。** 本次 793 项测试通过，但 pip-audit 新增漏洞，整体仍是 FAILED。
4. **测试计数以 `scripts/verify.sh` summary 为准。**
5. **pnpm 默认镜像没有 audit endpoint。** 审计前端依赖时使用：
   `pnpm --dir web --registry=https://registry.npmjs.org audit --audit-level high`。
6. **Vite/Vitest 配置类型要从 `vitest/config` 导入 `defineConfig`。** 从 `vite` 导入会拒绝 `test` 字段。
7. **console script 不能直接抛 `typer.Exit`。** 独立 `knowledge-app` 入口会出现 traceback；launcher 应返回退出码，由 Typer 命令转换。
8. **`/tmp` 在 macOS 是 `/private/tmp` 的软链。** 涉及根路径安全断言时使用解析后的真实路径。
9. **上游 CLI 会在 CWD 产生 `data/`、`storage/`。** 已加入 ignore，但提交前仍要检查污染。
10. **上游真实包名是 `backend`，且真实仓库 analyze 会原生崩溃。** 不要用 fixture 成功推断 live 成功。
11. **不得把设计 HTML 当成已交付 Web 应用。**
12. **不要重复统计说明文字里的 checkbox 示例。** Local Beta 总数是 251。
13. **只在 `main` 工作，不创建分支或 worktree。**
14. **提交前检查目标仓库、分支和 `git status`，避免把自动截图或临时浏览器产物混入功能提交。**

## 7. 接手命令

```bash
cd /Users/qiming/workspace/CodeWiki
git pull --ff-only
git status --short --branch
git log -5 --oneline --decorate
VERIFY_FAST=1 bash scripts/verify.sh
```

当前预期不是全绿：在升级 `aiohttp` 前，pip-audit 会失败。先关闭该安全问题，再请求 Task 2 数据库授权。

## 8. 本轮结束状态

- 当前功能进度：Local Beta 6/251；
- 当前功能提交：`dfa267d`；
- 交接前远端 HEAD：`ff1437b`；
- 当前完整门禁：FAILED（aiohttp 漏洞）；
- 下一安全动作：升级 `aiohttp` 至 3.14.4 或更高兼容版本；
- 下一功能动作：获批后执行 M9 Task 2。
