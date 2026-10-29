# SPDX-License-Identifier: BSD-3-Clause
"""可观测地基：JSON-Lines trace 泵 + 聚合 reader（DESIGN_observability.md）。

四壳（CLI/Gradio/FastAPI/MCP）共用同一数据源：
- FileTraceSink: env reset/step emit 的 trace 落 JSON-Lines 文件。
- aggregate(): 按 episode/世代算 攻破率 / avg reward / avg_turns / latency p50、p90。
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

TraceRecord = dict


class FileTraceSink:
    """把 trace 记录 append 到 JSON-Lines 文件。线程安全（GIL + 单写）。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def __call__(self, record: dict) -> None:
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def read_traces(path: str | Path) -> list[TraceRecord]:
    """读取 JSON-Lines 全部记录（按写入顺序）。"""
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def aggregate(traces: list[TraceRecord]) -> dict:
    """算每 episode/足迹级指标：攻破率、avg reward、turns、latency p50/p90。"""
    eps: dict[str, dict] = {}
    for t in traces:
        eid = t.get("episode_id", "?")
        eps.setdefault(eid, {"turns": 0, "hit": False, "reward": float(t.get("reward", 0))})
        if t.get("type") == "step":
            eps[eid]["turns"] = max(eps[eid]["turns"], int(t.get("turn", 0)))
            eps[eid]["reward"] = float(t.get("reward", 0))
            if t.get("verdict") == "unsafe":
                eps[eid]["hit"] = True

    if not eps:
        return {"episodes": 0, "hit_rate": 0.0, "avg_reward": 0.0,
                "avg_turns": 0.0, "latency_p50": 0.0, "latency_p90": 0.0}

    hits = sum(1 for e in eps.values() if e["hit"])
    avg_reward = statistics.mean(e["reward"] for e in eps.values())
    avg_turns = statistics.mean(e["turns"] for e in eps.values())
    lats = [float(t.get("latency_s", 0)) for t in traces if "latency_s" in t]
    p50 = statistics.median(lats) if lats else 0.0
    p90 = (sorted(lats)[int(len(lats) * 0.9) - 1] if lats else 0.0)
    return {
        "episodes": len(eps),
        "hit_rate": hits / len(eps),
        "avg_reward": round(avg_reward, 4),
        "avg_turns": round(avg_turns, 2),
        "latency_p50": round(p50, 4),
        "latency_p90": round(p90, 4),
    }