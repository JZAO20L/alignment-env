# models — 模型层

> 三角色模型的配置、下载与 provider。供 env（target/guard 后端）与训练（defense）共用。

## 文件

- `config.py` — `AlignmentModels`/`ModelSpec`；guard/attack/defense 三角色，defense 唯一 `trainable`。
- `download.py` — ModelScope 下载，断点续传 + `config.json`/`.incomplete` 完成判定。
- `provider.py` — `ModelProvider` 接口；`Mock` / `OpenAICompatible`(vLLM) 两后端。
- `factory.py` — `build_all(config)` 装配三角色 provider。
- `models.yaml.example` — 配置模板（复制为 `models.yaml`，尤其是改 defense）。

## 配置与覆盖

默认（不填 `models.yaml`）：
- guard   = `Qwen/Qwen3Guard-Gen-4B`（冻结）
- attack  = `Qwen/Qwen3-4B`（冻结）
- defense = `Qwen/Qwen3-4B`（trainable，用户可改）

覆盖优先级：环境变量 > `models.yaml` > 默认。
- 模型 id：`ALIGN_<GUARD|ATTACK|DEFENSE>_MODEL`
- 缓存目录：`ALIGN_MODEL_DIR`（默认 `~/.cache/alignment-env/models`；byted 可指向现有 `/mnt/.../models`）

## 使用

```bash
alignment-env models init          # 写默认 models.yaml
alignment-env models show          # 看三角色配置
alignment-env models prepare       # ModelScope 下载全部（已存在跳过）
alignment-env models status        # 看是否已下载
```

provider（env 消费）：

```bash
# 默认全部 mock（离线可跑）；要连真模型：
ALIGN_GUARD_BACKEND=openai ALIGN_GUARD_BASE_URL=http://127.0.0.1:8001 \
ALIGN_DEFENSE_BACKEND=openai ALIGN_DEFENSE_BASE_URL=http://127.0.0.1:8002 \
  python -c "from models.factory import build_all; from models.config import load_models; \
             p=build_all(load_models()); print(g := p['guard'].generate([{'role':'user','content':'hi'}]))"
```

依赖方向：`models` 被 `envs/red_blue_env`（生成/服务）与后续 `rl`（defense 训练）依赖。