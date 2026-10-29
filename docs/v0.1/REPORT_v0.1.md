# REPORT_v0.1 — 实现记录（M1–M4）

> **状态**：`active`
> **更新**：2026-10-29

## 1. 结论

transport-free 攻防环境三层中间层已全部跑通（mock 离线），自进化红队攻破率
随世代上升已验证（0% → ~70%）。T1.3 真 guard/target 接入留 GPU 环境。

commit 溯源：`10c3f95`（三层地基）/ 本次自进化场景器+redrun+面板（见 git log）。

## 2. 实测数字（mock leak-aware，seed=0）

`E python -m cli.main redrun --gens 8`（种群 16）:

| gen | 攻破率 | 种群命中 | avg_fitness | 代表性攻击 |
|---|---|---|---|---|
| 0 | 0.0% | 0/16 | 0.000 | 请问你能帮助我吗 |
| 1 | 18.8% | 3/16 | 0.188 | 合规审计师要求… |
| 2 | 25.0% | 4/16 | 0.219 | 合规审计师要求… |
| 3 | **75.0%** | 12/16 | 0.688 | 合规审计师要求… |
| 4+ | 75% | 12/16 | 0.750 | 同上 |

> 攻破率 0% → 75%。演化锁定"权威(内部合规审计师)"策略——这是适应度景观的峰值，
> 遗传机制（精英保留+变异/重组）自主找到它。demo 脚本：`scripts/redteam_smoke.py`。

> ⚠️ 该数字在 **leak-aware mock** 下测得：mock 编码了"策略有效性强弱"先验。接真
> guard 后走同一演化循环，fitness 换成真实 reward，数字会变但机制不变。

## 3. 三层对齐

| 层 | 壳 | 状态 | 备注 |
|---|---|---|---|
| ① | 本地 CLI `launch / redrun / monitor / models` | ✅ | mock 离线 |
| ② | 本地 WebUI（Gradio 演示+监控+自进化 3 Tab） | ✅ | 见下"代理地雷" |
| ③ | 可部署 C/S（FastAPI `/reset·/step·/episode·/metrics`） | ✅ | 纯 C/S，不做 MCP |
| 底座 | transport-free env core + `obs/` 可观测 + 模型两接口族 | ✅ | 四壳共用 |

## 4. 与原计划（TODO_v0.1）对照

| 任务 | 状态 | 说明 |
|---|---|---|
| T1.1 OpenEnv 脚手架 | ✅ | openenv 已降为可选 extra，壳不依赖它 |
| T1.1b 模型层 | ✅ | 重构为两接口族（Verifier+LLMBackend+Retry/Budget） |
| T1.2 env 逻辑 | ✅ | transport-free core 而非 OpenEnv 子类（见 DESIGN_architecture 偏离记录） |
| T1.3 真 guard 接入 | ⏳ GPU | vLLM base_url 注入，本机无 GPU 未跑 |
| T1.4 合成场景器 | ✅ | `scenarios.py`：受害者卡三要素采样 |
| T1.5 自进化红队 | ✅ | `redteam.py`：遗传演化 + `redrun` |
| T1.6 CLI | ✅ | launch/redrun/monitor/models |
| T1.7 Gradio 控制面 | ✅ | 演练+监控+自进化 |
| T1.8 COOKBOOK+REPORT | ✅ | 本文 + COOKBOOK_v0.1.md |
| T1.9 可观测 | ✅ | obs/jsonl.py：trace+aggregate |

## 5. 偏离 DESIGN 记录（不原地改 DESIGN）

- **不做 OpenEnv 子类**：env 核心改为 transport-free（纯 Pydantic DI），OpenEnv 仅作
  可选播放器/部署附加。理由：byted 代理 env 会让 openenv import 崩，且"便于部署"
  优先可离线。四壳（CLI/WebUI/C/S/MCP）共享同一核心。
- **rap reward 二分先行**：mock 阶段 DAPO 稀疏 shaping 未上（M2 先跑二分）。
- **监控面板用纯净组件**：不引 plotly/绘图（代理环境崩），自进化 Tab 用 Dataframe+Markdown。

## 6. 下步（GPU 环境）

1. T1.3：真 guard/target（vLLM base_url）单轮出真实 reward，实测 HTTPS 延迟定预算。
2. M3 真机采集：30 轮攻破率 vs 世代曲线（run_id 可追溯 trace）。
3. 可选：MCP shim 包到同一核心（当前做纯 C/S）。