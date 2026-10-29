# SPDX-License-Identifier: BSD-3-Clause
"""ModelScope 自动下载：断点续传 + 完成判定。

判定"已下载"沿用 jailbreak 约定：config.json 存在 且 无 *.incomplete 分片。
modelscope 在下载中会周期落 .incomplete，只看 config.json 会挑中半成品。
"""

from __future__ import annotations

from pathlib import Path

from .config import AlignmentModels, ModelSpec, default_cache_dir


def is_downloaded(local_dir: Path) -> bool:
    if not Path(local_dir).is_dir():
        return False
    if not (Path(local_dir) / "config.json").is_file():
        return False
    if list(Path(local_dir).glob("*.incomplete")):
        return False
    return True


def local_dir_for(spec: ModelSpec, cache_dir: Path | None = None) -> Path:
    """一个 model id 的本地目录：<cache>/<repo 的末段>（如 Qwen3Guard-Gen-4B）。"""
    cache_dir = cache_dir or default_cache_dir()
    return cache_dir / Path(spec.model).name


def download_model(
    spec: ModelSpec,
    cache_dir: Path | None = None,
    backend: str = "modelscope",
) -> Path:
    """下载单个模型到缓存，返回本地目录。已存在且完整则跳过。"""
    cache_dir = cache_dir or default_cache_dir()
    dest = local_dir_for(spec, cache_dir)
    if is_downloaded(dest):
        return dest

    if backend != "modelscope":
        raise NotImplementedError(f"仅支持 modelscope 后端，got {backend!r}（HF 镜像待接）")

    # 延迟导入：不装 modelscope 也能用 status/show/mock
    try:
        from modelscope import snapshot_download
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "未安装 modelscope，先 `uv pip install modelscope`"
        ) from e

    cache_dir.mkdir(parents=True, exist_ok=True)
    # 断点续传：modelscope snapshot_download 的续传参数因版本而异
    # （新版无 resume_download，改按缺省行为 + 本轮 is_downloaded 判定）
    kwargs: dict = {"local_dir": str(dest)}
    try:
        snapshot_download(spec.model, **kwargs)
    except TypeError:
        import inspect
        sig = inspect.signature(snapshot_download)
        if any("resume_download" in p for p in sig.parameters):
            kwargs["resume_download"] = True
            snapshot_download(spec.model, **kwargs)
        else:
            raise
    if not is_downloaded(dest):
        raise RuntimeError(f"下载后校验未过：{dest}")
    return dest


def ensure_models(models: AlignmentModels, cache_dir: Path | None = None) -> dict[str, Path]:
    """下载全部角色模型，返回 {role: local_dir}。已存在者跳过。"""
    out: dict[str, Path] = {}
    for role in models.all_roles():
        spec = models.spec(role)
        out[role] = download_model(spec, cache_dir=cache_dir)
    return out


def status(models: AlignmentModels, cache_dir: Path | None = None) -> list[dict]:
    """返回每个角色的状态（不下载），供 CLI `models status` 使用。"""
    cache_dir = cache_dir or default_cache_dir()
    rows: list[dict] = []
    for role in models.all_roles():
        spec = models.spec(role)
        dest = local_dir_for(spec, cache_dir)
        rows.append({
            "role": role,
            "model": spec.model,
            "trainable": spec.trainable,
            "status": "downloaded" if is_downloaded(dest) else "missing",
            "local_dir": str(dest),
        })
    return rows