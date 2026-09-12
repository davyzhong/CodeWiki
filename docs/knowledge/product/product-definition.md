---
status: maintained
last-reviewed: 2026-09-12
sources:
  - superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md §1–3, §20–21
  - materials/origin/project-origin.md
  - superpowers/plans/active/2026-09-02-m8-ab-benchmark-design.md
---

# 产品定义（Product Definition）

## 一句话定义

CodeWiki（设计名 Knowledge Compiler）是一个 **local-first 的仓库知识编译器**：读取一个本地 Git 仓库，通过可替换的证据引擎（默认上游 CodeWiki 0.6.x 公开接口）获取有界、可验证的代码证据，萃取为 Claim/Evidence 驱动的 Canonical Knowledge IR，再确定性编译出三种视图——给人读的 Repo Wiki（Markdown + 单文件 HTML）、给 Agent 消费的 Knowledge Cards、按任务预算编译的 Task Context（CLI + 七个只读 MCP 工具）。

## 核心假设（产品要验证的东西）

> **预先萃取、源码证据支持的仓库知识，能否提高 Coding Agent 的任务成功率（H1），或在成功率相当时降低探索成本（H2）？**

- H1 主判据：配对成功率差 ≥ +10 个百分点，或 McNemar/精确二项 p<0.10；
- H2 主判据：成功率不降（±1 任务内）且 token 中位数降幅 ≥ 20%（Wilcoxon p<0.10）；
- 判定标准已预注册（防事后挑选），详见 [benchmark-methodology](../methods/benchmark-methodology.md) 与 M8 设计草案；
- 夹具测试不能替代本验证——技术全部完成后这是唯一待做的产品级实验。

## 三种视图，同一份 IR

```
Canonical Knowledge IR（唯一事实知识存储）
  ├─ Repo Wiki        人类浏览：导航、Mermaid、源码引用、stale 过期横幅
  ├─ Knowledge Cards  Agent 消费：verified-only 高密度单元（YAML + Markdown）
  └─ Task Context     任务现场：FTS 检索 + 一跳关系扩展 + token 预算编译
```

Wiki 与 Cards 必须从同一 IR 编译（不允许各自生成互相矛盾的事实），这是从 Qoder 双视图借鉴并强化的核心理念（见 [decision-log](decision-log.md) D-003）。

## 五类知识对象

`Architecture`（系统结构/边界）、`Module`（职责/接口/依赖）、`Flow`（触发/有序步骤/失败路径）、`Rule`（业务约束/严重度/适用范围）、`TechStack`（技术/版本/配置证据）。每个事实字段必须由 Claim 支撑，每条 Claim 必须绑定 Evidence（路径/符号/行范围/内容哈希）。

## 成功标准（两层）

1. **技术 DoD**（已全部达成，2026-09-02）：单仓库完整 build/update、双执行模式共享持久化编排器、五类型 Claim/Evidence 验证、全部视图与检索、七个只读 MCP 工具、崩溃恢复与确定性测试、离线 752 项测试双遍一致。
2. **产品 gate**（待 M8）：Evidence 结构有效率 100%、≥50 条抽样 Claim 源码支持率 ≥90%、stale/conflicted 绝不进入默认上下文、H1 或 H2 命中。**技术达标但产品 gate 失败 = 完成的实验，不是扩范围的理由**。

## V0.1 边界（明确的非目标）

远程 Git URL 克隆（V0.1.x）、多仓库工作区（V0.2）、团队 SaaS/权限/审批、人工编辑之外的双向合并、Issue/Incident/Decision 等扩展知识类型、非代码企业知识、Web 服务、向量数据库、自研 AST 解析器。

## 演进路径

V0.1（本地单仓库全闭环，当前）→ V0.1.x（Git URL/clone 缓存/私有凭证）→ V0.2（多仓库工作区与跨仓库 Flow）→ 更远（人工治理、Git/PR 决策、企业知识）。

## Revision History

- 2026-09-12 首次提炼入知识库（从规格 §1–3/§20–21、项目起源、M8 设计草案）。
