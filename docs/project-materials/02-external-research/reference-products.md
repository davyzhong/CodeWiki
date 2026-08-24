# 参考产品与实现模式

核验日期：2026-08-24。第三方能力会变化；本页先列最终影响 V0.1 决策的核心基线，再保留早期研究过但未成为直接依赖的次级线索。

## 模式对照

| 产品或模式 | 核心价值 | 对本项目的启发 | 没有直接照搬的部分 |
|---|---|---|---|
| Google Code Wiki | 自动生成持续更新的结构化 Wiki、图表、问答与源码链接 | 人类知识视图需要可导航、可视化且回链源码 | 托管式产品形态和特定模型绑定 |
| Qoder Repo Wiki | 仓库级结构化文档、增量更新、Git 同步、人类编辑保护 | Wiki 应是可维护且随代码演进的产品产物 | IDE 专属工作流和封闭实现 |
| Qoder Knowledge Cards | 与 Repo Wiki 同步生成的高密度 Agent 知识单元 | 人类 Wiki 与 Agent Cards 应来自同一知识源 | 直接采用其存储格式或封闭生成机制 |
| GitHub Copilot Memory | 带代码引用的仓库级记忆，使用前重新验证 | Agent 默认读取必须检查当前代码状态 | 只做零散 Memory 而不建立完整 IR |
| PorunC/CodeWiki | 本地 AST、代码图、GraphRAG、Wiki、MCP、Codex Skill | 作为可替换 Evidence Provider 和公开接口基线 | Fork 平台、导入内部模块或读取内部数据库 |
| AGENTS.md / CLAUDE.md | 低成本、人工可控的静态指令 | Skill/指令适合表达“如何工作” | 用静态文件承担自动事实萃取和增量维护 |

## Qoder：Repo Wiki + Knowledge Cards

Qoder 把两种使用者分开：Repo Wiki 面向人类理解，Knowledge Cards 面向 Agent。官方文档显示 Cards 与 Repo Wiki 同步生成，当前包括 Architecture、Spec 和 Tech Stack 等高密度知识类型，并能随提交更新；Wiki 计划位于 `.qoder/repowiki/wiki_plan.yaml`，生成内容可通过 Git 共享。

这直接促成了本项目的三视图模型：

```text
Canonical Knowledge IR
  ├─ Repo Wiki       人类浏览与理解
  ├─ Knowledge Cards Agent 稳定读取
  └─ Task Context    面向当前任务的预算化编译
```

本项目进一步要求 Claim/Evidence 成为 IR 的组成部分，避免 Wiki 和 Card 各自生成相互矛盾的事实。

## PorunC/CodeWiki：MVP 底座与边界

上游项目的实现管线可概括为：

```text
Repository -> tree-sitter AST -> Code Graph -> Communities
           -> FTS / Vector -> GraphRAG -> Wiki / Q&A / MCP / Skill
```

其设计强调确定性代码事实、图关系、检索和带源码引用的 Wiki。上游 Codex Skill 则采用“计划页面 → 获取紧凑证据 → 只依据证据写页 → 保存 → citation validation → HTML 导出”的流程，并明确禁止把庞大检索上下文直接灌入会话或编造路径/API/架构事实。

本项目最终选择 Adapter，而非 Fork：

- 只使用公开 CLI/MCP/HTTP；
- 不把内部 SQLite/PostgreSQL Schema 当成合同；
- 不导入上游 Python 内部模块；
- 将 AST/图/搜索结果转换成版本化 Evidence Provider DTO；
- 在独立 `.knowledge/` 中维护 Claim/Evidence 驱动 IR。

Phase 0 已对 `codewiki 0.6.5` 公共表面完成实测，详见[实验报告](../../spikes/codewiki-public-surface.md)。

## 次级研究线索

以下方案出现在早期研究归档中，对概念形成有帮助，但没有成为 V0.1 的直接依赖。原始研究没有完整保留每项的精确页面版本，因此这里只记录其影响；未来若要据此实现功能，必须重新查验官方资料。

| 线索 | 当时提炼的启发 | 未进入核心基线的原因 |
|---|---|---|
| Sourcegraph | 预编译 Knowledge 不能替代实时的 Search → Read → Reflect；两者应组合 | V0.1 聚焦持久化知识层，不建设通用代码搜索平台 |
| Cursor | Index + Rules + Memory + Agent Retrieval 代表较轻的知识模式 | 封闭产品实现，且重点不是可验证 Canonical IR |
| DeepWiki | Outline/Page Agent 可沿 imports、callers 和源码搜索逐页取证 | 更偏 Wiki 生成流程，缺少本项目所需的独立治理 IR |
| Microsoft deep-wiki Skill | 读真实代码、追踪连接、为结论给文件/行号，禁止按命名猜测 | 作为 evidence-grounded prompting 参考，不作为运行时依赖 |
| Qwen CodeScope | Structure Graph + Evolution Graph + Embedding 把代码结构与 Git 演进结合 | 作为演进图概念参考，V0.1 先以可实测的 CodeWiki Adapter 开始 |

`AGENTS.md` / `CLAUDE.md` 不是单一第三方产品来源，而是静态仓库指令文件这一通用模式；本项目保留它们“表达如何工作”的优点，但不让其承担自动事实萃取。

## 官方来源

- [Google Code Wiki 官方介绍](https://developers.googleblog.com/introducing-code-wiki-accelerating-your-code-understanding/)
- [Qoder Repo Wiki](https://docs.qoder.com/user-guide/repo-wiki)
- [Qoder Knowledge Cards](https://docs.qoder.com/user-guide/knowledge-engine/knowledge-cards)
- [GitHub Copilot Memory](https://docs.github.com/en/copilot/concepts/agents/copilot-memory)
- [PorunC/CodeWiki 仓库](https://github.com/PorunC/CodeWiki)
- [PorunC/CodeWiki 设计（固定提交）](https://github.com/PorunC/CodeWiki/blob/7be8f702504cbd69aec6491a2e4e81f5311e0ba6/docs/design.md)
- [PorunC/CodeWiki 使用文档（固定提交）](https://github.com/PorunC/CodeWiki/blob/7be8f702504cbd69aec6491a2e4e81f5311e0ba6/docs/usage.md)
- [PorunC/CodeWiki Codex Skill（固定提交）](https://github.com/PorunC/CodeWiki/blob/7be8f702504cbd69aec6491a2e4e81f5311e0ba6/backend/skills/codewiki/SKILL.md)
