# 系统知识（system）

当前实现的 as-built 事实：组件如何组织、每个命令/工具实际的行为语义、安全边界如何落地。规格（specs/）说"应该是什么"，本区说"现在是什么"（含三处已记录偏差的指针）。

| 文档 | 内容 | 何时读 |
|---|---|---|
| [architecture.md](architecture.md) | 组件地图、数据流、与规格的三处偏差 | 改代码前建立全景 |
| [behavior-reference.md](behavior-reference.md) | CLI 命令与退出码、MCP 七工具、检索门禁、验证闭环 | 使用/排查/写集成时 |
| [security-model.md](security-model.md) | 信任边界与防御措施清单（路径/凭据/注入/只读） | 安全评审 / 新增外部输入时 |
