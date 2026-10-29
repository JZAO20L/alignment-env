# SPDX-License-Identifier: BSD-3-Clause
"""模型装配：config -> {guard: Verifier, attack/defense: LLMBackend}。

按用户定稿的两接口族：
  guard   -> Verifier   （判罚/reward 主力，固定、单一后端）
  attack  -> LLMBackend （red/policy，攻击生成，已套重试/预算）
  defense -> LLMBackend （target/blue 受害者，可训练，已套重试/预算）
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import AlignmentModels, Role
from .provider import (
    Budget,
    LLMBackend,
    Verifier,
    build_llm_backend,
    build_provider,
    build_verifier,
)


@dataclass
class RuntimeBackends:
    """env 需要的装配结果（比 dict 更类型安全，自带访问命名）。"""

    guard: Verifier                       # 判罚/reward 来源
    target: LLMBackend                    # 受害者（blue）
    policy: LLMBackend                    # 攻击方（red）
    budget: Budget | None = None          # 本轮 episode 的预算（中间件计数）

    @property
    def names(self) -> dict[str, str]:
        return {"guard": str(self.guard), "target": str(self.target), "policy": str(self.policy)}


def build_all(
    models: AlignmentModels,
    *,
    backend: str | None = None,
    base_urls: dict[str, str] | None = None,
    budget: Budget | None = None,
) -> RuntimeBackends:
    """按角色装配两个接口族。

    默认全部 mock（离线干跑）；连真实模型用环境变量：
      ALIGN_GUARD_BACKEND=openai ALIGN_GUARD_BASE_URL=http://127.0.0.1:8001
      ALIGN_DEFENSE_BACKEND=openai ALIGN_DEFENSE_BASE_URL=... ALIGN_DEFENSE_MODEL=Qwen3-4B
      ALIGN_ATTACK_BACKEND=openai ALIGN_ATTACK_BASE_URL=...
    """
    base_urls = base_urls or {}
    spec = {r: models.spec(r) for r in models.all_roles()}

    # defense=受害者(target) 是 trainable 角色；attack=攻击方(red)。
    target = build_llm_backend(
        "defense", backend=backend, base_url=base_urls.get("defense"), model=spec["defense"].model,
        budget=budget,
    )
    policy = build_llm_backend(
        "attack", backend=backend, base_url=base_urls.get("attack"), model=spec["attack"].model,
        budget=budget,
    )
    guard = build_verifier(
        "guard", backend=backend, base_url=base_urls.get("guard"), model=spec["guard"].model,
    )
    return RuntimeBackends(guard=guard, target=target, policy=policy, budget=budget)


__all__ = ["RuntimeBackends", "build_all", "build_provider", "Budget", "LLMBackend", "Verifier"]