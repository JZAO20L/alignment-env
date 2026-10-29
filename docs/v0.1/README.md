# v0.1 — 红蓝攻防对齐环境

> **状态**：`active`

## 范围

v0.1 交付一个自包含、可部署的红蓝攻防对齐环境：

- `envs/red_blue_env/`：OpenEnv 包装的攻防环境（`reset/step/state` + 自带 Web 播放器）。
- 攻击方为**自进化红队**：从攻击库采样 prompt → 打受害者 → guard 判罚 → reward 回填并改写攻击库。
- CLI + Gradio 控制面：`launch / train / monitor`。

非目标：v0.1 不接 RL 训练（`red` 可从 verifier 换可训练 policy，但那在 v0.2）；不做公网暴露。

## 目标（v0.1）

1. 标准 env 契约，任何 trainer 可消费（reward/done 在 observation 上）。
2. Reward 来自冻结 guard 模型，可注入（mock / vLLM）。
3. 红队攻击库自进化，攻破率随世代单调上升（M3）。
4. 无 GPU 也能干跑（mock target/guard）——满足"便于部署"。

## 里程碑

| 里程碑 | 内容 | 验收 |
|---|---|---|
| **M1** | OpenEnv 脚手架 + 真实 API 核对 + `reset/step/state` 冒烟 | 服务端 + client 往返得 reward/done ✅ |
| **M2** | 攻防模型与 env 逻辑（AttackAction / AttackObservation / 注入 target/guard） | 单场景 step 出真实 reward |
| **M3** | 自进化红队 + 合成场景采样，30 轮采集 | 攻破率 vs 世代曲线上升 |
| **M4** | Gradio 三页控制面 + README + 本地可干跑 | 面板可看、README 可复现 |

## 索引

- DESIGN：[DESIGN_v0.1_red_blue_env.md](DESIGN_v0.1_red_blue_env.md)
- DESIGN·架构（Step1/Step2 + transport-free 核心 + 四壳）：[DESIGN_architecture.md](DESIGN_architecture.md)
- DESIGN·可观测层（trace 泵 + 聚合 + 面板）：[DESIGN_observability.md](DESIGN_observability.md)
- TODO：[TODO_v0.1.md](TODO_v0.1.md)
- COOKBOOK（首次上手 + 代理地雷 + 命令速查）：[COOKBOOK_v0.1.md](COOKBOOK_v0.1.md)
- REPORT（M1–M4 实现记录 + 自进化实测数字）：[REPORT_v0.1.md](REPORT_v0.1.md)