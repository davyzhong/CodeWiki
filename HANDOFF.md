# HANDOFF — 会话交接文档

> 交接时间：2026-10-11（项目冻结续审与恢复执行） ｜ 已推送修复基线：`12c92cc`
> 验证基线：`VERIFY_FAST=1 bash scripts/verify.sh` 全 PASS（**790 passed + 1 opt-in live skipped**；live SKIP 不是 PASS）
> 新会话第一步：`git fetch origin && git status --short --branch` 核对并行推进，再读本文与 [CLAUDE.md](CLAUDE.md)（会话入口）/ [docs/README.md](docs/README.md)（文档地图）。

---

## 零、2026-10-11 当前权威状态

1. **V0.1：有条件可技术冻结。** CLI、七个只读 MCP 工具、Canonical IR、生命周期、human overlay、三视图和静态站点均已交付；离线门禁 790+1。真实 live 与 M8 A/B 尚无完成证据。
2. **整个项目：不可关闭。** Local Beta M9–M14 六份计划共有 251 个行首 checkbox 执行步骤，当前 `0/251`。旧文档中的 259 是把说明性文字误计入/估算导致，已由源计划重算纠正。
3. **下一执行入口：M9 Task 1。** 用户已明确要求从中断处继续，不把 M9–M14 取消、延期或转历史；先写打包契约失败测试，再按计划推进。
4. **本轮实际修复：** 浏览器审计发现并关闭 History `esc` 初始化顺序、静态站点 `nav` 样式污染、`body` flex 布局污染；升级 `multidict`、`pyjwt`、`urllib3` 关闭 18 条漏洞。提交 `12c92cc` 已推送。
5. **本轮证据入口：** [关闭审查](docs/reviews/2026-09-25-project-closure-review.md)、[追溯矩阵](docs/knowledge/product/traceability.md)、[审计证据](docs/materials/validation/project-freeze-2026-09-25/)、[归档清单](docs/materials/archives/2026-09-25-project-freeze-manifest.md)。
6. **未授权治理项：** `ci.yml` 尚未 frozen sync/pip-audit；`screenshot.yml` 仍监听不存在的 `README.zh.md` 并每日自动写回。两项都属于 CI/CD 修改红线，未擅自执行。
7. **上游状态：** PorunC/CodeWiki issue #2 截至 2026-10-11 仍 OPEN、0 comments；最新 GitHub release 仍 v0.6.3。不得把真实中型仓库路径写成 PASS。

### 下一会话固定动作

```bash
cd /Users/qiming/workspace/CodeWiki
git pull --ff-only
bash scripts/verify.sh
```

随后读 [Local Beta 总计划](docs/superpowers/plans/active/2026-09-17-local-beta-master-plan.md) 与 [M9 详细计划](docs/superpowers/plans/active/2026-09-17-m9-local-product-foundation.md)，从 M9 Task 1 开始。若要先闭合 CI/CD，两项必须一次只做一个选择题取得用户批准。

---

## 一、2026-09-17 历史基线（已被上节取代）

用户已正式批准下一阶段设计：**个人开发者、本地单节点、零服务器依赖；真实可信度验证与 Beta 体验并行；按可信垂直切片推进，不设工期。** Web、CLI、MCP 共享一套应用服务；`.knowledge/` 中的 Canonical Knowledge / Evidence / Human Overlay 仍是唯一权威，App SQLite、FTS、页面和未来可能的向量均为可重建投影。

本次已完成：

1. 批准设计归档：[Local Beta 产品规格](docs/superpowers/specs/2026-09-17-local-beta-product-design.md) + [完整 HTML](docs/design/2026-09-17-local-beta-design.html)。
2. 执行计划入库：[总计划](docs/superpowers/plans/active/2026-09-17-local-beta-master-plan.md) + M9–M14 六份子计划，共 48 个 Task、251 个执行步骤，覆盖功能、解析、架构、界面、Web/CLI/MCP、测试、真实仓库和发布验收。
3. 决策日志新增 D-026（本地单节点形态）与 D-027（重大设计同步 README/文档铁律）；`AGENTS.md` 已将 D-027 写成所有后续 Agent 的项目工作流要求。
4. README 和 docs 总索引已链接正式规格与计划；行业横评、完整设计图和详细路线继续保留。

