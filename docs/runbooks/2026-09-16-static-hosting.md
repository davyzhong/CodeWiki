---
status: active
created: 2026-09-16
applies-to: knowledge compile ≥ 3bdc657（展示层 v3）
---

# 静态托管 Runbook（exports/site 发布手册）

> 用途：把 `knowledge compile` 产出的多页静态站点发布给团队阅读（GitHub Pages / 内网静态服务）。
> 边界：**只发布 `exports/site/` 目录**。它是面向人类的公开视图；`.knowledge/` 其余内容（objects、runs、cache、manifest、human overlays）是内部状态，不随站点发布。

## 1. 产物确认

```bash
knowledge compile
ls .knowledge/exports/site/
# index.html（目录表 + Ask + 覆盖率）
# history.html（世代时间线 + 两代 diff）
# modules/ flows/ rules/ architecture/ tech-stack/ + 聚合页 + sources.html
```

全部页面为相对路径互链、数据编译时内嵌（无运行时 fetch 依赖、无外部 CDN、无字体请求），拷走整个目录即可离线打开或托管。暗色模式跟随访问者系统偏好（`prefers-color-scheme`），可手动切换并记忆。

## 2. 启用 evidence permalink（推荐）

```bash
knowledge init --language zh --web-url https://github.com/org/repo
knowledge compile
```

此后模块页/typed 页/源索引页的证据引用、Ask 命中卡片里的证据链接都指向 `{web_url}/blob/{commit}/{path}#L{s}-L{e}` 永久链接。`web_url` 随仓库版本控制（`.knowledge/config.yaml`），团队所有人链接一致。

## 3. 发布到 GitHub Pages（示例）

```bash
knowledge compile
cp -R .knowledge/exports/site /tmp/site-publish
# 把目录内容推到 gh-pages 分支或 pages 目录（按仓库习惯），
# 例如用 gh CLI：
# cd /tmp/site-publish && git init -b gh-pages && git add -A \
#   && git commit -m "publish knowledge site" && git push -f <remote> gh-pages
```

私有仓库的 Pages 访问权限跟随仓库设置；知识内容本质是"已验证的结构化代码理解"，发布前自行确认无敏感摘录（evidence excerpt 来自仓库本身，敏感度与源码同级）。

## 4. 内网静态服务（示例）

```bash
knowledge compile
python3 -m http.server 8771 --directory .knowledge/exports/site --bind 127.0.0.1
# 或任意静态文件服务器（nginx alias / object storage 静态托管）
```

`knowledge serve` 与上述托管**互为替代**：serve 额外提供 `/api/preview?task=` 只读端点（回环内跑真实检索，Ask 面板自动升级为"server-backed preview"）；纯静态托管时 Ask 自动回落到编译时内嵌的 Claim 级客户端检索。两种模式都只读，都不会执行被分析仓库的任何代码。

## 5. 更新节奏

- 每次 `knowledge build/update` 后跑 `knowledge compile`，重新拷贝目录发布；产物确定性保证同输入逐字节一致，可安全做发布 diff（无变化则不重发）。
- `history.html` 展示 runs 时间线与两代对象集 diff；它读取的是本地 runs 历史，随发布目录一起冻结为静态快照。
- 覆盖率条与目录表包含 `insufficient_evidence` 终态（灰红段/无链接行）——这是诚实覆盖语义，发布时**不要**手工删改这些行。

## 6. 常见问题

| 现象 | 说明 |
| --- | --- |
| Ask 显示"知识库未覆盖此问题" | evidence-only 语义：检索未命中已验证 Claim，不做生成式回答 |
| 证据链接 404 | `web_url` 与仓库托管平台不匹配，或 commit 未推送（permalink 用完整 commit 哈希） |
| 静态托管下 Ask 不走 server preview | 预期行为：`/api/preview` 仅 `knowledge serve` 提供；静态模式回落客户端检索 |
| 手机上侧栏折叠成顶栏 | 预期响应式行为（≤900px） |
