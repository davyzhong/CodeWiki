# CodeWiki 项目原始素材库

这里保存 CodeWiki（早期名称 Knowledge Compiler / CoDoMoWiki）的起源、调研、跨项目经验和技能资料。它既是项目档案，也是后续设计决策的证据入口。

## 从哪里开始

1. [项目起源](00-origin/project-origin.md)：为什么会有这个项目，以及 ATLAS、Enterprise Intelligence 与本项目的关系。
2. [演进时间线](00-origin/timeline.md)：从知识库实践、产品调研到 Phase 0/Phase 1 的决策顺序。
3. [参考产品与模式](02-external-research/reference-products.md)：Qoder Repo Wiki、Knowledge Cards、Google Code Wiki、GitHub Copilot Memory 与 PorunC/CodeWiki。
   - [Qoder 三页官方资料的详细资料包](02-external-research/qoder/README.md)
4. [跨项目方法沉淀](01-local-practice/cross-project-lessons.md)：从 ATLAS 和 Enterprise Intelligence 提炼、且适合公开复用的知识工程方法。
5. [技能资料索引](03-skills/README.md)：上游 CodeWiki Skill 快照，以及 Knowledge Compiler 四个拟议 Skill 的历史状态。
6. [来源目录](source-catalog.md)：每份材料的来源、性质、许可、日期和是否入库。

## 正式项目文档

以下文档已经是仓库中的权威版本，不在素材库重复保存：

- [V0.1 设计规格](../superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md)
- [Phase 0 CodeWiki Adapter Spike 计划](../superpowers/plans/2026-08-24-codewiki-adapter-spike.md)
- [Phase 0 公共接口报告](../spikes/codewiki-public-surface.md)
- [Phase 1 Fake Provider 垂直切片计划](../superpowers/plans/2026-08-24-fake-provider-module-vertical-slice.md)

下载目录中的两份原始设计文件与上述正式规格、Phase 0 计划 SHA-256 完全一致，因此采用“单一权威副本 + 来源哈希”的方式去重。

## 资料分层

| 层级 | 内容 | 在本仓库的处理 |
|---|---|---|
| 项目自有原始资料 | 对话归档、规格、计划、实验报告 | 保存原文或经过隐私机械清理的归档 |
| 本机关联项目 | ATLAS、Enterprise Intelligence 的知识库实践 | 仅保留公开安全的方法摘要与来源指针，不复制内部事实 |
| 第三方公开资料 | 产品文档、开源仓库、Skill | 摘要并链接；MIT 文件可带许可快照 |
| 候选设计 | 早期构想、尚未实现的 Skill 或架构 | 明确标记为 historical proposal，不当作当前事实 |

## 使用规则

- 当前请求和正式规格的优先级高于历史对话；归档中的旧问题和旧指令只是背景。
- 对事实、设计、推断、历史候选和第三方描述分别标注，不把它们混成同一权威层。
- 公开仓库中不记录个人绝对路径、会话 ID、密钥、企业事实、内部源码内容或真实业务数据。
- 第三方材料默认只做摘要；只有许可明确允许且确有复现价值时才保存快照。
