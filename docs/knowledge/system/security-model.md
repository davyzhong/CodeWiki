---
status: maintained
last-reviewed: 2026-09-12
sources:
  - superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md §14
  - superpowers/plans/historical/2026-08-26-v0-1-mainline-recovery.md Gate 8
  - src/knowledge_compiler/（validation/module.py、providers/codewiki.py、mcp_server.py、retrieval/）与对应测试矩阵
---

# 安全模型（Security Model）

信任边界：**被分析的仓库文本是不可信输入**；上游提供方输出是不可信输入；一切 Agent/MCP 读取默认 fail closed。

## 执行边界（绝对禁令）

- 永不执行被分析仓库的代码、测试、构建、安装脚本或钩子；永不 `pip install` 它。
- MCP 服务器无任何构建/子进程/写路径（源码级检查 + 整树字节不变测试钉死）。

## 路径与文件系统防御

- 证据路径：相对 POSIX、拒绝对路径/遍历（`..`）/盘符/NUL/反斜杠；
- 读取用描述符相对链（`openat` + `O_NOFOLLOW`）防 symlink 逃逸与 check/open 竞争；拒绝非常规文件；
- 发布事务拒绝 symlink 的受管目录/祖先，暂存文件 `O_EXCL` 创建，journal 校验目的地不得逃逸根；
- 合格文件清单永久排除 `.knowledge/`、`.codewiki/`、`.git/`、ignored、依赖目录、二进制、凭据文件、超限文件——生成物与密钥不进入证据，也不污染快照哈希。

## 凭据处理

- 模型端点/密钥只来自环境变量或用户级配置，永不入库（config schema 显式拒绝 secret 字段）、不进提示词/报告/日志/`.knowledge/`；
- Evidence Pack 进入模型前做凭据模式检测与脱敏：原始字节哈希本地校验，模型只见脱敏摘录（双哈希分离）；
- 观测输出（spike/报告）统一 `<REPO>`/`<REDACTED>` 净化，入库前机械扫描绝对路径与密钥模式。

## 注入防御（文本永远是数据）

- Markdown/Card/Wiki/HTML/Mermaid 编译对全部合同字段按上下文转义（HTML 实体、管道、反引号围栏自适应、标题/列表/围栏/缩进代码块开头中和）；对抗性测试矩阵断言 `<script>`/`javascript:`/伪造标题等不可注入结构；
- 抽取与验证把仓库文本当数据；MCP 响应中的仓库/人工文本同样按数据转义。

## 有界性

证据包三重预算（item/字符/token）；CLI 参数边界校验；上游调用数组传参 + 120s 超时 + 输出尺寸上限；检索按 token 预算编译，源码正文默认不内嵌（指针按需）。

## fail-closed 读取

见 [behavior-reference](behavior-reference.md) 检索门禁一节：快照/代际/索引戳不一致即拒绝，而非降级服务旧知识；stale/conflicted/invalid/insufficient 永不进入默认上下文。

## 验证方式

以上每条都有对应测试族：路径/遍历/symlink 竞争矩阵、凭据不泄漏扫描、注入载荷矩阵、MCP 只读整树字节比对、预算超限拒绝、门禁不匹配拒绝。安全矩阵离线运行，不依赖网络或付费模型。

## Revision History

- 2026-09-12 从规格 §14、恢复计划 Gate 8 与实现/测试建卷。
