# Live Smoke Runbook（真实 CodeWiki + LiteLLM 端到端冒烟）

> 用途：闭合恢复计划中唯一保持 opt-in 的验收项，在真实仓库上跑通一次非夹具的完整构建。全程约 5–15 分钟，消耗一次真实 LLM 调用量（小型仓库约 0.5–2M tokens）。

## 0. 前置核对

```bash
codewiki --version        # 必须 ∈ 0.6.x（0.7+ 会被 preflight 拒绝）
.venv/bin/python -m pytest tests/integration/test_live_primary_build.py -q
# 期望：1 skipped（未设环境变量时的默认状态）
```

## 1. 环境变量

```bash
export KNOWLEDGE_EXTRACTION_MODEL="<litellm 模型串>"   # 例如 openai/gpt-4o-mini、zhipu/glm-4.x
export <对应 PROVIDER>_API_KEY="..."                   # litellm 按模型串前缀读取
# 仅当 .knowledge/config.yaml 的 worker_profiles 配置了 validation_profile 时才必需：
export KNOWLEDGE_VALIDATION_MODEL="<litellm 模型串>"
```

模型串兼容 litellm 全部路由；密钥永不入库、不写入 `.knowledge/`。

## 2. 目标仓库与构建

```bash
R=/path/to/target-git-repo          # 干净工作树；将被读取但不会被修改
cd "$R"
git status --porcelain              # 必须为空：脏树会被检索门禁正确拒绝
/Users/qiming/workspace/CodeWiki/.venv/bin/knowledge init --language zh
/Users/qiming/workspace/CodeWiki/.venv/bin/knowledge build --executor llm
echo $?                             # 期望 0（2 = partial，1 = failed；报告在 .knowledge/state/runs/last-build.json）
```

构建成功后应存在：`manifest.yaml`（三戳一致）、`plan.yaml`、`objects/**`、`views/wiki/index.md`、`views/cards/**`、`exports/repo-wiki.html`、`cache/knowledge-index.sqlite3`。

## 3. 读侧验证

```bash
knowledge status
knowledge validate
knowledge context "在 checkout 流程中库存何时被预留？"
knowledge compile                   # 幂等重跑应逐字节一致
knowledge open                      # 打开 HTML；若曾落后会先告警
```

## 4. 闭合 opt-in 测试

```bash
cd /Users/qiming/workspace/CodeWiki
KNOWLEDGE_RUN_LIVE=1 KNOWLEDGE_LIVE_REPOSITORY="$R" \
  .venv/bin/python -m pytest tests/integration/test_live_primary_build.py -q
# 期望：1 passed
```

## 5. 常见故障对照

| 现象 | 处置 |
|---|---|
| `codewiki version is unsupported` | 安装/切换 0.6.x |
| `KNOWLEDGE_EXTRACTION_MODEL is not configured` | 补导出环境变量 |
| litellm 401/403 | 密钥未导出或与模型串前缀不匹配 |
| `repository has uncommitted changes`（检索时） | 预期行为：提交或还原工作区后重试 |
| 构建结果 `partial` | 查看 `last-build.json` 的 diagnostics；个别目标 insufficient_evidence 属正常产品行为，记录即可 |

## 6. 回收

把以下三样贴回会话即可完成验收归档：`last-build.json`、`knowledge status` 输出、opt-in 测试的 pytest 尾行。
