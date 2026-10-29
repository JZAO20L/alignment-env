# SPDX-License-Identifier: BSD-3-Clause
"""模型层配置：guard / attack / defense（两接口族映射）。

两接口族（用户 2026-10-28 定稿）：
  guard   -> Verifier   （判罚/reward，固定、单一后端）
  attack  -> LLMBackend （red/policy 攻击方，可插拔多后端）
  defense -> LLMBackend （target/blue 受害者，唯一 trainable，v0.2 训练对象）
Role 枚举保留 guard/attack/defense 以兼容 models.yaml 与 CLI；装配时在 factory 映射为两族。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

Role = Literal["guard", "attack", "defense"]

# 默认 ModelScope repo id（与 jailbreak 一致：guard 用 Qwen3Guard，defense 用 Qwen3-4B）
DEFAULT_SPECS: dict[Role, dict] = {
    "guard":   {"model": "Qwen/Qwen3Guard-Gen-4B", "trainable": False,
                "description": "Verifier：判罚/reward 来源，冻结，固定后端"},
    "attack":  {"model": "Qwen/Qwen3-4B",          "trainable": False,
                "description": "LLMBackend(red/policy)：攻击生成，可插拔多后端"},
    "defense": {"model": "Qwen/Qwen3-4B",          "trainable": True,
                "description": "LLMBackend(target/blue)：受害者，待训练，用户可改"},
}

# 环境变量覆盖：ALIGN_<ROLE>_MODEL
_ENV_OVERRIDE: dict[Role, str] = {
    "guard": "ALIGN_GUARD_MODEL",
    "attack": "ALIGN_ATTACK_MODEL",
    "defense": "ALIGN_DEFENSE_MODEL",
}


def default_cache_dir() -> Path:
    """模型默认缓存：~/.cache/alignment-env/models，可用 ALIGN_MODEL_DIR 覆盖。

    byted 机器可指向已有 /mnt 模型：export ALIGN_MODEL_DIR=/mnt/bn/.../models
    """
    return Path(os.getenv("ALIGN_MODEL_DIR", Path.home() / ".cache" / "alignment-env" / "models"))


class ModelSpec(BaseModel):
    model: str = Field(..., description="ModelScope repo id（或 HF 名）")
    trainable: bool = Field(False, description="是否为待训练角色")
    description: str = ""


class AlignmentModels(BaseModel):
    """三角色模型配置。不填时用默认 spec；用户可在 models.yaml 覆盖任意角色。"""

    guard: ModelSpec = Field(default_factory=lambda: ModelSpec(**DEFAULT_SPECS["guard"]))
    attack: ModelSpec = Field(default_factory=lambda: ModelSpec(**DEFAULT_SPECS["attack"]))
    defense: ModelSpec = Field(default_factory=lambda: ModelSpec(**DEFAULT_SPECS["defense"]))

    # 便于调用方直接构造全默认
    @classmethod
    def defaults(cls) -> "AlignmentModels":
        return cls()

    def spec(self, role: Role) -> ModelSpec:
        return getattr(self, role)

    def all_roles(self) -> list[Role]:
        return ["guard", "attack", "defense"]

    def trainable_roles(self) -> list[Role]:
        return [r for r in self.all_roles() if self.spec(r).trainable]

    # ---- 持久化与覆盖 ----
    @classmethod
    def load(cls, path: Path | None = None, apply_env: bool = True) -> "AlignmentModels":
        """从 models.yaml 加载；缺失该文件时用默认。随后可选地应用环境变量覆盖。"""
        data: dict = {}
        if path is not None and Path(path).is_file():
            data = yaml.safe_load(Path(path).read_text()) or {}
        for role, spec_data in list(DEFAULT_SPECS.items()):
            data.setdefault(role, {})
            for k, v in spec_data.items():
                data[role].setdefault(k, v)
        if apply_env:
            for role, var in _ENV_OVERRIDE.items():
                if os.getenv(var):
                    data[role]["model"] = os.getenv(var)
        return cls(**{role: data[role] for role in data if role in DEFAULT_SPECS})

    def dump_yaml(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        out = {r: self.spec(r).model_dump() for r in self.all_roles()}
        path.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True), encoding="utf-8")


@lru_cache(maxsize=1)
def load_models(config_file: Path | None = None) -> AlignmentModels:
    return AlignmentModels.load(config_file)