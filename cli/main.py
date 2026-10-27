# SPDX-License-Identifier: BSD-3-Clause
"""alignment-env CLI：模型准备 + （后续）serve / redrun / ui / train。"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from models.config import AlignmentModels, default_cache_dir, load_models
from models.download import ensure_models, status

app = typer.Typer(help="alignment-env: OpenEnv 式红蓝攻防对齐环境 (launch / train / monitor)")
models_app = typer.Typer(help="模型准备：下载 / 状态 / 配置")
app.add_typer(models_app, name="models")

DEFAULT_CONFIG = Path(os.getenv("ALIGN_CONFIG", "models.yaml"))


def _models(*, config: Path | None) -> AlignmentModels:
    path = config or DEFAULT_CONFIG
    return load_models(path if path.is_file() else None)


@models_app.command("show")
def show(config: Path = typer.Option(None, "--config", help="models.yaml 路径")):
    """打印当前三角色模型配置（含 trainable 标志与环境覆盖）。"""
    m = _models(config=config)
    typer.echo("模型配置" + ("（含环境覆盖）" if os.getenv(_env_used(m)) else ""))
    for row in _rows(m):
        trainable = "◆ trainable" if row["trainable"] else "冻结"
        typer.echo(f"  {row['role']:<8} {row['model']:<28} {trainable}")
    typer.echo(f"缓存目录: {default_cache_dir()}")


@models_app.command("status")
def status_cmd(config: Path = typer.Option(None, "--config"), cache: Path = typer.Option(None, "--cache")):
    """显示各角色模型是否已下载（不下载）。"""
    m = _models(config=config)
    for row in status(m, cache_dir=cache):
        mark = "✅" if row["status"] == "downloaded" else "⬜ missing"
        typer.echo(f"  {mark} {row['role']:<8} {row['model']:<28} {row['local_dir']}")


@models_app.command("prepare")
def prepare(
    config: Path = typer.Option(None, "--config"),
    cache: Path = typer.Option(None, "--cache"),
    backend: str = typer.Option("modelscope", "--backend"),
):
    """按 modelscope 下载三角色全部模型；已存在则跳过（断点续传）。"""
    m = _models(config=config)
    dirs = ensure_models(m, cache_dir=cache)
    for role, d in dirs.items():
        typer.echo(f" ✓ {role:<8} -> {d}")


@models_app.command("init")
def init_config(path: Path = typer.Option(DEFAULT_CONFIG, "--path")):
    """写出默认 models.yaml（可再编辑，尤其 defense 改成你想训的模型）。"""
    AlignmentModels.defaults().dump_yaml(path)
    typer.echo(f"已写 {path}，可编辑后使用（--config {path}）")


def _rows(m: AlignmentModels) -> list[dict]:
    return [
        {"role": r, "model": m.spec(r).model, "trainable": m.spec(r).trainable}
        for r in m.all_roles()
    ]


def _env_used(m: AlignmentModels) -> str:
    return next((v for v in ("ALIGN_GUARD_MODEL", "ALIGN_ATTACK_MODEL", "ALIGN_DEFENSE_MODEL") if os.getenv(v)), "")


if __name__ == "__main__":
    app()