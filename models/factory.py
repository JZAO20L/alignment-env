# SPDX-License-Identifier: BSD-3-Clause
"""三角色 provider 装配：config -> {role: ModelProvider}。"""

from __future__ import annotations

from .config import AlignmentModels, Role
from .provider import ModelProvider, build_provider


def build_all(
    models: AlignmentModels,
    *,
    backend: str | None = None,
    base_urls: dict[Role, str] | None = None,
) -> dict[Role, ModelProvider]:
    """按角色为三角色各构造一个 provider。

    默认全部 mock（便于部署/测试）；要连真实模型时，用环境变量或显式参数指定 openai 后端与 base_url。
    例如: ALIGN_GUARD_BACKEND=openai ALIGN_GUARD_BASE_URL=http://127.0.0.1:8001 ...
    """
    base_urls = base_urls or {}
    providers: dict[Role, ModelProvider] = {}
    for role in models.all_roles():
        spec = models.spec(role)
        providers[role] = build_provider(
            role,
            backend=backend,
            base_url=base_urls.get(role),
            model=spec.model,
        )
    return providers