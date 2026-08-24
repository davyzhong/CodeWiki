# ATLAS 与 Enterprise Intelligence 的方法沉淀

本文只提炼能够公开复用的知识工程方法。关联项目均为私有工作区；其业务事实、原始素材、源码事实、人员信息、指标和内部路径不进入本仓库。

## 来自 ATLAS 的方法

ATLAS 的主要贡献是“规划知识也必须被治理”。它带来的原则包括：

1. **状态必须显式。** CURRENT、HISTORICAL、SUPERSEDED、REJECTED、DESIGN、HYPOTHESIS 等状态不能只藏在文件名或上下文中。
2. **事实和规划判断分离。** 规划材料可以支撑设计，但不能冒充企业事实基线；视觉材料和综合导航也不能自动升级为事实。
3. **来源映射和演进记录是一等产物。** 原始文件、转换结果、当前权威版本与被替代版本需要能互相追踪。
4. **稳定 ID 不跟着路径变化。** 目录是阅读界面，ID 是机器身份；重组目录不应改变对象身份。
5. **更新不覆盖历史。** 新口径成为当前版本时，旧版本仍保留可解释的状态和演进关系。
6. **跨库要有权威边界。** 同一个术语或事实出现在多个知识库时，要预先规定谁负责事实、谁负责规划，以及冲突如何裁决。

这些经验直接影响了 CodeWiki 的 Validity、Governance、Conflict、Provenance、稳定 Knowledge ID，以及 stale/retired 生命周期设计。

## 来自 Enterprise Intelligence 的方法

Enterprise Intelligence 的主要贡献是“知识生成必须是一条可验证的数据管线”。它带来的原则包括：

1. **知识层级不可倒置。** Source Evidence → Extracted Facts / Code Objects → Rendered Pages / Indexes；派生页不能反过来成为更高权威来源。
2. **重要结论必须有精确锚点。** Source Code Wiki 的声明要回到仓库、版本、文件、符号或行范围，而不是只给模糊文件名。
3. **机器产物应确定性可重建。** ID、排序、JSONL、分块、哈希和路径规范要让相同输入产生相同输出。
4. **检索默认 canonical-first。** 当前事实、源码解释、来源证据、历史和规划参考应按不同意图分层检索。
5. **覆盖率要诚实。** 结构化基线不能冒充深度业务理解；无证据的领域应明确为空或待补，不用模型补齐。
6. **发布需要门禁。** Schema、跨引用、链接、重复、敏感信息、凭据、绝对路径和大文件检查应成为发布前的一部分。
7. **内容面向人，合同面向机器。** 人读知识页可以用自然语言和本地语言；技术资产、稳定字段和 API 合同保持机器友好。

这些经验直接影响了 CodeWiki 的 Claim/Evidence 合同、Evidence Pack、Structural Validator、manifest generations、可恢复发布事务、Agent 默认 fail-closed 和验证报告。

## 合并后形成的 CodeWiki 原则

| 问题 | 继承的方法 | CodeWiki 中的体现 |
|---|---|---|
| 这条知识是什么性质？ | ATLAS 状态与证据分级 | verified / stale / conflicted / invalid / insufficient_evidence / retired |
| 这条知识从哪里来？ | 两库 provenance 与来源映射 | Claim → Evidence → repository snapshot / path / symbol / range |
| 人和 Agent 是否共用同一事实？ | 双层内容观 | Canonical IR 单一事实源，编译 Wiki、Cards、Context |
| 仓库变化后怎么办？ | 演进记录 + 可重建管线 | tracked baseline、affected targets、incremental update、generation check |
| 模型能否决定事实或删除？ | 权威边界 + 证据优先 | 证据不足不猜；retirement 只由确定性检查授权 |
| 如何避免“看起来完整”？ | EI 覆盖率诚实原则 | required/optional targets、partial 状态、gap 与 coverage 报告 |
| 如何安全发布？ | EI 发布门禁 | secret/path sanitization、schema/link/test checks、transactional publish |

## 没有继承的内容

- ATLAS 或 Enterprise Intelligence 的业务域、组织结论、系统清单、指标、源代码和企业事实。
- 两个项目的目录结构本身；CodeWiki 只吸收其中可泛化的方法。
- ATLAS 的具体规划权威或 EI 的企业事实权威。CodeWiki 是通用工具，不是二者的合并知识库。
