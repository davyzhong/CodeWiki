---
status: maintained
last-reviewed: 2026-09-16
sources:
  - docs/spikes/codewiki-public-surface.md（Phase 0 实测报告，结论 go）
  - tests/fixtures/codewiki/0.6/cli-observations.json（实测观测，可再生 go 判定）
  - materials/research/reference-products.md（上游架构与边界）
  - materials/skills/upstream-codewiki/（上游 Codex Skill 快照，MIT，提交 7be8f70）
---

# 上游依赖：PorunC/CodeWiki（upstream-codewiki）

本项目的证据引擎默认实现依赖上游 CodeWiki（PyPI 包 `codewiki`）。集成纪律见 [decision-log](../product/decision-log.md) D-001/D-002；本文是关于上游的运行知识。

## 架构管线（调研所知）

```
Repository → RepoScanner → tree-sitter AST → Code Graph（符号/调用/导入/继承/路由/配置引用）
  → 社区检测 → FTS（可选向量）→ GraphRAG → Wiki / Q&A / MCP / Codex Skill
```

- 多语言：Python/TypeScript/Java/Go/Rust/C/C++/C# 等（tree-sitter）；
- 确定性提取为主，LLM 负责组织与解释（AST 与源码是事实来源）；
- Wiki 页面通过引用校验后才置 `generated`；Git diff + 文件哈希做增量，受影响页标 stale；
- 存储 SQLite（Lite：`.codewiki/codewiki-lite.sqlite3`），支持 PostgreSQL/pgvector；
- MIT 许可，版本 0.6.x 阶段（我们锁定 `>=0.6,<0.7`，0.7+ 会被 preflight 拒绝）。

## 公开面合同（Phase 0 实测，`codewiki 0.6.5`）

12 项必需能力全部 supported（MCP 回退未启用）：

| 能力 | 来源命令 | 备注 |
|---|---|---|
| 版本 | `package_version`（`--version` 不存在，exit 2） | 用 `importlib.metadata` 探测 |
| 仓库注册 | `repos add <path> --json` | 返回稳定 repo id（如 `85f16b68ab657f68`） |
| 全量索引 | `analyze <repo> --json` | status=done + 节点/边/社区计数 |
| 增量索引 | `update <repo> --json` | mode=incremental + 变更计划（git_diff+sha256） |
| 仓库调研 | `repos scan <repo> --json` | 文件/语言/sha256/大小清单 |
| 符号检索 | `graph search <sym> --repo --json` | 节点含 file_path/start_line/end_line/signature |
| 主题探索 | `graph explore <topic> --repo --json` | entry_points + relationships（calls/defines/exports/references）+ source_sections |
| 影响分析 | `graph affected --stdin --json`（喂变更文件） | 受影响文件/节点/测试/wiki 页 |

原始 JSON 形状（字段名、metadata 结构、source_sections 带行号内容）以 `tests/fixtures/codewiki/0.6/cli-observations.json` 为准——适配层只认这个实测合同，不认文档猜测。

## 上游 Codex Skill 的工作流（快照研究价值）

上游 Skill 让 Codex 按"计划队列 → 每页取紧凑证据（`--limit` 有界，避免整包 GraphRAG 灌入）→ 只依据证据写页 → save → citation 校验 → HTML 导出"工作，并明文禁止编造路径/API/架构事实。这直接启发了本项目 Evidence Pack 有界预算（D-016）与 source-grounded 模式（patterns P3）。

## 集成边界（红线）

1. 只调用公开 CLI/MCP/HTTP，参数走数组不拼 shell；
2. 禁止 `import codewiki/backend.*`，禁止查询其 SQLite/PostgreSQL 表；
3. 上游返回的路径/源引用先验证（仓库根内、相对、非 symlink）再本地读源码；
4. 提供方 hint 只增强、不替代本地变更检测；
5. 上游索引失败时：安全失效照常提交，不做语义重生、不谎报发现。

## 2026-09-16 半 live 实测发现（Python 3.13 / codewiki 0.6.5）

1. **真实中型仓库 analyze 原生崩溃（2026-09-16 已诊断到最小复现）**：tenacity、structlog、click、jsonschema、requests 五个公开仓库 `codewiki analyze` 全部段错误（exit 138/139，零输出）；微型 probe fixture（≈10 文件）与 84 文件合成仓库正常。**阻塞 live 冒烟与 M8 真实仓库路径**。
   - 诊断结论：单文件直连 `PythonAstParser.parse` 即崩（无 CLI/无 cache/无线程），50 次全新子进程 50/50 崩、信号混合 SIGSEGV×28 + SIGBUS×22——典型 C 层内存未定义行为；强制单 worker 仍崩（排除 worker 线程竞争）；faulthandler 常见崩溃帧 `ast_cache.write:52 → dataclasses.asdict`，但 `AstSymbol` 字段全为纯 Python 类型，指向 tree-sitter 捕获层（py-tree-sitter 0.26.0 + CPython 3.13.15 + macOS arm64 组合）。
   - 最小复现：requests/models.py ddmin 压至 258 行语法完整文件（`materials/origin/codewiki-segfault-repro-258.py`）；触发是结构性的（import 块 + TYPE_CHECKING + Final + `@overload/@staticmethod` 栈的整体），手写小片段不触发。
   - Issue 已发布（用户确认）：https://github.com/PorunC/CodeWiki/issues/2（草稿存档 `materials/origin/2026-09-16-codewiki-segfault-issue-draft.md`）。处置：发 issue 或等 0.7+；升级前必须重测（重跑 Phase 0 spike 流程），无假设升级。
2. **公开面 CLI 合同在非 fixture 仓库成立**：84 文件合成仓库上 `repos add`/`analyze`/`repos scan`/`graph search`/`graph explore` 全链路真实跑通（索引 1.4s、inspect 1.3s、规划 5 目标）。
3. **接入层缺口（2026-09-16 已修复，三层根因）**：① `graph search/explore "*"` 在真实 CLI 上是无效查询（fixture 伪造了通配行为）——inspect 改为按源文件名词探测 search（≤8 词，跳过 `__init__*` 前缀），并过滤 file 型节点（file 命中不是符号）；② `.knowledge/` 在同仓库第二次构建后被上游增量索引收入（上游无排除参数）——explore/search/证据读取三处读侧防御过滤；③ 预算语义分层：零匹配 → 空包（worker 判 insufficient）、有匹配但一项装不下 → raise（配置错误 fail-closed）、多匹配超额 → 按确定性序截断到预算内。修复后干净索引上半 live 达成 partial（flow/rule 2 对象 verified、7 页编译、FTS 索引）；module 目标残余失败是 DemoWorker 假件的证据 id 翻译局限（属真实 LLM worker 联调范围）。

升级到 0.7+ 前：公开面合同必须重新实测（重跑 Phase 0 spike 流程），无假设升级。

## Revision History

- 2026-09-16 半 live 实测追加：五仓库 analyze 崩溃、CLI 合同在合成仓库成立、entry_points 匹配缺口。
- 2026-09-12 从 spikes 报告、实测 fixture 与调研笔记提炼建卷。
