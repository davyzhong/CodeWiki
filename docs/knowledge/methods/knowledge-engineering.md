---
status: maintained
last-reviewed: 2026-09-12
sources:
  - 原 docs/project-materials/01-local-practice/cross-project-lessons.md（2026-09-12 迁入本知识库并升级格式；来源项目 ATLAS / Enterprise Intelligence 均为私有工作区，仅方法可公开）
  - 本仓库文档库三层治理（decision-log D-023）即本篇方法的自应用
---

# 知识工程方法沉淀（Knowledge Engineering）

来自两个真实知识库项目（ATLAS 规划资料治理、Enterprise Intelligence 事实知识库）的、经过公开安全提炼的治理原则。它们直接塑造了 CodeWiki 的 Validity/Provenance/稳定 ID/stale-retired 生命周期，也是本仓库文档库治理的依据。

## 来自 ATLAS 的六原则（规划知识也必须被治理）

1. **状态必须显式。** CURRENT/HISTORICAL/SUPERSEDED/REJECTED/DESIGN/HYPOTHESIS 不能只藏在文件名或上下文中。
2. **事实与规划判断分离。** 规划材料可以支撑设计，但不能冒充事实基线；综合导航类材料也不能自动升级为事实。
3. **来源映射与演进记录是一等产物。** 原始文件、转换结果、当前权威版本与被替代版本要能互相追踪。
4. **稳定 ID 不跟着路径变化。** 目录是阅读界面，ID 是机器身份；重组目录不改变对象身份。
5. **更新不覆盖历史。** 新口径成为当前时，旧版本保留可解释的状态与演进关系。
6. **跨库要有权威边界。** 同一术语出现在多个库时，预先规定谁负责事实、谁负责规划、冲突如何裁决。

## 来自 Enterprise Intelligence 的七原则（知识生成必须是可验证的数据管线）

1. **知识层级不可倒置。** Source Evidence → Facts/Code Objects → Rendered Pages/Indexes；派生页不能反成更高权威来源。
2. **重要结论必须有精确锚点。** 回到仓库/版本/文件/符号/行范围，而非模糊文件名。
3. **机器产物确定性可重建。** ID、排序、分块、哈希、路径规范保证相同输入相同输出。
4. **检索默认 canonical-first。** 按意图分层检索（当前事实/源码解释/来源证据/历史参考）。
5. **覆盖率要诚实。** 无证据的领域明确为空或待补，不用模型补齐"看起来完整"。
6. **发布需要门禁。** schema/交叉引用/敏感信息/绝对路径/大文件检查是发布的一部分。
7. **内容面向人，合同面向机器。** 知识页可用自然语言；稳定字段与 API 合同保持机器友好。

## 合并后的映射表（问题 → 方法 → 在本项目的体现）

| 问题 | 继承的方法 | CodeWiki 中的体现 |
|---|---|---|
| 这条知识是什么性质？ | 状态与证据分级 | verified/stale + 五种目标终态 |
| 从哪里来？ | provenance 与来源映射 | Claim → Evidence → snapshot/path/range；文档 decision-log |
| 人和 Agent 共用同一事实？ | 双层内容观 | Canonical IR 单源编译三视图 |
| 仓库变了怎么办？ | 演进记录 + 可重建管线 | tracked baseline、invalidation、generation |
| 模型能否决定事实/删除？ | 权威边界 + 证据优先 | 证据不足不猜；retirement 只由确定性证明授权 |
| 避免"看起来完整"？ | 覆盖率诚实 | required/optional、partial 状态、显式 insufficient_evidence |
| 如何安全发布？ | 发布门禁 | 脱敏/一致性检查/事务发布/verify.sh |

## 没有继承的内容

两个来源项目的业务域、组织结论、系统清单、指标、源代码与企业事实；它们的目录结构本身。CodeWiki 只吸收可泛化方法，不是二者的合并知识库。

## Revision History

- 2026-08-24 首次成文（cross-project-lessons.md，项目素材库内）。
- 2026-09-12 迁入知识库 methods 分区，升级 front-matter 与来源指针，正文保持原义。
