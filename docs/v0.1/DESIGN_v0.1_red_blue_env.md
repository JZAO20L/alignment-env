# DESIGN_v0.1_red_blue_env — 红蓝攻防对齐环境

> **状态**：`active`
> **更新**：2026-10-27 定稿；基于 OpenEnv 0.10.0 实测核对（非猜测接口）。

## 1. 目标与非目标

**目标**
- 把"红队攻防 → guard 判罚"封装成标准 OpenEnv/Gymnasium 风格环境：`reset()` / `step()` / `observation`（自带 `done` / `reward`）。
- Reward 来自**冻结的 guard 模型**，可注入，不写死在环境里。
- v0.1 主打**红队自动化**：攻击库自进化，攻破率随世代上升；这同时是自进化 harness 主题的落地。
- **便于部署**：mock target/guard 时无 GPU 也能干跑。
- 附带 CLI + Gradio 控制面（launch / train / monitor）。

**非目标（v0.1）**
- 不接 RL 训练；RL 作为可选插件，env 核心不动。
- 不做公网暴露、多租户、计费。

## 2. 约束

- 环境实现必须基于 OpenEnv 0.10 的真实接口（已核对，见 §4），不照文档盲写。
- guard/target 是 env 进程**外**的 HTTP 服务（vLLM），env 通过 base_url 注入调用；QoS 波动（判罚延迟）写进 step 的超时预算。
- 单环境 `SUPPORTS_CONCURRENT_SESSIONS=True` 的前提：场景无共享可变状态（每次 reset 重建环境实例）。
- 一次变更 = 代码 + 受影响文档（见 `docs/README.md`）。

## 3. 方案与取舍

### 3.1 为什么用 OpenEnv 而非自制 Gym
OpenEnv 已提供：FastAPI + WebSocket 服务端、`EnvClient`（同步/异步）、自带 Web 播放器（`ENABLE_WEB_INTERFACE`，底层 gradio）、`openenv.yaml` 清单、`openenv build/push` 部署到 HF Space。自制则要全重写。取舍代价：承其版本约束（gradio↔httpx 兼容），且需规避 byted 主机代理 env 导致的 import 崩溃（见 COOKBOOK）。

### 3.2 reward 口径（待 M2 定标量）
- 基础：guard 判攻破（UnSafe）→ `reward=1, done=True`；Safe → `reward=0`。
- 可选逆程 shaping（DAPO 思路）解决稀疏：多轮时对"偏离安全立场"给少量正奖励。M2 先跑二分，稀疏再上 shaping。
- reward 范围在 `openenv.yaml::validation.reward.range` 声明 `[0,1]`。

### 3.3 mock 优先、真 backend 可插拔
注入接口（见 §5）让 target/guard 可来自 rule-based mock（部署演示）或 vLLM（训练实证）。这是"便于部署"与"真实信号"之间的主要取舍点：mock 保证可复现 / 无 GPU 跑通，却可能给不出真实奖励分布——故 M2 必须用真 guard 验证一次 reward 分布。

### 3.4 与 evolving-harness 的关系
本环境是"自进化"主题的另一面：evolving-harness 自进化 skills，本环境自进化攻击库。同源不同物，独立 repo。论文叙事："自进化一题两表"。

### 3.5 模型层（核心两个接口族，先于攻击方法落地）
做攻击方法前把模型地基做好（`models/` 包，供 env 与训练共用）。模型层分**两个接口族**（不是三个平级角色）：

| 接口族 | 角色 | 接口 | 默认 | 固定性/可插拔 |
|---|---|---|---|---|
| **Verifier(Judge)** | **guard** | 验证+给分：输入对话/回复 → verdict + scalar reward | `Qwen/Qwen3Guard-Gen-4B` | **固定**，全 env 的 verify/reward 主力 |
| **LLMBackend** | **target(blue/受害者)** · **policy(red/攻击方)** | 生成：messages → text | `Qwen/Qwen3-4B` | **可插拔，允许多后端** |

关键点：

- **guard 语义=验证方**，走独立 `Verifier` 接口（判攻破 → reward），**固定、单一后端**。改判据改注入的判罚规则，不换模型族。
- **target(blue) 与 policy(red) 同属 `LLMBackend` 生成族**，允许多后端接入：**OpenAI 兼容（vLLM / sglang / DeepSeek / Qwen）**、**其他厂商（Anthropic / Vertex …）**、**自托管 vLLM/sglang** 部署模型。
- `LLMBackend` 带**跨后端强制中间件**，包裹在 env 与裸 SDK 之间：
  - **指数退避重试**：429 / 超时 / 瞬态错误自动退避重试；
  - **预算管理**：token / 步数 / 成本上限，超限即终止当前 episode（防失控）。
