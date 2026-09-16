# HANDOFF — 会话交接文档

> 交接时间：2026-09-16（会话结束） ｜ HEAD：`0f639b1`（与 `origin/main` 同步，工作树干净）
> 验证基线：`VERIFY_FAST=1 bash scripts/verify.sh` 全 PASS（**782 passed + 1 opt-in live skipped**，compileall / diff-check / pip-audit 绿；live SKIP 属预期）
> 新会话第一步：`git fetch origin && git status --short --branch` 核对是否有并行推进，再读本文与 [docs/README.md](docs/README.md)。

---

## 一、当前任务状态（本会话做了什么）

本会话（2026-09-16）是**展示层 + M8 准备**会话，六条提交线全部完成并推送，`782 tests` 全绿：

1. **演示与 README 门面**（`adaa907`）：五类型 fixture 构建跑通生产管线（partial，3 verified + 2 诚实 insufficient）、HTML Wiki 打开展示、三张真实截图、README 全面重建（徽章/Mermaid×3/截图/定位表）。
2. **展示层 v2 设计与实施**（`4b93349` 设计 → `3bdc657` 实施）：三轮竞品调研（DeepWiki/dbt docs/Quartz/TiddlyWiki/coverage.py/OpenAPI/MCP 官方/Backstage）→ 用户四项决策（permalink 走 init config、立即实施、Ask 用 evidence-only、按可托管设计）→ 落地：`web_url` config + evidence permalink、单文件 HTML 大改（双主题/类型过滤/覆盖率条/Ask）、`exports/site/` 多页静态站点、serve 站点服务、MCP 合规三动作（structuredContent/意图化描述/provenance 头）。
3. **展示层 v3 三阶段**（`967e22d` 设计 → `f9359d0`/`9492a47`/`ed8ece7`）：F1-F3 typed 页证据引用 + Claim 级 Ask + insufficient 诚实层；F4-F6 status 过滤 + 响应式 + overlay 徽章；F7-F10 世代时间线 diff（history.html）+ Related 卡局部 SVG + serve `/api/preview` 双模 Ask + 静态托管 runbook（[docs/runbooks/2026-09-16-static-hosting.md](docs/runbooks/2026-09-16-static-hosting.md)）。
4. **M8 基准冻结**（`5ac851e`）：四项决策按用户授权自主定稿（[设计文档 §8](docs/superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md)）——click/flask/requests 任务池、Claude Code headless、低档 60k≈5.4M、两臂。
5. **M8 harness**（`f41adc7`）：[benchmark/](benchmark/README.md) 零依赖（不进 wheel）——任务清单校验、dryrun/claude-code 后端、fail-to-pass 机器判定、McNemar 精确 + Wilcoxon 符号秩、CLI runner；**dry-run 全流程可跑**，真实路径等 key。
6. **半 live 实测**（`0f639b1`）：三发现入知识库（见"卡住的问题"）+ 展示层规模验证（34 对象 0.12s 编译、40 页 527KB、确定性成立）。

## 二、已完成的内容（关键事实）

### 2.1 展示层 as-built（不可回退红线）

- **单源双渲染**：`_render_page_bodies` 让单文件 HTML 与 site/ 共享同一份页面渲染，视图不可能漂移出矛盾；**确定性编译**有测试守着（两次 compile 逐字节一致）。
- 交付三段：`exports/repo-wiki.html`（单文件归档件）/ `exports/site/`（多页可托管站点：index 目录表 + history.html + 每对象详情页）/ `knowledge serve`（回环只读 + `/api/preview` 端点）。
- Ask 双模：serve 环境探测 `/api/preview` 升级 server-backed 预览；静态托管回落编译时内嵌的 Claim 级客户端检索。均 evidence-only（无生成式）。
- permalink：`init --web-url` → config 强校验 → `{web_url}/blob/{commit}/{path}#L{s}-L{e}`，module/typed/sources 页全覆盖。
- 关系逻辑单源：`compiler/relations.py` 供 MCP `knowledge_get_related` 与站点 Related 卡共享。
- 覆盖率诚实层：吃 runs 最新记录的 `insufficient_evidence` 终态（灰红段 + 无链接行）。

### 2.2 演示与复现（临时产物随 /tmp 清理，方法在案）

- 五类型演示构建 `DemoWorker` 三手法（空证据包抛 `InsufficientEvidence` / id-scope-envelope 全文替换重绑 / `(path,start,end)` 证据 id 翻译；typed draft 过滤 `verification` 字段、`validity` 显式赋 None）——权威参考 `tests/integration/test_real_provider_slice.py` 与 `tests/orchestrator/test_runner.py`。
- 截图生成：两规则 CSS（先全隐藏再按 id 显示，**勿用链式 `:not()`**）+ scrollHeight 探针（onload 写 `<title>` 再 `--dump-dom` 读回）+ Chrome headless `--force-device-scale-factor=2`。
- 半 live 复现：脚本 `/private/tmp/codewiki-semilive-run.py`（重启即失）= clone/指向仓库 + `CodeWikiEvidenceProvider(CodewikiRunner())` + **`ensure_index` 先行** + DemoWorker；跑时需 `PATH="$PWD/.venv/bin:$PATH"`。

## 三、卡住的问题（全部等外部输入，无技术阻塞）

