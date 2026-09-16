# HANDOFF — 会话交接文档

> 交接时间：2026-09-16（会话结束，当日第三次更新） ｜ HEAD：`4da9bbb`（与 `origin/main` 同步，工作树干净，CI 绿）
> 验证基线：`VERIFY_FAST=1 bash scripts/verify.sh` 全 PASS（**787 passed + 1 opt-in live skipped**；live SKIP 属预期）
> 新会话第一步：`git fetch origin && git status --short --branch` 核对并行推进，再读本文与 [CLAUDE.md](CLAUDE.md)（会话入口）/ [docs/README.md](docs/README.md)（文档地图）。

---

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
- **CLAUDE.md**：新会话入口（第一步/规则/红线/文档表）；**decision-log 至 D-025**；**787** 为当前基线计数。
- **.gitignore** 已含 `/data/`、`/storage/`（codewiki CWD 副产物，曾两次污染提交）。

### 2.3 上游崩溃证据链（全部入库）

- 最小复现文件 `docs/materials/origin/codewiki-segfault-repro-258.py`；issue 草稿（含双 faulthandler 栈与 50 次信号统计）`docs/materials/origin/2026-09-16-codewiki-segfault-issue-draft.md`（status: published）；诊断结论在 [upstream-codewiki.md](docs/knowledge/industry/upstream-codewiki.md)。

## 三、卡住的问题（全部等外部输入，无技术阻塞）

| # | 事项 | 等什么 | 解锁后动作 |
|---|--- |--- |--- |
| 1 | **上游崩溃修复** | [PorunC/CodeWiki#2](https://github.com/PorunC/CodeWiki/issues/2) 的回复/发版 | 定期查 issue；有新版本按纪律重跑 Phase 0 spike 实测后升级 |
| 2 | **live 冒烟** | `KNOWLEDGE_EXTRACTION_MODEL` + API key + codewiki 修复 | 按 [runbooks/2026-09-02-live-smoke.md](docs/runbooks/2026-09-02-live-smoke.md)；module 目标的 DemoWorker 残余失败在此阶段由真实 LLM worker 接管 |
| 3 | **M8 实验执行** | API key（harness/dry-run 全就绪，[benchmark/README.md](benchmark/README.md)） | 真实模式跑；预注册判据勿事后改 |

## 四、下一步计划（按优先级）

1. **等输入型**：issue #2 跟进；API key 到位后 live 冒烟 → M8 执行（顺序勿倒）。
2. **可选增强**（无输入依赖、低优先）：demo DemoWorker 的证据 id 翻译升级为真实 pack 形状（sha256: id 直接透传），让演示构建 module 也 verified；知识库 system/behavior-reference 补展示层新命令面（--web-url、site 结构）。
3. **M8 之后**：V0.1.x / V0.2（见规格 §21，不提前实现）。
4. **文档维护**：知识文档修正追加 Revision History；计数以 verify.sh 尾行为准（当前 787）。

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
git fetch origin && git status --short --branch   # 预期：clean、与远程同步（4da9bbb）
bash scripts/verify.sh                             # 预期：VERIFY: PASS（787+1skip，live SKIP 属预期）
gh issue view 2 --repo PorunC/CodeWiki             # 可选：查上游 issue 是否有回复
```

然后：读本文 → [CLAUDE.md](CLAUDE.md) → [README.md](README.md)。若带来了 API key：先确认 codewiki 崩溃是否已被上游修复（issue #2），再走 live 冒烟 runbook；若继续离线工作：第四节第 2 条是仅剩的无输入任务。半 live/演示复现方法见 git 历史版本 `042b8a1` 的 HANDOFF §2.2（DemoWorker 三手法与截图探针法）。
