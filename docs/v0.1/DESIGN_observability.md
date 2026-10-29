# DESIGN — 可观测层（trace 泵 + 聚合 + 面板）

> **状态**：active（2026-10-28 定方向，随 T1.2 落地）
> **定位**：alignment-env 除 OpenEnv 式 env 契约外，自带一层 LangSmith 式可观测。
> **方向（用户确认）**：自包含 trace + 面板，**不**造 LangSmith 克隆、不做托管依赖。LangSmith 导出 shim 仅作可选后置。

## 1. 为什么 / 非目标

- **Why**：攻防 env 是长程、多角色（guard/attack/defense）交互，跑起来后只看到 reward/done 无法定位"哪一步、哪个模型、哪个场景出的问题"。可观测性是把"能部署的 demo"变成"可诊断、可交付的工程"的关键。
- **非目标**：不实现 span 树/分布式追踪、不接进 LangSmith/OTel 生态（仅预留导出位）、不做公网托管面板。

## 2. 三层结构（地基 → 聚合 → 视图）

```
 env.reset/step ──emit──▶ TraceSink (JSON-lines / SQLite, 无 GPU 可写)
                                 │
                                 ▼
                          TraceReader (聚合)
                          · per-episode / per-generation 指标
                                 │
                                 ▼
                     Gradio monitor 页 (T1.7) ──可选──▶ LangSmith 导出 shim(后置)
```

### 2.1 地基：TraceSink（env 边界强制 emit）
- 挂在 `AlignmentEnvironment.reset/step` 上，每个**原子交互**产出一条结构化记录，字段：
  `run_id / episode_id / step / role(guard|attack|defense) / model_id /
   prompt(或 action) / output(或 observation) / latency_ms / n_tokens(或 cost) /
   verdict / reward / done`
- 落盘：主写 JSON-lines（`<output>/traces/<run_id>.jsonl`，追加写、可断点）；SQLite 作可选被查询后端。
- **mock 也照常 emit**：无 GPU 干跑（mock provider）时 trace 同样落盘 → 分层 ②③ 在离线可演示，契合"便于部署"。
- 契约以独立 schema/Pydantic 模型定义，与 provider 解耦（就是大盘两层的数据源）。

### 2.2 聚合：TraceReader
- 输入 trace 文件，输出按 episode / generation 聚合的指标：
  攻破率（对齐的 ASR）曲线、avg reward、延迟 p50/p90、token 成本、verdict 分布、错误率/重试。
- 纯函数/小 lib，`monitor` 页直接消费；也是 CLI `ui`/`monitor` 命令的数据源。

### 2.3 视图：Gradio monitor 页（T1.7 升级）
- 在已有 `monitor` 页上加：单 episode 回放（逐 step 的角色/输入/输出/verdict）、
  generation 攻破率曲线、延迟/token 概览。
- 读 2.2，不直接读 trace 文件。

## 3. scope 分级（对应你的优先级）
| 层 | 内容 | 备注 |
|---|---|---|
| ① | TraceSink + schema | **必须**，随 T1.2 的 reset/step 一起落地 |
| ② | TraceReader 聚合 | 必须，无它面板无数据 |
| ③ | monitor 页升级 | 第三顺位（v0.1 M4/T1.7 时做） |
| × | LangSmith/OTel 导出 shim | 可选，后置；有 TraceSink 后成本极低（就是改序列化目标） |

## 4. 落地顺序
1. 定 schema + `TraceSink`（emit 写在 T1.2 的 reset/step 里）。
2. `TraceReader` 聚合出攻破率/延迟/token。
3. T1.7 面板把 2 画出来。

> 偏离本设计时写 REPORT，不改 DESIGN（沿用仓库约定）。