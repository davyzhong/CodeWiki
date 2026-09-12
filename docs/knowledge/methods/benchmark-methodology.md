---
status: maintained
last-reviewed: 2026-09-12
sources:
  - superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md（执行级细节以该草案为准，冻结后升级为计划）
  - superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md §19–§20（Agent A/B 基准与产品 gate）
---

# 产品基准验证方法（Benchmark Methodology）

如何验证"预编译知识真的让 Agent 更好"这一产品假设。本文提炼方法；执行参数（任务集、模型、预算）以 M8 设计草案为准且必须**先冻结后执行**。

## 为什么夹具测试不够

离线套件证明"系统按合同运行"，不证明"知识有用"。产品假设（H1 任务成功率 / H2 探索成本）只能在真实仓库 + 真实任务的对照实验中测量。**技术 DoD 达成但产品 gate 失败 = 完成的实验，不是扩范围的理由。**

## 臂位设计

| 臂 | 注入物 | 回答的问题 |
|---|---|---|
| Control | 无（Agent 只见仓库） | 基线 |
| Treatment-A | 启动时注入 `knowledge context "<task>"`（固定预算） | 一次性知识注入是否有益 |
| Treatment-B（可选） | 挂载七个只读 MCP 工具 | 按需检索是否优于一次性注入 |

最小可执行集 = Control vs A；同一 harness、同一系统提示、同一模型档，仅注入物不同（逐字节控制）。

## 任务集规则

真实公开 Git 仓库（Python ≥10k LOC、测试本地可跑、无网络/密钥依赖）；任务是真实 issue/小 feature，验收 = 指定测试红转绿（**机器可判定**）；12–20 个任务、≥3 仓库、难度分层；知识构建失败的仓库不入集（记为产品缺陷上报）。

## 预注册判定（防事后挑选）

- H1：配对成功率差 ≥ +10pp（15 任务即 ≥2 个翻转）或 McNemar/精确二项 p<0.10；
- H2：成功率不降（±1 任务内）且 token 中位数降幅 ≥ 20%（Wilcoxon p<0.10）；
- 判据在收集数据**之前**冻结；任何协议偏离记日志，重跑只按预声明规则；
- 结果为负也如实报告并附质性归因（知识条目在最终 diff/记录中的命中情况）。

## 效度威胁与对策

| 威胁 | 对策 |
|---|---|
| 任务污染（Treatment 偷读知识目录） | 注入物路径唯一，prompt 明令禁止，harness 记录全部文件访问 |
| 知识过期 | 知识严格按任务 base commit 构建，构建后工作区置 clean |
| 小样本假阳性 | 不做总体率断言，只做配对非参检验 + 逐任务呈现 |
| harness 偏差 | 两臂除注入物外逐字节相同；种子只影响采样侧 |
| 泄漏选择效应 | 每任务多种子（s∈{1,2,3}）重复，同任务内配对比较 |

## 度量与记录

逐次运行 JSONL：`task_id, arm, seed, success, total_tokens, tool_calls, wall_seconds, final_diff_hash, notes`；另记探索成本（read/search/grep 次数）、时间到首次有效编辑、知识消费量、知识导致的错误（与普通 Agent 错误分开）。原始数据脱敏后入库，结论正负都回填 README 状态段。

## Revision History

- 2026-09-12 从 M8 设计草案与规格 §19–20 提炼建卷。
