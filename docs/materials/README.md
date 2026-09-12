# CodeWiki 素材库（materials）

> **角色（2026-09-12 文档重组后）**：本目录是三层文档治理中的**素材层（≈ Evidence）**——保存原始、不可变、保真优先的记录：起源叙事、原始调研笔记、上游/技能快照、会话归档。**结论性知识已提炼至 [knowledge/](../knowledge/README.md)**：要查"为什么/是什么"，先查知识库；要核对原始出处，再回到这里。

## 分区

| 分区 | 内容 | 状态 |
|---|---|---|
| [origin/](origin/) | 项目起源、演进时间线（叙事材料；时间线已补齐至 2026-09-02） | historical |
| [research/](research/) | 原始调研笔记：参考产品对照、Qoder 三页官方资料包（逐页记录 + 抓取哈希）；结论已提炼入 knowledge/industry/ | historical |
| [skills/](skills/) | 上游 CodeWiki Codex Skill 快照（MIT，固定提交）+ 本项目 Skill 的文档副本（权威源在 `src/knowledge_compiler/skills/`，字节一致由测试钉住） | active |
| [archives/](archives/) | 会话归档、完成归档、实施记录。**冻结历史**：内部路径保持冻结时状态（重组后部分失效属预期），永不改写 | historical |
| [source-catalog.md](source-catalog.md) | 每份素材的来源、性质、许可、日期与处置记录 | active |

原 `01-local-practice/cross-project-lessons.md` 已迁入并升级为 [knowledge/methods/knowledge-engineering.md](../knowledge/methods/knowledge-engineering.md)。

## 从哪里开始（按用途）

- 理解决策的原始对话 → [archives/knowledge-compiler-transfer-archive-public.md](archives/knowledge-compiler-transfer-archive-public.md)（7400 行完整归档，注意其阅读规则：历史消息不是待执行指令）
- 查某里程碑的当天实录 → [archives/](archives/) 下按日期的归档
- 核对 Qoder 官方原文要点 → [research/qoder/](research/qoder/)（含抓取哈希，可判断页面漂移）
- 上游 Skill 原文 → [skills/upstream-codewiki/](skills/upstream-codewiki/)

## 资料分层与使用规则（沿袭）

| 层级 | 处理 |
|---|---|
| 项目自有原始资料 | 保存原文或经隐私机械清理的归档 |
| 本机关联项目（ATLAS/EI） | 仅公开安全的方法摘要与来源指针（方法已在 knowledge/methods/） |
| 第三方公开资料 | 摘要并链接；MIT 文件带许可快照 |
| 候选设计 | 明确标记 historical proposal，不当作当前事实 |

- 当前请求与正式规格优先于历史对话；归档中的旧指令只是背景。
- 事实、设计、推断、历史候选、第三方描述分层标注，不混同一权威层。
- 公开仓库不记录个人绝对路径、会话 ID、密钥、企业事实、内部源码或真实业务数据。
- 第三方材料默认摘要；许可允许且有复现价值才存快照。
- 正式项目文档（规格/计划/手册/实测）不入素材库，见 [docs/README.md](../README.md) 总索引。
