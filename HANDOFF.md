# HANDOFF — 会话交接文档

> 交接时间：2026-09-16（同日第二次更新：展示层 v2 已实施） ｜ HEAD：见 `git log -1`（展示层实施提交）
> 验证基线：`VERIFY_FAST=1 bash scripts/verify.sh` 全 PASS（**782 passed + 1 opt-in live skipped**，compileall / diff-check / pip-audit 绿；live SKIP 属预期）
> 新会话第一步：`git fetch origin && git status --short --branch` 核对是否有并行推进，再读本文与 [docs/README.md](docs/README.md)。

---

## 一、当前任务状态（本会话做了什么）

本会话（2026-09-16）两次大交付：**①演示与 README 门面**（五类型 fixture 构建 + 三张真实截图 + README 重建，`adaa907`）；**②展示层 v2 设计与实施**：

1. **三轮调研**（本地知识库 + DeepWiki/dbt docs/Quartz/TiddlyWiki/coverage.py/OpenAPI/MCP 官方/Backstage）→ 设计文档 [plans/active/2026-09-16-presentation-layer-design.md](docs/superpowers/plans/active/2026-09-16-presentation-layer-design.md)（`4b93349`）。
2. **用户四项决策**：permalink 走 init config；展示层立即实施（缺决策时参考竞品自主定）；Ask 用 evidence-only 检索式；按可托管设计。
3. **实施落地**（全部完成，765 tests 绿）：
   - config 新增 `web_url`（http(s) 裸根、拒 userinfo/query；`init --web-url`）
   - evidence permalink：`_evidence_permalink` → module/sources 页 `{web_url}/blob/{commit}/{path}#L{s}-L{e}`
   - 单文件 HTML 大改：CSS 变量双主题+手动切换、类型过滤 chips、五类型覆盖率条（诚实 none 态）、Ask(evidence-only) 视图（客户端检索+snippet+诚实空态）、GFM 表格渲染、`.md→.html` 链接改写
   - `exports/site/` 多页静态站点（index 目录表：搜索/过滤/列头排序；每对象详情页；相对路径可托管）+ `_render_page_bodies` 单源双渲染防漂移
   - serve 升级：site 目录静态服务（`.html` 白名单 + 路径穿越/symlink 防护），无 site 时回退单文件
   - MCP 合规：`structuredContent` 双返回、三个工具描述意图化、全部工具 payload 加 `provenance` 头（generation/commit/freshness）
4. README 更新（四张新截图含 site-catalog、--web-url 快速上手）。
5. **M8 基准冻结 + harness 落地**（5ac851e/f41adc7）：四项决策按授权自主定稿（click/flask/requests 任务池、Claude Code headless、低档 60k≈5.4M、两臂）；`benchmark/` 零依赖 harness（任务清单校验/可换后端/fail-to-pass 判定/McNemar+Wilcoxon 配对统计/CLI runner），dry-run 全流程可跑，真实路径等 API key。
6. **半 live 三发现**：① codewiki 0.6.5 在五个真实中型仓库 analyze 段错误（阻塞 live/M8 真实仓库，详见 upstream-codewiki.md）；② CLI 公开面合同在 84 文件合成仓库真实跑通；③ 真实 explore 输出的 entry_points 匹配缺口致目标全落 insufficient（接入层联调属 live 阶段）。展示层规模验证：34 对象 0.12s 编译、40 页 527KB 站点、确定性成立。
7. **V3 三阶段连续实施完成**（同日，f9359d0/9492a47/ed8ece7）：F1-F3 typed 页证据引用+Claim 级 Ask+insufficient 诚实层；F4-F6 status 过滤+响应式+overlay 徽章；F7-F9 history 时间线 diff+Related 卡局部 SVG+serve /api/preview 双模 Ask；F10 静态托管 runbook（docs/runbooks/2026-09-16-static-hosting.md）。关系逻辑抽至 compiler/relations.py 供 MCP 与站点共享。

## 二、已完成的内容

### 2.1 演示构建的复现方法（临时文件会被系统清掉，方法记在这里）

