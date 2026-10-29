# SPDX-License-Identifier: BSD-3-Clause

"""Red Blue Env：transport-free 攻防环境核心 + 可选 OpenEnv 适配。

- core 是纯对象（reset/step，无传输耦合），CLI/Gradio/FastAPI/MCP 四壳直接 import。
- OpenEnv 客户端/播放器（client/models）依赖 openenv，缺依赖时仅 core 可用。
"""

from .core import AlignmentEnvironment, AttackAction, AttackObservation, Scenario

try:  # openenv 可选：缺依赖时 transport-free 部分仍可用
    from .client import RedBlueEnv
    from .models import RedBlueAction, RedBlueObservation
except Exception:  # noqa: BLE001 —— openenv 未装/代理崩时降级为 None
    RedBlueEnv = None  # type: ignore
    RedBlueAction = RedBlueObservation = None  # type: ignore

__all__ = [
    "AlignmentEnvironment",
    "AttackAction",
    "AttackObservation",
    "Scenario",
    "RedBlueEnv",
    "RedBlueAction",
    "RedBlueObservation",
]