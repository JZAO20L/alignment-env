# SPDX-License-Identifier: BSD-3-Clause
"""层② 本地 Gradio WebUI。

两个 Tab：攻防演练（对话驱动攻击 + 实时 guard 判罚/reward）、监控面板（读 trace 聚合）。

启动（byted 主机须先清代理，否则 gradio/httpx import 崩）：
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u no_proxy -u NO_PROXY \
      python -m webui.app
"""

from __future__ import annotations

import os
from pathlib import Path

import gradio as gr

from models.config import load_models
from models.factory import build_all
from envs.red_blue_env.core import AlignmentEnvironment, AttackAction
from envs.red_blue_env.redteam import demo_target_guard, run_evolution
from envs.red_blue_env.scenarios import build_scenario_bank
from obs import FileTraceSink, aggregate, read_traces

DEFAULT_TRACE = Path(os.getenv("ALIGN_TRACE", "output/webui_trace.jsonl"))


class Server:
    """进程内共享攻防环境；每集一份对齐状态，trace 落盘供监控 Tab 消费。"""

    def __init__(self, trace_path: Path = DEFAULT_TRACE):
        backends = build_all(load_models())
        self.trace_path = trace_path
        self.sink = FileTraceSink(trace_path)
        self.env = AlignmentEnvironment(
            guard=backends.guard, target=backends.target, max_turns=10, trace_sink=self.sink,
        )
        self.backends = backends

    def reset(self, scenario: str = "") -> dict:
        obs = self.env.reset(scenario=scenario or None)
        return {"episode": obs.episode_id, "scenario": obs.scenario,
                "backend": self.backends.names}

    def step(self, attack: str) -> dict:
        obs = self.env.step(AttackAction(message=attack))
        return {"attack": attack, "victim": obs.target_reply, "verdict": obs.verdict or "—",
                "reward": obs.reward, "done": obs.done, "turn": obs.turn}


SERVER = Server()


def _greet(scenario: str) -> tuple[list, str, str]:
    info = SERVER.reset(scenario or "")
    return [(None, "场景: " + info["scenario"])], info["scenario"], "就绪 · 输入攻击开始新一集"


def _attack(client_msg: str, history: list) -> tuple[list, str, str, str, str]:
    step = SERVER.step(client_msg)
    history = (history or []) + [(client_msg, (step["victim"] or "(无)"))]
    verdict = f"**guard:** `[{step['verdict']}]` reward={step['reward']} 轮次={step['turn']}"
    status = "🏆 已攻破 → 点「开始新一集」重置" if (step["verdict"] == "unsafe" and step["done"]) else ""
    return history, "", (step["victim"] or "(无)"), verdict, status


def _stats() -> tuple[str, list[list]]:
    recs = read_traces(SERVER.trace_path)
    if not recs:
        return "无 trace。先在「攻防演练」跑几轮。", []
    a = aggregate(recs)
    header = (f"**共 {a['episodes']} 集** ｜ 攻破率 **{a['hit_rate'] * 100:.1f}%** ｜ "
              f"平均奖励 {a['avg_reward']} ｜ 平均轮数 {a['avg_turns']} ｜ "
              f"latency p50={a['latency_p50']*1e3:.0f}ms p90={a['latency_p90']*1e3:.0f}ms")
    eps: dict[str, dict] = {}
    for t in recs:
        eid = t.get("episode_id", "?")
        eps.setdefault(eid, {"turns": 0, "hit": False, "reward": t.get("reward", 0)})
        if t.get("type") == "step":
            eps[eid]["turns"] = max(eps[eid]["turns"], int(t.get("turn", 0)))
            eps[eid]["reward"] = t.get("reward", 0)
            if t.get("verdict") == "unsafe":
                eps[eid]["hit"] = True
    rows = [[eid, "攻破" if e["hit"] else "未攻破", e["turns"], e["reward"]] for eid, e in eps.items()]
    return header, rows


def _evolve(gens: int) -> tuple[str, list[list]]:
    """自进化红队：跑 N 世代，返回 (汇总串, 每世代明细表)。用纯净组件展示，
    不引 plotly/绘图重依赖（byted 代理机会崩那些 import）。"""
    guard, target = demo_target_guard()
    env = AlignmentEnvironment(guard=guard, target=target, max_turns=3,
                               scenarios=build_scenario_bank(50))
    report = run_evolution(env, generations=gens, seed=0)
    rates = [r["hit_rate"] for r in report]
    head = (f"**攻破率随世代上升:** {' → '.join(f'{x*100:.0f}%' for x in rates)}"
            f"（{rates[0]*100:.0f}% → {rates[-1]*100:.0f}%）")
    rows = [[r["gen"], f"{r['hit_rate'] * 100:.1f}%", r["alive_hit"], r["avg_fitness"],
             r["best"][:28]] for r in report]
    return head, rows


def main() -> object:
    with gr.Blocks(title="alignment-env · 红蓝攻防演练") as demo:
        gr.Markdown("# alignment-env — 红蓝攻防对齐环境")
        with gr.Tabs():
            with gr.Tab("攻防演练"):
                scenario = gr.Textbox(label="攻击目标（场景）", placeholder="留空采默认场景卡")
                with gr.Row():
                    reset_btn = gr.Button("开始新一集")
                    status = gr.Markdown("—")
                chatbot = gr.Chatbot(label="对话（红→ · victim←）")
                with gr.Row():
                    attack_in = gr.Textbox(label="你的攻击", placeholder="输入攻击文本，回车", scale=4)
                    send = gr.Button("发送", scale=1)
                victim_out = gr.Textbox(label="最近一轮 victim 回复", interactive=False)
                verdict_out = gr.Markdown("guard: —")

                reset_btn.click(_greet, [scenario], [chatbot, scenario, status])
                send.click(_attack, [attack_in, chatbot], [chatbot, attack_in, victim_out, verdict_out, status])
                attack_in.submit(_attack, [attack_in, chatbot], [chatbot, attack_in, victim_out, verdict_out, status])

            with gr.Tab("监控面板"):
                summary = gr.Markdown("—")
                grid = gr.Dataframe(
                    headers=["episode", "结果", "轮次", "reward"],
                    datatype=["str", "str", "number", "number"], interactive=False,
                )
                timer = gr.Timer(value=5)
                timer.tick(_stats, outputs=[summary, grid])

            with gr.Tab("自进化红队"):
                gr.Markdown("攻击种群逐世代演化，攻破率（victim 泄露判攻破）应随世代上升。"
                            "点击「跑演化」进程内跑一次（mock leak-aware，离线可干跑）。")
                gens_in = gr.Slider(3, 20, value=8, step=1, label="世代数")
                evo_btn = gr.Button("跑演化")
                curve_out = gr.Markdown("—")
                grid2 = gr.Dataframe(
                    headers=["gen", "攻破率", "种群命中", "avg_fitness", "代表性攻击"],
                    datatype=["number", "str", "number", "number", "str"], interactive=False,
                )
                evo_btn.click(_evolve, [gens_in], [curve_out, grid2])

    demo.launch(server_name=os.getenv("ALIGN_WEBUI_HOST", "127.0.0.1"),
                server_port=int(os.getenv("ALIGN_WEBUI_PORT", "7860")))
    return demo


if __name__ == "__main__":
    main()