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

### 3.5 模型层（先于攻击方法落地）
做攻击方法前把模型地基做好（`models/` 包，供 env 与训练共用）。三个模型角色：

| 角色 | 默认 ModelScope id | trainable | 说明 |
|---|---|---|---|
| guard（评估/奖励） | `Qwen/Qwen3Guard-Gen-4B` | 否 | 冻结，判攻破 → reward |
| attack（攻击） | `Qwen/Qwen3-4B` | 否 | 冻结，生成红队攻击 |
| defense（防御/受害者） | `Qwen/Qwen3-4B`（用户可改） | **是** | 待训练对象；env 里的 "target" |

- 语义：guard 与 attack 固定（注入的评估/攻击模型），defense 是唯一被训练、且由用户指定的角色。
- 下载走 ModelScope（`modelscope snapshot_download`），断点续传；完成判定沿用 jailbreak：`config.json` 存在且无 `*.incomplete`。
- 缓存默认 `~/.cache/alignment-env/models`，`ALIGN_MODEL_DIR` 覆盖（byted 可指向现有 `/mnt/.../models` 复用已下载模型）。
- `ModelProvider` 两后端：`mock`（离线可部署）与 `openai`（vLLM endpoint）。`build_all(config)` 装配三角色 provider。
- 覆盖优先级：环境变量（`ALIGN_<ROLE>_MODEL` / `_BACKEND` / `_BASE_URL`）> `models.yaml` > 默认。

**env 与模型的映射**：env 内 `red → attack provider`，`target(受害者) → defense provider`，`reward → guard provider`。attack 方法(T1.2+)在此之上实现，不再耦合某具体模型。

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

三个角色全注入式（DI），env 与算法解耦：
```python
target = injectable(LLM)   # 受害者；默认 mock，可换 vLLM base_url
guard  = injectable(LLM|rule)  # 奖励来源，冻结
red    = injectable(policy|evolver|human)  # v0.1 = 自进化红队
```

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