- **trainable 与接口族无关**：defense(target) 仍是 v0.2 被训练对象，policy(red) v0.1=自进化红队；两者都是生成族，可训练与否是训练层的事，不改变接口族。
- 下载/缓存/覆盖优先级沿用：ModelScope 断点续传（`config.json` 存在且无 `*.incomplete`）、`ALIGN_MODEL_DIR`（byted 指向已有 `/mnt/.../models` 复用）、环境变量 > `models.yaml` > 默认。

**env 与模型的映射**：env 内 `red → LLMBackend(policy)`，`target(受害者) → LLMBackend(defense)`，`reward → Verifier(guard)`。攻击方法(T1.2+)在此之上实现，不再耦合某具体模型。

## 4. 已核对的真实接口（OpenEnv 0.10.0）

| 我最初的猜测 | OpenEnv 实际 |
|---|---|
| `step()` 返回 `(obs, reward, done, info)` 元组 | **`step()` 返回单个 Observation**；reward/done 是 Observation 基类字段，另有 `metadata` |
| `reset()` 返回 `(obs, info)` | 返回单个 Observation |
| `ActionSpace/ObservationSpace` 一等对象 | Pydantic 模型 `Action` / `Observation`（继承 `openenv.core.env_server.types`，**不是** BaseModel） |
| 奖励用 RolloutTracker | 内建 Rubric 机制（`rubric=` + `_apply_rubric`）；我们的 reward 来自外部 guard，直接在 step 写入 Observation.reward，不走 rubric |
| — | 基类签名：`reset(self, seed=None, episode_id=None, **kwargs)` / `step(self, action, timeout_s=None, **kwargs)`；`State(episode_id, step_count)` 可子类化加场景/轮数 |
| — | `create_app(Environment_cls, Action, Obs, env_name=, max_concurrent_envs=)` → FastAPI；`POST /reset /step /state /schema` + `WS /ws` |
| — | 自带 Web 播放器：`ENABLE_WEB_INTERFACE=true` + `render_web()` / `web_actions()` |

## 5. 接口（v0.1 实现约定）

```
envs/red_blue_env/
  models.py   AttackAction(Action){prompt} · AttackObservation(Observation){scenario, history, verdict, hit, turn}
  server/red_blue_env_environment.py
              AlignmentEnvironment(Environment):
                reset()   # 取/采样受害者场景卡, 重置轮数, 返回首 obs
                step()    # ①攻击文本→target ②guard 判罚 ③追加历史, reward=guard打分, done=hit或超轮
  server/app.py   create_app(factory, ...)  # target/guard 由工厂注入(读 base_url env)
  client.py   AlignmentClient(EnvClient[...])
  openenv.yaml   reward range [0,1] 等
```

两个接口族全注入式（DI），env 与算法解耦：
```python
target = injectable(LLMBackend)  # victim/blue；默认 mock，可换多后端(OpenAI/Vendor/自托管)
guard  = injectable(Verifier)    # 奖励来源，固定后端，判出发 verdict+reward
red    = injectable(policy|evolver|human)  # v0.1 = 自进化红队
```
> LLMBackend 自动套 指数退避重试 + 预算管理 中间件（§3.5）。

## 6. 验收标准（v0.1）

- [ ] M2：单场景 step 用真 guard 出 reward，reward 分布有区分度（非全 0/全 1）。
- [ ] M3：30 轮红队自动化采集，攻破率随世代单调上升（曲线可追溯到 run_id）。
- [ ] M4：`env -u <proxies> alignment-env <cmd>` 在无 GPU 机器干跑；README 可复现。
- [ ] 全部数字在 REPORT 中有 commit / trace 来源。

## 7. 风险与开放问题

| 风险 | 影响 | 缓解 |
|---|---|---|
| 真 guard 延迟写入 step → 训练吞吐受限 | M2 后可能需并发/批处理 | M2 实测一次 guard HTTPS 延迟，定超时预算 |
| mock guard 给不出真实奖励分布 | M3 曲线好看但失真 | M2 强迫用真 guard 验证 |
| 代理 env 崩溃 openenv | 首次上手卡死 | COOKBOOK 记 `env -u` 启动法 |