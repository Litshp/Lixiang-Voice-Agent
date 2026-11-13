# 改善报告

- 实际投入：本次 session 未单独计时，提交前需按实际记录补填；环境准备：约 5 分钟
- 一句话成果：明确且低风险的已确认目标现在可绕过模型直接执行，eligible 场景的澄清从 3/36 降为 0/36，P95 从 930ms 降为 580ms，平均模型成本降为 0。

## 问题与判断

旧 `legacy_task_success` 只代表收到回执。baseline 为 90/100，但按真实目标核验只有 88/100 正确完成，且有 2/100 错误目标执行。优先保留高风险和非幂等安全底线，同时处理明确低风险请求的多余模型调用和澄清。尝试将明确请求全部路由到 `small` 后，澄清增加、完成率下降，因此按 EVAL_PLAN 的调整记录撤回该方案。

## 成果与证据

- 入口：`evals/candidate/run_fast_path.py`；指标：`evals/candidate/analyze.py`。
- 原约束 baseline（100/100）：正确完成 88/100，错误目标 2/100，非幂等重复 0/100，澄清 43/100，P95 1380ms，平均模型成本 0.00314 USD。
- 边界 fast path（100/100）：正确完成 89/100，错误目标 2/100，非幂等重复 0/100，澄清 40/100，整体 P95 1380ms，平均模型成本 0.00206 USD。
- fast path eligible 组（明确目标、低风险，36/36）：正确完成从 35/36 提升到 36/36，澄清从 3/36 降到 0/36，P95 从 930ms 降到 580ms。before/after timeout 仍使用原幂等键，未产生重复 commit。
- 复现：`UV_CACHE_DIR=/tmp/codex-uv-cache uv run --quiet --offline --no-project python -m evals.candidate.run_fast_path --out runs/fast_path`；随后运行 `UV_CACHE_DIR=/tmp/codex-uv-cache uv run --quiet --offline --no-project python -m evals.candidate.analyze --traces runs/fast_path/traces.jsonl --out runs/fast_path/oracle_summary.json`。

## 最终取舍与限制

保留 fast path 作为独立边界实验，不宣称它已经改善原 simulator 下的整体 P95。高风险和模糊请求仍走 baseline，已有 2/100 低风险错误目标仍未解决。新增假设是 `explicit_target` 已经是产品侧确认目标，规则路径不调用模型，模型成本计为 0；规则本身的真实解析成本尚未测量。下一步应在真实入口验证确认目标的来源和规则执行授权，再决定是否纳入产品接口。

## 个人判断与 AI 交互

本次使用 Codex 完成材料审计、指标设计、失败策略比较、TDD 和验证；用户指出“增加澄清会恶化 P95”，据此撤回全量保守澄清方向，改为规则优先 fast path。当前工程没有可导出的本地 session 文件，缺失情况见 `ai-sessions/INDEX.md`。
