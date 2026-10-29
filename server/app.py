# SPDX-License-Identifier: BSD-3-Clause
"""层③ 可部署 C/S 服务（FastAPI 壳，包同一 transport-free core）。

把 AlignmentEnvironment 暴露为 HTTP/JSON，复用 core（不重复业务逻辑），
trace 落盘 → /metrics 聚合（可观测层）。跨语言、可部署到远程节点。

启动：
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u no_proxy -u NO_PROXY \
      python -m server.app            # 默认 127.0.0.1:8100，host/port 用环境变量覆盖

端点：
  POST /reset         {scenario?}        -> {episode_id, observation}
  POST /step          {episode_id, message} -> observation
  GET  /episode/{id}  -> observation（当前快照）
  GET  /health        -> ok
  GET  /metrics       -> 攻破率/平均奖励/latency（读 trace）
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from models.config import load_models
from models.factory import build_all
from envs.red_blue_env.core import AlignmentEnvironment, AttackAction
from obs import FileTraceSink, aggregate, read_traces

DEFAULT_TRACE = Path(os.getenv("ALIGN_TRACE", "output/server_trace.jsonl"))
HOST = os.getenv("ALIGN_SERVE_HOST", "127.0.0.1")
PORT = int(os.getenv("ALIGN_SERVE_PORT", "8100"))


# ---- 会话存储：episode_id -> 一个 env 实例（每集一份状态）----
class SessionStore:
    def __init__(self, trace_path: Path = DEFAULT_TRACE):
        backends = build_all(load_models())
        self.sink = FileTraceSink(trace_path)
        self.backends = backends
        self._envs: dict[str, AlignmentEnvironment] = {}
        self._lock = threading.Lock()

    def new_env(self, scenario: str | None = None, max_turns: int = 10) -> tuple[str, Any]:
        env = AlignmentEnvironment(
            guard=self.backends.guard, target=self.backends.target,
            max_turns=max_turns, trace_sink=self.sink,
        )
        obs = env.reset(scenario=scenario)
        with self._lock:
            self._envs[obs.episode_id] = env
        return obs.episode_id, obs

    def env(self, episode_id: str) -> AlignmentEnvironment:
        with self._lock:
            env = self._envs.get(episode_id)
        if env is None:
            raise HTTPException(404, f"episode 不存在: {episode_id}")
        return env


STORE = SessionStore()
app = FastAPI(title="alignment-env · red-blue serve", version="0.1.0")


# ---- API 模型 ----
class ResetReq(BaseModel):
    scenario: str | None = None
    max_turns: int = 10


class StepReq(BaseModel):
    episode_id: str
    message: str


@app.get("/health")
def health() -> dict:
    return {"ok": True, "backend": STORE.backends.names}


@app.post("/reset")
def reset(req: ResetReq) -> dict:
    eid, obs = STORE.new_env(scenario=req.scenario, max_turns=req.max_turns)
    return {"episode_id": eid, "observation": obs.model_dump()}


@app.post("/step")
def step(req: StepReq) -> dict:
    env = STORE.env(req.episode_id)
    obs = env.step(AttackAction(message=req.message))
    return {"episode_id": req.episode_id, "observation": obs.model_dump()}


@app.get("/episode/{episode_id}")
def episode(episode_id: str) -> dict:
    env = STORE.env(episode_id)
    return {"episode_id": episode_id, "history": list(env.history),
            "turn": len(env.history) // 2, "scenario": env.scenario.instruction,
            "done": bool(env.history)}


@app.get("/metrics")
def metrics() -> dict:
    recs = read_traces(STORE.sink.path)
    return {"records": len(recs), "aggregate": aggregate(recs)}


def main() -> None:
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()