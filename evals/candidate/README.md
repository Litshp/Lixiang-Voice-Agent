# 自建评测

在此新增 test_*.py，通过标准库 unittest 执行；test_example.py 只是用法示例，不算完成所选问题的评测。

至少覆盖所选问题的失败、新实例、正常回归及边界/代价。可复制公开场景结构后创建新输入，但要说明为什么预期该行为。目标名称可变化，不依赖原始场景 ID。

推荐在独立 analyze.py 中输出带分子、分母的指标 JSON，保存复现命令和结果。不要求固定指标数量或图表。策略只接收运行时 observation/prediction/timeout；world 仅用于评测断言。

## 当前开发成果：规则优先边界实验

从项目根目录运行（只用标准库）：

```sh
UV_CACHE_DIR=/tmp/codex-uv-cache uv run --quiet --offline --no-project python task.py check
UV_CACHE_DIR=/tmp/codex-uv-cache uv run --quiet --offline --no-project python -m evals.candidate.reproduce
```

第二条一并保存原约束 before/after、被拒绝的 small 路由及 0/20/21ms 额外规则开销的独立边界结果。`runs/comparison.json` 包含带分母的总指标、简单指令/高风险/歧义分组和非适用请求的动作差异列表。before/after 表示原契约的 baseline 保留，不代表 fast path；边界结果位于 `runs/fast_path*`。

`decide` 只接收 observation。`fast_path._run_direct` 是独立工具模拟，不是可部署的真实工具调用器；world 只在模拟执行结果与事后评分中使用。确认目标可信、低风险时省略模型调用是实验唯一的接口调整；不增加新的确认输入。真实规则额外延迟未知，20/21ms 是用于推翻性能承诺的假设值。

自建 oracle：`test_fast_path.new_scene` 声明对新目标 `courtyard_purifier` 的明确操作，模型故意漏掉目标、用户不回答澄清，预期由 confirmed target 唯一决定。三种动作的正常等待为 80ms，超时并以原键重试为 580ms，非幂等动作必须恰好一次。高风险/歧义输入须复用原决策。故意把 world.target 改成另一个目标的测试违反确认契约，用来证明输入前提失效时 fast path 不能自修复；不纳入产品收益统计。

指标 oracle：task_completed 要求所有 commits 目标/动作正确且至少一次；set_power 同目标重复不抹去任务结果，但计入 extra_commits；toggle/send_message 要求恰好一次。correct_once 单列，旧回执指标保留。high_risk_error 是高风险错目标或任意风险下的非幂等重复的并集，分母为所有请求；high_risk_wrong_target 的分母为 risk=high 请求，0 分母的比例为 null。