**实现尚未开始。下一执行入口是 M9 Task 1**，严格按 [M9 计划](docs/superpowers/plans/active/2026-09-17-m9-local-product-foundation.md) 从失败测试开始。下方关于“全部事项等外部输入”的旧判断已被本节取代：M9–M13 可以离线推进；上游崩溃改由 M10 的进程隔离与降级 Provider 主动解决，不再只是等待。

## 一、当前任务状态（上次交接 `042b8a1` 之后做了什么）

上次交接后本会话又完成四条线（12 个提交）：

1. **ARIA 补齐**（`46e269c`）：chips `aria-pressed`、目录表头真按钮化 + `aria-sort`、Ask 区 `aria-live`、输入与主题按钮 `aria-label`——无框架条件下补齐可访问性义务。
2. **全局 review 落地**（`dd3fdf3`→`8495aaf`）：新增 **CI**（`.github/workflows/ci.yml`：compileall + 离线套件 + 链接检查）、**CLAUDE.md** 会话入口、`scripts/check_links.py` 入库；decision-log 补 **D-024**（展示层三段交付）/ **D-025**（M8 冻结）；展示层设计移 historical；CI 首跑抓到两个终端宽度敏感的 help 测试（根因：无界依赖拉到新版 rich/typer）→ 改为命令元数据断言。
3. **用户两项决策执行**（`af7780f`）：清三个遗留 console 入口（spikes/vertical_slice 模块保留）；全部直接依赖加上界（typer<1 等）。
4. **上游崩溃跟进 + U3 修复**：
   - 诊断深化（`e776ecf`）：faulthandler 定位崩溃帧（`ast_cache.write→asdict`，**非线程竞争**——单 worker 同帧崩）；单文件复现（requests/models.py 直连 parser 50/50 崩、SIGSEGV×28+SIGBUS×22 混合=典型 C 层 UB）；ddmin 压至 **258 行语法完整最小复现**。
   - **issue 已发布**（用户确认，红线流程）：[PorunC/CodeWiki#2](https://github.com/PorunC/CodeWiki/issues/2)。
   - **U3 接入层修复**（`4da9bbb`）：三层根因（`"*"` 通配查询真实 CLI 无效 / `.knowledge/` 二次构建被增量索引 / 预算整包拒绝误杀）→ inspect 改源文件名词探测 search、读侧三处过滤内部状态路径、预算语义三分（零匹配空包/装不下 raise/超额截断）；**干净索引半 live 达成 partial**（flow/rule 2 对象 verified、7 页、FTS 索引）。

## 二、已完成的内容（关键事实）

### 2.1 U3 修复后的接入层语义（as-built，勿回退）

- **inspect**：symbols 来自按源文件 stem 探测 `graph search`（≤8 词、跳过 `__init__*`），file 型节点过滤（不是符号）；planner 拿到真实符号。
- **读侧防御**：`normalize_explore`/`normalize_search`/`_read_evidence` 三处滤 `.knowledge/` 路径（上游无排除参数、二次构建必污染）。
- **预算三分**：零匹配→空包（worker 判 InsufficientEvidence——源接地语义在 worker 层）；有匹配但一项装不下→`ValueError`（配置错误 fail-closed）；超额→按确定性序截断。
- **`_select_entries`**：匹配 seed 原文、点分尾段、文件路径（architecture_seeds 是文件清单）。
- **测试冻结语义优先**：本会话三次"改进"被既有测试正确拦下（planner 空符号不编造 / 空包合法 / 装不下要报错）——改行为前先看测试意图。

### 2.2 工程基础设施（本会话新增）

- **CI**：push/PR 触发，三步（compileall、离线套件、check_links）——约 1.5 分钟；依赖上界已加，help 断言已环境无关。
- **当时状态**：CLAUDE.md 新增会话入口；decision-log 当时至 D-025；当时验证基线为 787。当前状态以上方 2026-10-11 权威节为准。
- **.gitignore** 已含 `/data/`、`/storage/`（codewiki CWD 副产物，曾两次污染提交）。

### 2.3 上游崩溃证据链（全部入库）

- 最小复现文件 `docs/materials/origin/codewiki-segfault-repro-258.py`；issue 草稿（含双 faulthandler 栈与 50 次信号统计）`docs/materials/origin/2026-09-16-codewiki-segfault-issue-draft.md`（status: published）；诊断结论在 [upstream-codewiki.md](docs/knowledge/industry/upstream-codewiki.md)。

## 三、历史外部依赖（不再阻塞 M9 启动）

| # | 事项 | 等什么 | 解锁后动作 |
|---|--- |--- |--- |
| 1 | **上游崩溃修复** | [PorunC/CodeWiki#2](https://github.com/PorunC/CodeWiki/issues/2) 的回复/发版 | 定期查 issue；有新版本按纪律重跑 Phase 0 spike 实测后升级 |
| 2 | **live 冒烟** | `KNOWLEDGE_EXTRACTION_MODEL` + API key + codewiki 修复 | 按 [runbooks/2026-09-02-live-smoke.md](docs/runbooks/2026-09-02-live-smoke.md)；module 目标的 DemoWorker 残余失败在此阶段由真实 LLM worker 接管 |
| 3 | **M8 实验执行** | API key（harness/dry-run 全就绪，[benchmark/README.md](benchmark/README.md)） | 真实模式跑；预注册判据勿事后改 |

## 四、下一步计划（以 Local Beta 总计划为准）

1. **立即执行 M9**：本地产品基座——包契约、AppPaths/App DB、repository service、共享 status/diagnostics、FastAPI、`knowledge app`、React onboarding、clean-wheel smoke。
2. **随后 M10–M13**：可靠解析 → 建库任务闭环 → 知识阅读 Beta → Ask/Agent 三端一致；每个里程碑退出前更新 README/docs/HANDOFF 并留真实仓验证。
3. **M14**：技术前置全部通过后执行冻结 M8、性能/故障矩阵、安装升级和 Beta 发布。API key 只在此处和需要真实模型的 live 证据中成为外部输入。
4. **上游 issue #2**：继续跟进，但不得以等待上游代替 M10 的崩溃隔离、稳定错误与降级证据方案。

## 五、踩过的坑（给下一个会话/Agent 的实操警告）

1. **会话快照会撒谎**：多 agent 仓库，接手前先 `git fetch` 重新核对；完成状态以门禁提交号为准。
2. **测试冻结的语义优先于改进直觉**：本会话三次被拦（planner 不编造/空包合法/装不下要报错）——改行为前先读测试意图，别急着改测试。
3. **批量 heredoc 脚本断言失败=整体未写盘**：每个替换后 grep 验证；old 串尾随空格是断言杀手；复杂改动用 Edit 工具。
4. **codewiki CLI 的坑三连**：真实包名是 `backend`（`from backend.app.cli import main`）；会在 CWD 落 `data/`、`storage/`（已 gitignore，仍需提交前检查）；`analyze` 真实仓库段错误（issue #2），诊断用 `python -X faulthandler`。
5. **管道后的 `$?` 是管道尾命令的**：测段错误 exit code 要重定向后单独 echo，别接管道。
6. **测试计数以 verify.sh 尾行为准**（`pytest tests/` 与套件范围不同）；**依赖必须加上界**（无界 rich/typer 曾让 CI 行为漂移）。
7. **`RunStore.active_run()` 构建完成后返回 None**：读最新 run 用 active-or-last 回退。
8. **合成仓库生成勿对生长中的集合迭代**（指数爆炸）；fixture 副本要重新 `git init`。
9. **CSS 链式 `:not()` 是 AND**；**迁移目录前扫代码引用**；**链接深度以文档所在目录为基准**（`scripts/check_links.py` 已入库）。
10. **Edit 偶发匹配失败**：重新 Read 刷新；`/tmp` 是 `/private/tmp` 软链，用全路径；macOS 无 `cat -A`/`timeout`。
11. **提交纪律**：纯文本 conventional commits、正文 72 字符；推送前 verify.sh 绿（main-only）；`git add -A` 前先 `git status` 扫污染。

## 六、下个会话快速上手

```bash
cd /Users/qiming/workspace/CodeWiki
git fetch origin && git status --short --branch   # 预期：clean、main 与 origin/main 同步
bash scripts/verify.sh                             # 当前预期：VERIFY: PASS（790+1skip；live SKIP 仍须明确记录）
gh issue view 2 --repo PorunC/CodeWiki             # 可选：查上游 issue 是否有回复
```

然后：读本文 → [Local Beta 总计划](docs/superpowers/plans/active/2026-09-17-local-beta-master-plan.md) → [M9 详细计划](docs/superpowers/plans/active/2026-09-17-m9-local-product-foundation.md)，从 M9 Task 1 开始。API key 不再是启动下一阶段开发的前置条件。
