# SPDX-License-Identifier: BSD-3-Clause
"""ModelProvider：三角色模型的可生成接口。

v0.1 两个后端：
- MockProvider            —— 离线可跑，便于部署/测试（返回固定文本）。
- OpenAICompatibleProvider—— 指向 vLLM 等 OpenAI 兼容 endpoint（base_url+model）。

管理式 vLLM 启动不在本 slice：攻击方法(T1.2)+训练(T1.2+)阶段再消费 provider。
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class ModelProvider(ABC):
    """统一的生成接口。messages: list[{role,content}]。返回助手文本。"""

    name: str = "abstract"

    @abstractmethod
    def generate(self, messages: list[dict], *, max_tokens: int = 512, **kw) -> str:
        ...

    def __str__(self) -> str:  # pragma: no cover - debug 用
        return self.name


class MockProvider(ModelProvider):
    """返回固定文本；用于无 GPU 干跑与单元测试。"""

    name = "mock"

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def generate(self, messages: list[dict], *, max_tokens: int = 512, **kw) -> str:
        last = messages[-1]["content"] if messages else ""
        return f"{self.prefix}mock[{last[:24]}]"


class OpenAICompatibleProvider(ModelProvider):
    """指向任意 OpenAI 兼容 endpoint（vLLM / deepseek / qwen…）。"""

    name = "openai"

    def __init__(self, base_url: str, model: str, api_key: str = "EMPTY", **client_kw):
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("未安装 openai，先 `uv pip install openai`") from e
        self._client = OpenAI(base_url=base_url, api_key=api_key, **client_kw)
        self._model = model
        self.name = f"openai://{model}@{base_url}"

    def generate(self, messages: list[dict], *, max_tokens: int = 512, **kw) -> str:
        resp = self._client.chat.completions.create(
            model=self._model, messages=messages, max_tokens=max_tokens, **kw
        )
        return resp.choices[0].message.content or ""


def build_provider(
    role: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    backend: str | None = None,
) -> ModelProvider:
    """按角色构造 provider。

    backend / base_url 缺省时从环境变量读（便于挂到已有 vLLM）：
      ALIGN_<ROLE>_BACKEND=mock|openai    ALIGN_<ROLE>_BASE_URL=http://127.0.0.1:8001
    显式传入优先于环境变量。
    """
    env_prefix = f"ALIGN_{role.upper()}"
    backend = backend or os.getenv(f"{env_prefix}_BACKEND", "mock")
    base_url = base_url or os.getenv(f"{env_prefix}_BASE_URL")
    model = model or os.getenv(f"{env_prefix}_MODEL")

    if backend == "mock":
        return MockProvider(prefix=f"[{role}] ")
    if backend == "openai":
        if not base_url or not model:
            raise ValueError(f"{role}: openai 后端需要 base_url + model（env: {env_prefix}_BASE_URL/_MODEL）")
        return OpenAICompatibleProvider(base_url=base_url, model=model)
    raise ValueError(f"未知 backend: {backend!r}（mock|openai）")