- 演示脚本当时在 `/tmp/codewiki-demo-build.py`，产物在 `/private/tmp/codewiki-demo/repo/.knowledge/`——**重启后 /tmp 会清空，需要时按下述模式重写**：
- 关键参考：`tests/integration/test_final_gate.py`（make_repository：copytree probe_repo + git init + remote add）、`tests/integration/test_real_provider_slice.py` 的 `StubRealWorker`（重绑模式）、`tests/orchestrator/test_runner.py`（五类型 fixture drafts）。
- `DemoWorker.extract` 的三个关键手法（fixture draft → 真实目标）：
  1. **空证据包直接 `raise InsufficientEvidence(...)`**（`contracts/semantic.py` 导入）→ runner 捕获落 `INSUFFICIENT_EVIDENCE` 终态；
  2. **id/scope/envelope 重绑**：`json.dumps(payload).replace(src_id, target.id)` 全文替换 + scope 七字段 + 请求字段（contract_version/run_id/target_id/…）逐个回填；
  3. **证据 id 翻译**：按 `(path, start_line, end_line)` 从 pack 真实证据建映射表翻译 claim 的 `evidence_ids`；typed draft 还需过滤 claim 里的 `verification` 字段、且 `draft["validity"] = None` 必须**显式赋 None 不能 pop**。
- `verify` 通用实现：回显 `request.claims` 全部 supported（照抄 StubRealWorker.verify）。

### 2.2 截图生成方法（同上，记方法不记临时文件）

- 变体 HTML = 原始 repo-wiki.html 在 `</style>` 前注入两条规则：**先 `main section{display:none}` 再 `main section#KEEP1,main section#KEEP2{display:block}`**；
- 精确测高：`</head>` 前注入 `onload` 把 `document.documentElement.scrollHeight` 写进 `<title>`，用 `--dump-dom` 读回，`--window-size=1440,H`；
- Chrome headless 命令：`--headless --disable-gpu --hide-scrollbars --force-device-scale-factor=2 --virtual-time-budget=4000 --screenshot=OUT file://...`。

### 2.3 此前的项目状态（沿袭，本会话仅核实未动）

V0.1 **技术链全部完成**（M1–M7、恢复计划 Gate 1–8、符合性修复 Task 1–5）；文档库三层治理（`e4f810e`）；上一份交接见 git 历史（`a783e7c` 版 HANDOFF）。生产入口齐备（`knowledge build/update/compile/context/open/serve/status/validate/edit` + `knowledge-mcp` 七只读工具）。完整记录：[timeline](docs/materials/origin/timeline.md)、[完成归档](docs/materials/archives/2026-08-25-completion-archive.md)。

## 三、卡住的问题（全部阻塞在用户输入，无技术阻塞）

| # | 事项 | 等什么 | 解锁后动作 |
|---|---|---|---|
| 1 | **Live 冒烟**（恢复计划唯一保留 opt-in 验收项） | ① `codewiki` 0.6.x 装入 PATH；② `KNOWLEDGE_EXTRACTION_MODEL` + 对应 provider API key；③ 一个干净工作树的真实 Git 仓库 | `bash scripts/verify.sh`（live 阶段自动激活），或按 [runbooks/2026-09-02-live-smoke.md](docs/runbooks/2026-09-02-live-smoke.md) 手动走 |
| 2 | **M8 A/B 基准冻结** | 用户 4 项决策：任务来源（12–20 任务/≥3 仓库）、harness 与模型档、token 预算档位（低 ≈5.4M / 中 ≈10.8M / 高 ≈18M）、是否加 MCP 臂 | 按 [M8 设计草案 §8](docs/superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md) 冻结后实施；判定标准已预注册，勿事后改 |

注意：`verify.sh` 第 5 阶段 SKIP（live 条件缺失）是**预期状态**，不是故障；`REQUIRE_LIVE=1` 可强制失败闭合。

## 四、下一步计划（按优先级）