| # | 事项 | 卡在哪 | 解锁后动作 |
|---|--- |--- |--- |
| 1 | **上游 codewiki 0.6.5 段错误** | tenacity/structlog/click/jsonschema/requests 五个真实中型仓库 `analyze` 全部 SIGSEGV/SIGBUS（微型与 84 文件合成仓库正常）。**阻塞 live 冒烟与 M8 真实仓库路径** | 向上游报 issue（附最小复现）或等 0.7+；升级前必须重跑 Phase 0 spike 实测（纪律已有）。证据见 [upstream 运行知识](docs/knowledge/industry/upstream-codewiki.md) |
| 2 | **接入层 entry_points 匹配缺口** | 真实 `graph explore` 输出归一化后与规划 topic 匹配为空 → 目标全落 insufficient_evidence。fixture 归一化与真实输出形状有差异 | live 阶段与真实 LLM worker 一起联调（`providers/codewiki.py` 的 `_select_entries`） |
| 3 | **live 冒烟** | 等 `KNOWLEDGE_EXTRACTION_MODEL` + API key + codewiki 修复 | 按 [runbooks/2026-09-02-live-smoke.md](docs/runbooks/2026-09-02-live-smoke.md) 走 |
| 4 | **M8 实验执行** | 等 API key（harness/统计/任务清单全就绪，dry-run 可跑） | 按 [benchmark/README.md](benchmark/README.md) 真实模式跑，产物入 `benchmark/results/`，报告入 docs/materials/ |

## 四、下一步计划（按优先级）

1. **跟进上游崩溃**（不花钱）：整理最小复现（真实仓库 shallow clone + `codewiki analyze` exit 139），向上游报 issue；同时用合成仓库继续可做的验证。
2. **有 key 后**：先修 entry_points 匹配缺口（联调）→ live 冒烟 → M8 实验执行（预注册判定勿事后改）。
3. **M8 之后**：V0.1.x（Git URL/clone 缓存/私有凭证）、V0.2（多仓库）——见规格 §21，不提前实现。
4. **文档持续维护**（轻量）：知识文档修正追加 Revision History；新计划进 `active/`；重大决策追加 decision-log 编号；测试计数以 `verify.sh` 尾行为准。

## 五、踩过的坑（给下一个会话/Agent 的实操警告）

1. **会话快照会撒谎**：多 agent 仓库，接手前先 `git fetch` + 重新核对；完成状态以门禁提交号为准，不信 checkbox。
2. **CSS 链式 `:not()` 是 AND 语义**：两条叠加 = 全隐藏。保留多个元素必须"先全隐藏 + 按 id 列表 display:block"两条规则。
3. **测试计数以 verify.sh 实测为准**：`pytest tests/` 与 verify.sh 套件范围不同（本日 782 vs 775 的教训出现两次）；文档计数抄 verify.sh 尾行。
4. **批量替换脚本断言失败 = 整体未写盘**：heredoc python 脚本里任一 assert 失败会在 write_text 前退出，"打印了成功消息"不代表落盘——每个替换后 grep 验证关键产物；heredoc 里 old 串尾随空格是断言杀手，复杂改动用 Edit 工具。
5. **`RunStore.active_run()` 构建完成后返回 None**：读最新 run 用 `next((r for r in records if r.active), records[-1] if records else None)`（与 MCP `_status` 一致）。
6. **合成仓库生成勿对"生长中的集合"迭代**：`for i: for py in rglob()` 会把上一轮 variant 也复制进去（指数爆炸）；先固定 originals 列表。fixture 副本要重新 `git init`（否则 `git add` 128）。
7. **codewiki CLI 会在 CWD 落 `data/`、`storage/` 目录**：手动跑 analyze 后检查仓库根是否被污染；本会话已清理一次（未提交）。
8. **subprocess 找不到 `codewiki`**：它在 `.venv/bin`，跑接入脚本要 `PATH="$PWD/.venv/bin:$PATH"`；macOS 无 `timeout` 命令（用工具自身 timeout）。
9. **迁移目录前必须扫代码引用**（`rg "docs/" src tests scripts`）；**相对链接深度要跑检查器**（以文档所在目录为基准，不是仓库根）；归档（materials/archives/）豁免。
10. **Edit 工具偶发匹配失败**（字节一致仍报 not found）：重新 Read 刷新文件状态；macOS 无 `cat -A` 用 `cat -et`；`/tmp` 是 `/private/tmp` 软链，Edit 用全路径。
11. **项目不用 emoji commit 风格**：纯文本 conventional commits，正文 72 字符内换行；推送前 `verify.sh` 必须绿（main-only，无分支）。

## 六、下个会话快速上手

```bash
cd /Users/qiming/workspace/CodeWiki
git fetch origin && git status --short --branch   # 预期：clean、与远程同步（0f639b1）
bash scripts/verify.sh                             # 预期：VERIFY: PASS（782+1skip，live SKIP 属预期）
```

然后：读本文 → [README.md](README.md)（门面，五图）→ [docs/README.md](docs/README.md)（文档地图）。若跟进上游崩溃：`docs/knowledge/industry/upstream-codewiki.md` 的半 live 实测节是全部证据；若做展示层演示：按本文 2.2 方法重做（临时产物已随 /tmp 清理）；若有 API key：按第三节解锁路径直接开工。
