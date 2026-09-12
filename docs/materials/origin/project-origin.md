# 项目起源

## 一句话定义

CodeWiki 是一个 local-first 的仓库知识编译工具：从本地 Git 仓库和可验证代码证据中形成独立的 Canonical Knowledge IR，再编译出给人阅读的 Repo Wiki、给 Agent 使用的 Knowledge Cards，以及面向具体任务的紧凑上下文。

## 为什么会开始

这个项目不是从“再做一个 Wiki”开始的，而是从两个真实知识库项目中的共同问题开始的。

在 ATLAS 项目中，大量历史文档、规划输入、方法论、设计稿、演示材料和外部参考需要被整理成可追溯的规划知识库。实践证明，只有目录分类不够，还必须显式处理版本、状态、证据等级、来源映射、演进时间线和跨库权威边界。

在 Enterprise Intelligence 项目中，任务进一步变成事实知识库与 Source Code Wiki：原始素材、结构化事实、源码锚点、派生知识页和机器索引之间要形成稳定的数据合同；每条重要结论要能回到来源，生成物不能反过来成为更高层的事实依据。

这两次实践暴露出一个更普遍的缺口：知识库整理仍然高度依赖一次性的人工工程。仓库变化以后，知识会过期；Wiki 适合人读，却不一定适合 Coding Agent；大量上下文直接灌给 Agent 又昂贵且不可靠。因此萌生了做一个自己的知识库工具的想法：把“扫描、萃取、验证、版本化、增量更新、为人和 Agent 编译不同视图”变成可重复运行的产品能力。

## 三个项目的关系

```text
ATLAS
规划资料治理、版本状态、证据分级、演进记录
        \
         +--> 可重复的知识工程方法 --> CodeWiki
        /
Enterprise Intelligence
事实层级、源码锚点、确定性索引、验证与发布门禁
```

- ATLAS 是规划参考库，不是本项目的数据源或产品依赖。
- Enterprise Intelligence 是企业事实与源码知识实践，不是本项目的数据源或产品依赖。
- CodeWiki 吸收两者的方法经验，但不会将其中的企业事实、源码或业务数据带入公开仓库。

## 从调研到产品定义

早期研究集中在五种模式：自动 Repo Wiki、IDE 内知识层、Agent Memory、本地代码智能平台和静态 Agent 指令。关键发现是：

- Qoder 的 Repo Wiki + Knowledge Cards 说明“人类视图”和“Agent 视图”应来自同一份知识，但密度和使用方式不同。
- GitHub Copilot Memory 说明事实应带代码引用，并在使用前重新验证。
- Google Code Wiki 说明自动结构化文档、图表、问答和源码链接具有直接的人类阅读价值。
- PorunC/CodeWiki 已提供 AST、代码图、GraphRAG、Wiki、MCP 和 Codex Skill，是合适的 Evidence Provider 与 MVP 参照。

由此形成的核心取舍是：不整体 Fork PorunC/CodeWiki，不依赖它的内部数据库；只通过公开 CLI/MCP/HTTP 适配其证据能力，并在上层建立自己的 Claim/Evidence 驱动 Canonical Knowledge IR。

## 名称演进

- **Knowledge Compiler**：最初的产品概念名，强调从证据到多视图的“编译”。
- **CoDoMoWiki**：GitHub 项目申请初期曾使用的临时仓库名。
- **CodeWiki**：当前本地目录与 GitHub 仓库名。它与上游 `PorunC/CodeWiki` 同名，因此文档中提到第三方项目时统一写作“PorunC/CodeWiki”或“上游 CodeWiki”。

产品内部的核心概念仍保留 Knowledge Compiler，因为它比单纯 Wiki 更准确地描述目标。
