# TODO_v0.1 — 红蓝攻防对齐环境

> **状态**：`active`
> **更新**：2026-10-27

## 进行中 / 下一步

| # | 任务 | 优先级 | 验收条件 | 状态 |
|---|---|---|---|---|
| T1.1 | OpenEnv 脚手架 + repo 初始化 + 冒烟（reset/step/state 往返） | — | 服务端 + client 得 reward/done | ✅ 完成 |
| T1.1b | **模型层**：config(guard/attack/defense, defense=trainable) + modelscope 下载(断点续传+完成判定) + ModelProvider(mock/openai vLLM) + CLI `models init/show/status/prepare` | P0 | show/status/factory 冒烟通过；指向 /mnt 能识别已下载 | ✅ 完成 |
| T1.2 | 攻防模型与 env 逻辑：`AttackAction` / `AttackObservation` / `AlignmentEnvironment.reset/step`，target/guard provider 注入 + mock | P0 | 单场景 step 用 mock guard 出 reward + done | ✅ transport-free core（偏离：非 OpenEnv 子类，见 REPORT） |
| T1.3 | 真 guard/defense 接入（provider 指向 vLLM base_url），单轮 step 出真实 reward | P0 | reward 分布有区分度；实测 guard HTTPS 延迟 | ⏳ GPU 环境 |
| T1.4 | 合成场景器（受害者卡：角色/立场/话题/禁泄露对象） | P1 | 能采样多样化场景 | ✅ scenarios.py |
| T1.5 | 自进化红队：攻击库 → 打 defense → guard → reward 回填改写 | P0 | 30 轮采集，攻破率随世代上升 | ✅ redteam.py+redrun（mock 0→75%） |
| T1.6 | CLI：`alignment-env launch/redrun/monitor/models` | P1 | 命令可复现 | ✅ |
| T1.7 | Gradio 控制面（演练/监控/自进化 三页） | P1 | 面板可看进度/回放/曲线 | ✅ |
| T1.9 | **可观测层**：`TraceSink`(schema+emit@reset/step, JSON-lines) → `TraceReader`(聚合攻破率/延迟/token) → monitor 页消费 | P1 | mock 干跑也能落 trace 并被面板读出；DESIGN_observability.md | ✅ obs/jsonl.py |
| T1.8 | COOKBOOK（首次上手 + 代理地雷）+ REPORT（M1–M4） | P1 | 可复现 | ✅ |

## 依赖

- T1.2 是 T1.3/T1.5 的前提；T1.5 依赖 T1.3（真 guard）+ T1.4（场景）。
- T1.6/T1.7 可并行于 T1.5 之后。

## 设计对照

- 接口与取舍见 [DESIGN_v0.1_red_blue_env.md](DESIGN_v0.1_red_blue_env.md) §5/§3。
- 偏离 DESIGN 时写进 REPORT，不原地改 DESIGN。