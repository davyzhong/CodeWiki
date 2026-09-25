---
status: frozen-blocked
last-reviewed: 2026-09-25
scope: m8-ab-benchmark
sources:
  - docs/superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md
  - docs/knowledge/methods/benchmark-methodology.md
---

# M8 A/B Benchmark Design（已冻结 v1.0）

> **状态：frozen（2026-09-16 冻结 §8 四项决策，依据用户授权"缺决策信息参考竞对与同行惯例自主决策"）**。执行前置 = live 冒烟通过 + API key 配置（技术前置与凭据前置分离：harness 与 dry-run 不依赖 key，已先行实现）。

**Status:** Frozen v1.0 2026-09-16；工程链全部闭合（origin/main `ab259fa`，752×2 绿），harness 于冻结同日实现（`benchmark/`）。本计划是恢复路线图明确留存的最后一段："Start M8 benchmark work only after every technical gate above passes" 已解锁。

**目的：** 验证产品初心（设计规格 §2/§3）——预先萃取、源码证据支持的仓库知识，能否提高 Coding Agent 的任务成功率（H1），或在成功率相当时降低探索成本（H2）。夹具测试无法替代本验证。

## 1. 臂位设计

| 臂 | 注入物 | 说明 |
|---|---|---|
| Control | 无 | Agent 只见仓库本身 |
| Treatment-A | 启动时注入 `knowledge context "<task>"` 输出（markdown，预算 6000） | 单次注入，不改 harness 配置 |
| Treatment-B（扩展，可选） | 挂载 `knowledge-mcp` 七只读工具 | 按需检索；需 harness 支持 MCP |

v0 最小可执行集 = Control vs Treatment-A；B 在 harness 支持 MCP 且预算允许时追加，用于回答"按需检索是否优于一次性注入"。

## 2. 任务集选择标准（冻结前需逐条核对）

- 仓库：真实公开 Git 仓库，Python ≥10k LOC，测试套件本地可运行（无网络/密钥依赖）；
- 任务：真实 issue/小 feature，验收 = 指定测试从红变绿（或 diff 通过评审脚本），**机器可判定**；
- 规模：12–20 个任务，来自 ≥3 个仓库，难度分层（simple/medium 各半）；
- 排除：依赖外部服务、涉及迁移/破坏性变更、base commit 上知识构建失败的（构建失败本身记为产品缺陷上报，不入集）。

候选来源由用户指定（私有仓库也接受，runbook 流程相同）。

## 3. 执行流程（每任务）

1. checkout 任务 base commit → `knowledge init` → `knowledge build --executor llm` → `knowledge compile`（构建产物留在 `.knowledge/`，禁止任何臂修改或提交它）；
2. 同一 base 上按种子 s∈{1,2,3} 分别运行 Control / Treatment（同一 harness、同一系统提示、同一模型档）；
3. 记录逐次运行 JSONL：`task_id, arm, seed, success, total_tokens, tool_calls, wall_seconds, final_diff_hash, notes`；
4. 汇总：逐任务配对表 + 聚合统计。

## 4. 预注册判定（防事后挑选）

- **H1 主判据：** 配对成功率差 ≥ +10 个百分点（15 任务即 ≥2 个翻转），或 McNemar/精确二项 p<0.10；
- **H2 主判据：** 成功率不降（±1 任务内）且 token 中位数降幅 ≥ 20%（Wilcoxon 符号秩 p<0.10）；
- 任一命中即报告"支持"；两个都不命中 → 如实报告"未验证出收益"，并附质性归因（context 命中率、被引用次数——在 Treatment 的最终 diff/记录中检索知识条目 ID 出现情况）。

## 5. 预算估算（按 15 任务 × 2 臂 × 3 种子）

| 档位 | 每次运行 token 上限 | 总量上限 |
|---|---|---|
| 低（任务小） | 60k | ≈5.4M |
| 中 | 120k | ≈10.8M |
| 高（任务大/卡死） | 200k | ≈18M |

另加一次性成本：每仓库 `knowledge build`（LLM 提取+验证），估算每仓库 0.5–2M tokens。**执行前必须由用户给出预算上限并配置相应 API key。**

## 6. 效度威胁与对策

- 任务污染：Treatment 臂 prompt 明确禁止读取 `.knowledge/` 之外的注入路径；harness 记录全部文件访问；
- 知识过期：知识严格按 base commit 构建，构建后工作区置 clean；
- 小样本：不做总体率断言，只做配对非参检验 + 逐任务呈现；
- harness 偏差：两臂除注入物外逐字节相同；种子只改变采样温度侧。

## 7. 产物与存放

- harness 脚本放顶层 `benchmark/`（不进 wheel，`pyproject` 不引用）；
- 原始 JSONL + 汇总 markdown 存 `benchmark/results/<date>/`；
- 报告写入 `docs/materials/`，结论无论正负都入 README 状态段。

## 8. 决策记录（2026-09-16 冻结）

按用户 2026-09-16 授权（"没有决策信息就多参考竞对和同行的实现方式来决策"），四项决策自主定稿如下；冻结后修改任何一项须在本文追加 Revision History 并重跑预注册核对：

| # | 决策 | 定稿 | 依据（行业惯例） |
|---|--- |--- |---|
| 1 | 任务来源 | 15 任务 × 3 仓库，候选池优先序：pallets/click → pallets/flask → psf/requests，备选 hynek/structlog、jsonschema；执行时按 §2 标准逐条核对，不合格顺延 | SWE-bench 范式（真实 issue + 测试红→绿机器判定）；小样本配对设计的常见规模（12–20）取中值 |
| 2 | harness 与模型档 | Claude Code headless（`claude -p --output-format json`）为默认后端；后端做成可替换接口（`benchmark/backends.py`），预留 Codex CLI；模型档执行时按可用 key 定，JSONL 记录模型标识 | harness = 用户实际使用的 Agent，结论才可迁移；headless JSON 输出可编程、可复现记录 |
| 3 | token 预算 | 低档起步：每次运行上限 60k，总运行 ≈5.4M（15 任务 × 2 臂 × 3 种子）+ 每仓库一次性构建 0.5–2M；不足时显式升级中档并记录理由 | 小样本实验从低档防单任务爆量；升级留痕防事后调参 |
| 4 | Treatment-B（MCP 臂） | v0 不含；仅当 Treatment-A 显示正效应后作为追加实验（B 回答"按需检索是否优于一次性注入"，前提是注入本身有效） | 实验效率顺序：A 无效则 B 无意义；三臂预算翻倍不合理 |

## Revision History

- 2026-09-16 v1.0 frozen：§8 四项决策定稿（任务池/harness/低档预算/两臂）；harness 同日实现（benchmark/，dry-run 可跑）。
- 2026-09-02 draft：初始设计。
