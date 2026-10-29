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

    demo.launch(server_name=os.getenv("ALIGN_WEBUI_HOST", "127.0.0.1"),
                server_port=int(os.getenv("ALIGN_WEBUI_PORT", "7860")))
    return demo


if __name__ == "__main__":
    main()