1. **用户提供环境 → 跑 live 冒烟**（约 1 小时 + 0.5–2M tokens）：成功后把 runbook 第 6 节三样产物（`last-build.json`、`knowledge status` 输出、opt-in 测试尾行）贴回会话归档验收。
2. **用户冻结 4 项决策 → M8 执行**：先写 `plans/active/` 的 harness 实施计划（命名规范：`YYYY-MM-DD-m8-<topic>.md`），再按草案 §3–§7 执行（harness 放顶层 `benchmark/`，不进 wheel）。
3. **M8 之后**：V0.1.x（Git URL/clone 缓存/私有凭证）、V0.2（多仓库）——见规格 §21，明确不提前实现。
4. **文档持续维护**（轻量）：知识文档修正追加 Revision History；新计划进 `active/`、完成后移 `historical/` 并标注；重大决策追加 decision-log 编号。README 的测试计数等数据**以 `verify.sh` 实测为准**，漂移即修。

## 五、踩过的坑（给下一个会话/Agent 的实操警告）

1. **会话快照会撒谎**：多 agent 仓库，任何接手动作前先 `git fetch` + 重新核对，不要信开场快照；完成状态以门禁提交号为准，不信 checkbox。
2. **CSS 链式 `:not()` 是 AND 语义**：`section:not(#a){}` + `section:not(#b){}` 两条叠加 = 全部隐藏（截图主区全空白的根因）。要"保留多个"必须写成 `先全隐藏 + 按 id 列表 display:block` 两条规则。
3. **截图测高用探针别拍脑袋**：注入 onload 把 scrollHeight 写进 `<title>`，`--dump-dom` 读回（virtual-time-budget 下脚本会执行且 DOM 序列化包含修改后的 title）。
4. **Read 本地图片只回 CDN URL 不给画面**：复核截图内容要用视觉模型分析，且其输出可能被截断/误判——下结论前用裁剪图（ImageMagick `-crop` 主内容区）做聚焦复核。
5. **临时脚本不要放在会被自删的目录里**：make_repository 若 rmtree 整个 DEMO 根目录，脚本放 DEMO 内会被删掉自己；脚本放 DEMO 外、只 rmtree REPO 子目录。另外 macOS `/tmp` 是 `/private/tmp` 软链，Edit 工具可能因路径解析失败，用 `/private/tmp/...` 全路径。
6. **zsh 默认不做 word splitting**：`set -- $var` 拿到的是整串；循环处理"名称 参数 参数"列表用 python subprocess 显式参数列表。
7. **迁移目录前必须扫代码引用**：`rg "docs/" src tests scripts` 提前捕获硬编码路径（曾有 Skill 字节一致测试硬编码 `docs/project-materials/`）。
8. **相对链接深度要跑检查器**：用"解析全部 md 相对链接→验证目标存在"脚本收敛零坏链（README 24 链已验）；归档（`materials/archives/`）按冻结历史豁免。
9. **Edit 工具偶发匹配失败**（字节一致仍报 not found）：重新 Read 刷新文件状态后即可成功；macOS 无 `cat -A`，用 `cat -et`。
10. **测试计数以 verify.sh 实测为准（当天重演）**：`pytest tests/` 与 verify.sh 套件范围不同（765 vs 753）；文档计数永远抄 verify.sh 尾行。
11. **项目不用 emoji commit 风格**：纯文本 conventional commits（`docs: …`/`feat: …`），正文 72 字符内换行；推送前 `verify.sh` 必须绿（main-only，无分支）。

## 六、下个会话快速上手

```bash
cd /Users/qiming/workspace/CodeWiki
git fetch origin && git status --short --branch   # 预期：clean、与远程同步（adaa907）
bash scripts/verify.sh                             # 预期：VERIFY: PASS（782+1skip，live SKIP 属预期）
```

然后：读本文 → [README.md](README.md)（新门面，含三图三截图）→ [docs/README.md](docs/README.md)（文档地图）。若用户带来了环境/决策，按第三节解锁路径直接开工；若需要重新演示或重新截图，按第二节 2.1/2.2 的方法重做（临时产物已随 /tmp 清理）；演示仓库 config 已含 web_url=fixture URL，重跑 demo 脚本后需重新写入 config 再 compile 才有 permalink。
