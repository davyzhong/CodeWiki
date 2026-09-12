# 静态知识库（knowledge）

本区是项目的**权威知识层**：从素材库（[materials/](../materials/)）与会话归档中提炼、带来源指针、静态稳定的知识。设计报告与实施计划引用本区，而不是翻原始归档——这就是"不依赖动态可变上下文"的自有知识库。

四条使用规则：

1. **单一权威副本**：一个事实在本区只定义一次；其他文档链接过来，不复制。
2. **知识不带日期**：版本由 `status + last-reviewed` 管理；修正追加 Revision History，不静默改写。
3. **结论可追溯**：每篇 front-matter 声明来源（素材文件 / 规格 / 提交号）。
4. **与代码不一致时**：先改代码或先改知识，二选一立即对齐——知识库不允许"已知过期"。

## 概念地图（遇到什么问题查哪篇）

| 问题类型 | 去处 |
|---|---|
| 产品是什么 / 成功标准 / 边界 | [product/product-definition](product/product-definition.md) |
| 为什么当初这样决定 / 有没有先例 | [product/decision-log](product/decision-log.md)（D-001…D-023） |
| 某术语（Claim？generation？overlay？）什么意思 | [product/domain-model](product/domain-model.md) |
| 行业有哪些竞品 / 怎么分层 | [industry/landscape](industry/landscape.md) |
| 双视图、fail-closed 这些模式是谁先做的 | [industry/patterns](industry/patterns.md) |
| Qoder 具体怎么工作 / 我们差在哪 | [industry/qoder-deep-dive](industry/qoder-deep-dive.md) |
| 上游 CodeWiki 怎么集成 / 能力矩阵 / 升级纪律 | [industry/upstream-codewiki](industry/upstream-codewiki.md) |
| 怎么治理知识库/文档库 | [methods/knowledge-engineering](methods/knowledge-engineering.md) |
| 怎么设计可验证的系统 | [methods/evidence-first-design](methods/evidence-first-design.md) |
| 怎么验证产品假设 | [methods/benchmark-methodology](methods/benchmark-methodology.md) |
| 系统现在长什么样 / 三处偏差 | [system/architecture](system/architecture.md) |
| 某命令/工具/退出码的行为 | [system/behavior-reference](system/behavior-reference.md) |
| 安全边界怎么落地 | [system/security-model](system/security-model.md) |

各分区另有索引：[product/](product/README.md) · [industry/](industry/README.md) · [methods/](methods/README.md) · [system/](system/README.md)
