# DESIGN — 架构：transport-free 核心 + 四壳（Step1/Step2）

> **状态**：active（2026-10-28）
> **定位**：alignment-env 的整体架构与交付阶段划分。底层原则就是一条：**env 核心不碰任何传输层**。
> **决策（用户确认）**：Step 1 = 可加载的 CLI + 本机 Gradio webui；Step 2 = **有界切片**的"完整服务"（MCP server + 单机多用户 FastAPI），不做高可用/负载均衡/K8s/多机。
> 相关：可观测层见 [DESIGN_observability.md](DESIGN_observability.md)；v0.1 env 契约见 [DESIGN_v0.1_red_blue_env.md](DESIGN_v0.1_red_blue_env.md)。

## 1. 一句话架构

同一个 **transport-free 的 env 核心**，被四个壳共用；可观测层（TraceSink/TraceReader）是唯一共享数据源。

```
                     alignment-env 核心（transport-free）
                    reset/step/observation/reward，无任何传输耦合
                                     │ emit
        ┌──────────┬───────────┬─────────────┬──────────────┐
        │ CLI      │ Gradio    │ FastAPI      │ MCP server   │
        │ 本机      │ 本机 webui │ 单机多用户/   │ 暴露 env 为   │
        │ 复现/headless│ 演示     │ 可上线切片    │ tools/资源    │
        └──────────┴───────────┴─────────────┴──────────────┘
                                     ▲
                    共享 TraceSink + TraceReader（[DESIGN_observability](DESIGN_observability.md)）
                    远程/多用户时 trace 是唯一的诊断线 → Step 2 价值翻倍
```

## 2. 两条阶段线

| 阶段 | 交付 | 取胜来源 | 范围 |
|---|---|---|---|
| **Step 1** | env 核心 + CLI + 本机 Gradio | 可复现、论文测量面（环1 结论从它出） | v0.1，现在做 |
| **Step 2（有界切片）** | MCP server + 单机多用户 FastAPI | **最硬的 Agent/full-stack 招聘信号** | 后置，边界见 §4 |

**贯穿 Step1/Step2**：TraceSink + TraceReader 作为共享地基——Step1 让它可演示，Step2 翻倍（远程/多用户时它是唯一诊断线）。

## 3. transport-free 核心（现在就写死，别等 Step 2）

- env 核心只实现 `reset/step/observation/reward/done`，**不 import 任何 HTTP / 套接字 / 传输代码**。
- 模型服务（guard/defense/attack）是 env 进程**外**的 HTTP 服务，env 通过注入的 provider 调用（沿用 v0.1 `provider` 抽象），回退 mock 可干跑。
- `reset/step` 里只做一件事的副作用：**emit trace**（见可观测 DESIGN）。
- 四壳各自只写"交互/协议适配"，不写业务逻辑 → Step1→Step2 是加 transport，不是重写核心。

## 4. Step 2 有界切片（范围契约，超出即停）

**必须**：
- **MCP server**：把红蓝环境暴露成 MCP tools/资源（`mcp.run/<env>` 等），任何 agent/app 可作为"能力"调用。
- **单机多用户 FastAPI**：HTTP 后端，带**最简 auth**（公共版无密钥可选 closed 部署；明记"公共 demo 一律 auth 且不进密钥"）。
- 复用可观测面板（多用户/远程的 trace 可视化）。

**不做**：高可用 / 负载均衡 / K8s / 多机分布式 / 公网无鉴权暴露。这些是"想更深"的后续，不做进当前边界。

## 5. timeline 落位（现状骨架）

```
现在     v0.1（Step1）── T1.1..T1.9（env/T1.2 起步 → 可观测/面板后置）
后置     v0.2（Step2 边界）── MCP server → 单机多用户 FastAPI → 上线加固(可选)
贯穿     环1 研究结论（攻破率 vs 世代 / 防御脆弱性 / RSI 收敛）未必只在尾部，随 env 完成即可开始采集
```

## 6. 偏离处理
- 偏离本 DESIGN 时写 REPORT，不改 DESIGN（沿用仓库约定）。