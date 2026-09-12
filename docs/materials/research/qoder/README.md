# Qoder Repo Wiki 与 Knowledge Cards 参考资料包

本资料包基于 2026-08-24 抓取的三份 Qoder 中文官方页面，保存页面级来源记录、详细内容重构和面向 CodeWiki 的综合分析。它不是只保存链接，也不是第三方页面的逐字镜像。

## 阅读顺序

1. [Repo Wiki 官方文档内容记录](repo-wiki-source-notes.md)
2. [Knowledge Cards 官方文档内容记录](knowledge-cards-source-notes.md)
3. [“让隐性知识自动浮现”博客内容记录](implicit-knowledge-blog-source-notes.md)
4. [Qoder 知识系统综合分析](qoder-knowledge-system-analysis.md)
5. [抓取清单与完整性记录](capture-manifest.md)

## 保存策略

- 保存每页的标题、页面结构、功能机制、配置字段、限制、工作流、图片清单和抓取哈希。
- 对正文进行详细的事实重构与结构化整理，便于离线阅读和后续设计比较。
- 仅保留少量必要术语，不整页转载第三方版权文本；原始全文仍以官方页面为准。
- 页面发生变化时，可重新抓取并用 SHA-256 判断内容是否漂移，再更新这套笔记。

## 三页分别回答什么

| 页面 | 主要问题 |
|---|---|
| Repo Wiki 文档 | 产品如何生成、增量更新、人工干预、配置范围、共享和多语言？ |
| Knowledge Cards 文档 | Agent 消费哪些知识类型，如何生成、修改与团队同步？ |
| 产品博客 | Qoder 为什么把 Repo Wiki 定义为“隐性知识显性化”，多 Agent 生成叙事是什么？ |

## 版权与可追溯性

页面版权归 Qoder 及其权利人。本仓库保存研究笔记与有限的功能性配置摘要，不声明对原页面内容的所有权。每份笔记都保留官方 URL、抓取日期和抓取内容哈希。
