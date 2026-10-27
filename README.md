# alignment-env

An OpenEnv-based model-alignment attack–defense training environment.

Red vs blue: an attacker (`red`) sends prompts against a victim model (`target`),
a frozen guard model (`reward`) judges each response, and the environment hands
back per-step reward and termination — wrapped in a standard
[OpenEnv](https://huggingface.co/docs/openenv/index) (Gymnasium-style) API, plus a
CLI + Gradio control plane for `launch` / `train` / `monitor`.

## Why

Jailbreak / alignment training is normally buried inside bespoke scripts. This
project packages it as a deployable RL environment with a stable interface:

- **Standard env contract** — `reset()` / `step()` / `observation` carry
  `done` + `reward`; any trainer (TRL, Unsloth, SkyRL, …) can consume it.
- **Reward from a guard model** — the judge is frozen and injectable.
- **Red-team automation first** — v0.1 auto-evolves a prompt library and watches
  attack success rise; RL attaches later as an optional plugin.
- **Runs with zero GPU** — mock target/guard let the whole thing demo on CPU.

## Goals (one-liner)

A deployable, observable, self-evolving attack–defense alignment env:
thesis engineering deliverable and a public portfolio artifact.

## Quickstart

```bash
git clone git@github.com:JZAO20L/alignment-env.git
cd alignment-env
uv venv .venv && source .venv/bin/activate
uv pip install --index-url https://pypi.org/simple openenv

cd envs/red_blue_env
# NOTE: unset proxy vars before importing gradio/openenv on a corporate net
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    -u all_proxy -u ws_proxy -u WS_PROXY -u no_proxy -u NO_PROXY \
    .venv_bin_python -m server.app --port 8090     # serve the sample env
# in another shell
cd envs
.venv_bin_python - <<'PY'
from red_blue_env import RedBlueAction, RedBlueEnv
with RedBlueEnv(base_url="http://localhost:8090").sync() as c:
    print(c.reset().observation)
    r = c.step(RedBlueAction(message="hello"))
    print(r.observation, r.reward, r.done)
PY
```

## Layout

```
envs/red_blue_env/   the OpenEnv environment (self-contained, deployable package)
docs/v0.1/           DESIGN / TODO / COOKBOOK / REPORT for the current version
```

## Docs

- Working docs are under `docs/` (Chinese). Root README is the public entry.
- Doc system norm: see [docs/README.md](docs/README.md) (mirrors evolving-harness).

## Status

M1 in progress — OpenEnv scaffolding wired, `reset/step/state` round-trip proven.
See [docs/v0.1/README.md](docs/v0.1/README.md).