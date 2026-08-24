# Qoder 页面抓取清单

- 抓取日期：2026-08-24（Asia/Shanghai）
- 抓取方式：Firecrawl `scrape --only-main-content`
- 输出形态：临时 Markdown；原始抓取仅用于分析，没有将第三方全文提交到仓库。

| ID | 官方 URL | 抓取结果 | 行数 | 字节数 | 抓取 Markdown SHA-256 |
|---|---|---:|---:|---:|---|
| `qoder-repo-wiki-zh` | https://docs.qoder.com/zh/user-guide/repo-wiki | HTTP 200 | 267 | 11,627 | `f20a737cd3bec5d333cfe12037187b6427c1b75ffbf68cecb1e64fff0b35d560` |
| `qoder-knowledge-cards-zh` | https://docs.qoder.com/zh/user-guide/knowledge-engine/knowledge-cards | HTTP 200 | 143 | 8,835 | `16d0992a18a0262505141f828736044c1a96c59e898aabf472042ff3f9f467a2` |
| `qoder-implicit-knowledge-blog-zh` | https://qoder.com/zh/blog/repo-wiki-surfacing-implicit-knowledge | HTTP 200 | 45 | 3,796 | `a7353f22eeede7586b51cd396baa0c3f948da87a7bd84330f3f1aaa31f8e0ab8` |

## HTTP 元数据

- 两份文档页返回 `text/html; charset=utf-8` 和 `cache-control: no-cache`，未提供稳定的 `Last-Modified`。
- 博客页返回 `text/html`，抓取时的 `Last-Modified` 为 `2026-08-20T03:33:27Z`，ETag 为 `6a867587-e671`。
- 博客正文标注发布日期为 2025-09-11、预计阅读时间 3 分钟。

## 完整性说明

哈希针对 Firecrawl 清理后的 Markdown，而不是服务器原始 HTML。它可以用于判断相同抓取方式下的页面内容是否变化，但不是 Qoder 发布版本号，也不能证明页面永久不变。

抓取内容包含站点导航、页脚和图片链接。研究笔记只采纳页面主体，导航性噪声不作为产品事实。
