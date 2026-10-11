---
status: frozen-evidence
last-reviewed: 2026-10-11
scope: project-freeze-environment
sources:
  - git repository and local verification commands
---

# 封存审计环境基线

## 身份与状态

| 项 | 实测值 |
|---|---|
| 仓库 | `https://github.com/davyzhong/CodeWiki` |
| 分支 | `main`（唯一开发主干） |
| 审计起点 | `cea7c4b`（2026-09-25）；2026-10-11 从 `9527902` 续审 |
| 已推送修复提交 | `12c92cc`（站点运行时/布局 + 依赖安全） |
| 远端状态 | public、未 archived、default branch `main` |
| 主机 | macOS Darwin 25.6.0 arm64 |
| 系统 Python | 3.9.6（不作为项目运行时） |
| uv 项目 Python | 3.12.13（按项目 `.python-version` 重建） |
| uv | 0.10.10 |
| Node | 26.10.0 |
| 项目包 | `knowledge-compiler 0.1.0.dev0` |
| 上游运行依赖 | `codewiki 0.6.5` |
| pytest | 9.1.1 |
| MCP SDK | 1.30.0 |

## 规模快照

- 2026-09-25 起审时 tracked files：279；Markdown：80；`src` Python：76；测试 Python：65。续审产生的文档与截图在最终清单中另行计数。
- 产品 Python 源码约 18,075 行；测试约 14,894 行。
- Git objects 约 37 MiB；工作区 417 MiB，主要增量来自本地 `.venv` 与已忽略的 `node_modules`。
- tracked 大文件主要为 README 截图（3.2 MiB、2.3 MiB）及 Local Beta 设计图（1.1 MiB）；均为有引用的项目资产。

## 可复现命令与结果

```bash
git pull --ff-only
uv lock --check
uv sync --frozen --extra dev
uv pip check
VERIFY_FAST=1 bash scripts/verify.sh
python scripts/check_links.py
git diff --check
```

2026-10-11 续审完整双遍实测：两遍均为 `790 passed, 1 skipped`；`compileall`、diff check、`pip-audit` 全部 PASS。Live smoke 因 `codewiki` 未暴露在 shell PATH、`KNOWLEDGE_EXTRACTION_MODEL` 与 `KNOWLEDGE_LIVE_REPOSITORY` 未配置而 SKIP；这不是 PASS。790 相比旧基线新增 3 个浏览器审计发现的回归测试。

## 环境修复记录

原锁文件与 `pyproject.toml` 不一致，并把 `pytest` 固定到受 GHSA-6w46-j5rx-g56g 影响的 8.4.2。首轮审计将开发依赖改为 `pytest>=9.0.3,<10`，重锁为 9.1.1。2026-10-11 再次审计时发现 `multidict 6.7.1`、`pyjwt 2.13.0`、`urllib3 2.7.0` 的 18 条已知漏洞，已在兼容范围内分别升级为 6.9.1、2.15.1、2.8.0，并通过 frozen sync、`uv pip check`、全套测试和 `pip-audit`。CI 仍未强制使用锁文件，见工程审计的批准门禁。

## Revision History

- 2026-09-25：建立封存审计环境与验证基线。
- 2026-10-11：记录续审环境、790+1 基线、静态站点修复和传递依赖安全升级。
