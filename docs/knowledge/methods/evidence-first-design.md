---
status: maintained
last-reviewed: 2026-09-12
sources:
  - superpowers/specs/2026-08-24-knowledge-compiler-v0-1-design.md 全文
  - M1–M5 计划与 ~31 轮独立审查的修复记录（materials/archives/2026-08-25-completion-archive.md §5）
  - superpowers/plans/historical/2026-08-26-v0-1-mainline-recovery.md（Gate 1–8）
  - src/ 与 tests/ 的 as-built 实现
---

# 证据优先的工程方法（Evidence-First Design）

本项目在 V0.1 全程（M1→恢复计划→符合性修复，约 150 个提交、31 轮审查）中沉淀的工程方法。每条都对应真实缺陷的修复，不是先验设计。

## 1 · 合同先行：确定性身份 + 不可变模型

- 一切跨边界数据是 Pydantic 合同：`extra="forbid"` + `frozen=True` + `revalidate_instances="always"`（嵌套被复制传入也重新验证——审查中发现的真实绕过路径）。
- **身份确定性派生**：snapshot_id / Evidence ID / 验证 digest 全部由内容 SHA-256 派生并在合同层强制比对，"内容变→身份变"不可伪造。
- 排序即合同：Claim/接口/依赖/关系/证据在验证时规范化排序，语义等价的乱序输入编译出逐字节相同输出（golden + 置换不变性测试钉死）。

## 2 · 验证分两层，各管一半真相

- **结构验证（确定性）**管"引用是否真实存在"：路径/行范围/原始字节哈希/派生 ID/Claim 引用闭包。
- **语义验证（独立请求）**管"证据是否真的支持陈述"：只喂 Claim + 脱敏摘录，判 supported/partial/unsupported/conflicted；与抽取分离的提示词、幂等域、上下文——同模型也必须两次独立调用。
- **摘要绑定**：验证结果绑定请求摘要（Claim 文本 + 证据 ID + 摘录哈希的 SHA-256），脱敏输出一变，旧验证即失效。

## 3 · 字节级源码完整性

- 描述符相对打开（`openat` 链 + `O_NOFOLLOW`）防路径穿越、symlink 逃逸与 check/open 竞争；非常规文件拒绝。
- 原始字节（保留 CRLF/尾换行，`splitlines(keepends=True)` 精确拼接）与脱敏摘录分别哈希、分别校验——本地验证原始字节，模型只见脱敏文本。

## 4 · 可恢复事务：manifest 最后替换

- 发布 = 预编译全部字节 → 暂存 fsync → journal（目的地+备份+先前存在性）→ 替换 canonical/Agent 面 → **manifest 最后替换（唯一提交标记）** → 清理。
- 恢复规则：journal 存在但 manifest 未提交 → 按备份回滚；manifest 已提交 → 清理即可。恢复本身可中断、可重入。
- 验证方式是**故障注入矩阵**（M1 的 38 个边界点 × "N+1 失败后 N 字节不变"断言），不是代码走查。

## 5 · 编译器无权威：只渲染已验证事实

编译器（YAML/Card/Wiki/Mermaid/HTML）不做 IO、不调模型、不产生新陈述；输入在边界整体重验证。对抗性测试把注入载荷（HTML/链接/围栏/标题/缩进代码）放进合同字段，断言输出全部转义为数据。

## 6 · 默认 fail closed 的读路径

每次默认读取校验"精确仓库身份（含脏树哈希）∧ 三代际戳一致"，不满足返回 `knowledge_update_required` 而非旧数据。诊断模式（`--include-stale`）必须醒目标记且绕过安全声明。

## 7 · 有界性是一等约束

证据包 item/字符/token 三重预算、CLI 参数边界、观测输出上限、120s 子进程超时——所有外部输入在进入语义/存储层前被限制和净化（上游 hint 只增强本地判断，从不替代）。

## 8 · 工作流方法：TDD × 双重评审 × 门禁推送

- 每个行为变更从失败测试开始；每个任务一个连贯提交；规格评审 + 代码质量评审双轨通过才算完成。
- 里程碑门禁（exit gate）通过才推送；门禁记录为独立提交（审计链）。
- **双遍全量套件**（计数级一致）暴露顺序/时间依赖；`verify.sh` 把全部离线验证 + live 探测固化成一条命令（D-022）。
- 诚实性纪律：完成归档明确区分"已完成并通过审查"与"已实现但有记录的限制"；未交付的东西在文档里如实标注（曾审查出 commit message 声称交付但实际未交付的 Skill 扩展）。

## 9 · 事故教训（2026-08-25 工作区搬移）

外部事故曾移动整个项目并丢失一个提交——恢复手段是"远程基线 + 会话转录逐字节复原"。由此确立：**门禁通过后立即推送**；文档与代码同仓同版本治理。

## Revision History

- 2026-09-12 从 V0.1 全程实现与审查记录提炼建卷。
