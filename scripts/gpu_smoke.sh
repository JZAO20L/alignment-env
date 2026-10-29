#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# GPU 冒烟编排：自拉起 3 个 vLLM（guard/target/policy）→ 跑 cli test all --real → 回收。
#
# 用法：
#   bash scripts/gpu_smoke.sh            # 跑真模型冒烟，结束后 KILL 服务
#   bash scripts/gpu_smoke.sh --keep     # 跑完保活 vLLM，便于回看（打印端口）
#   ALIGN_MODEL_DIR=/mnt/... bash scripts/gpu_smoke.sh   # 指向已下载模型
#
# 环境覆盖（默认见下）：ALIGN_GUARD_MODEL / ALIGN_DEFENSE_MODEL / ALIGN_ATTACK_MODEL
#   GPU_SMOKE_GUARD_PORT / _TARGET_PORT / _POLICY_PORT（默认 8000/8001/8002）
#   GPU_SMOKE_MAX_LEN（默认 2048，防显存爆）
#   GPU_SMOKE_LOG_DIR（默认 output/gpu_smoke）
# 若模型在本地 /mnt 而非 HF：把 ALIGN_*_MODEL 指到你下载好的本地目录即可
#   （vLLM 可直接 serve 本地 HF 目录路径），如：
#   ALIGN_GUARD_MODEL=/mnt/bn/.../Qwen3Guard-Gen-4B bash scripts/gpu_smoke.sh

set -u
KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1

# ---- 代理地雷：全清，防 gradio/httpx import 崩 ----
E(){
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
      -u no_proxy -u NO_PROXY -u all_proxy -u ALL_PROXY "$@"
}

# ---- 模型默认 spec（与 models/config.py 一致，可用 env 覆盖）----
GUARD_MODEL="${ALIGN_GUARD_MODEL:-Qwen/Qwen3Guard-Gen-4B}"
TARGET_MODEL="${ALIGN_DEFENSE_MODEL:-Qwen/Qwen3-4B}"
POLICY_MODEL="${ALIGN_ATTACK_MODEL:-Qwen/Qwen3-4B}"
GP=${GPU_SMOKE_GUARD_PORT:-8000}
TP=${GPU_SMOKE_TARGET_PORT:-8001}
PP=${GPU_SMOKE_POLICY_PORT:-8002}
MAXLEN=${GPU_SMOKE_MAX_LEN:-2048}
LOGDIR="${GPU_SMOKE_LOG_DIR:-output/gpu_smoke}"
mkdir -p "$LOGDIR"

GREEN='\033[32m'; RED='\033[31m'; NC='\033[0m'
PASS=0; FAIL=0
note(){ # note <name> <ok> [detail]
  local ok=$2
  if [[ $ok == 1 ]]; then printf "  [${GREEN}PASS${NC}] %s\n" "$1"; PASS=$((PASS+1))
  else printf "  [${RED}FAIL${NC}] %s — %s\n" "$1" "${3:-}"; FAIL=$((FAIL+1)); fi
}

# 在退出/失败时必执行：回收拉起的所有 vLLM（除非 --keep）
PIDS=()
cleanup(){
  if [[ $KEEP == 1 ]]; then
    echo "[keep] 保活 vLLM: guard=$GP target=$TP policy=$PP (pids=${PIDS[*]:-无})"
    return
  fi
  for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null; done
  echo "[cleanup] 已 KILL ${#PIDS[@]} 个 vLLM"
}
trap cleanup EXIT

echo "== 1/6  GPU spot-check =="
if ! nvidia-smi -L >/dev/null 2>&1; then
  note "nvidia-smi GPU 存在" 0 "无 GPU 或需 mlx worker launch 登入 gpu 节点"
  echo "失败：本脚本设计为带 GPU 机器上跑真模型。无 GPU 请用: python -m cli.main test (mock)"
  exit 1
fi
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader || true
note "GPU 存在 (nvidia-smi)" 1

echo "== 2/6  models prepare =="
E python -m cli.main models prepare >"$LOGDIR/models.log" 2>&1 \
  && note "下载/定位模型" 1 "LOG=$LOGDIR/models.log" \
  || { note "models prepare" 0; exit 1; }

echo "== 3/6  拉起 vLLM (guard=$GP target=$TP policy=$PP maxlen=$MAXLEN) =="
serve(){ # serve <role> <model> <port> <pidfile>
  local role=$1 model=$2 port=$3 pf=$4
  nohup vllm serve "$model" \
        --port "$port" \
        --max-model-len "$MAXLEN" \
        --quantization none >"$LOGDIR/$role.vllm.log" 2>&1 &
  echo $! > "$pf"
  echo "  $role: vllm serve $model :$port (pid $(cat "$pf"))"
}
serve guard "$GUARD_MODEL" "$GP" "$LOGDIR/guard.pid"
serve target "$TARGET_MODEL" "$TP" "$LOGDIR/target.pid"
serve policy "$POLICY_MODEL" "$PP" "$LOGDIR/policy.pid"
PIDS=($(cat "$LOGDIR"/*.pid))

# 健康等待：vLLM 冷启动很慢，轮询 /v1/models 至 200
wait_health(){ # wait_health <port> <name> <timeout_s>
  local port=$1 name=$2 timeout_s=${3:-300} url="http://127.0.0.1:$port/v1/models"
  local i=0
  echo "  等待 $name 就绪 (: $port, 上限 ${timeout_s}s)"
  while (( i < timeout_s )); do
    if curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "$url" 2>/dev/null | grep -q 200; then
      note "$name /v1/models 200" 1; return 0
    fi
    # 探日志里是否已崩（显存OOM/依赖错/端口占用），早停省的等
    if grep -qiE 'out of memory|CUDA out of memory|Address already in use|Traceback|Error' \
           "$LOGDIR/$name.vllm.log" 2>/dev/null; then
      note "$name 启动异常" 0 "see $LOGDIR/$name.vllm.log"; return 1
    fi
    sleep 3; i=$((i+3))
  done
  note "$name 就绪超时(${timeout_s}s)" 0; return 1
}
ok_guard=0; ok_target=0; ok_policy=0
wait_health "$GP" guard && ok_guard=1
wait_health "$TP" target && ok_target=1
wait_health "$PP" policy && ok_policy=1
[[ $ok_guard == 1 && $ok_target == 1 && $ok_policy == 1 ]] || { echo "[早停] 有 vLLM 未就绪"; exit 1; }

echo "== 4/6  接线 =="
export ALIGN_GUARD_BACKEND=openai    ALIGN_GUARD_BASE_URL="http://127.0.0.1:$GP/v1"    ALIGN_GUARD_MODEL="$GUARD_MODEL"
export ALIGN_DEFENSE_BACKEND=openai  ALIGN_DEFENSE_BASE_URL="http://127.0.0.1:$TP/v1"  ALIGN_DEFENSE_MODEL="$TARGET_MODEL"
export ALIGN_ATTACK_BACKEND=openai   ALIGN_ATTACK_BASE_URL="http://127.0.0.1:$PP/v1"   ALIGN_ATTACK_MODEL="$POLICY_MODEL"
echo "  guard   -> $ALIGN_GUARD_BASE_URL ($ALIGN_GUARD_MODEL)"
echo "  target  -> $ALIGN_DEFENSE_BASE_URL ($ALIGN_DEFENSE_MODEL)"
echo "  policy  -> $ALIGN_ATTACK_BASE_URL ($ALIGN_ATTACK_MODEL)"

echo "== 5/6  跑 cli test all --real =="
E python -m cli.main test all --real >"$LOGDIR/test_all.log" 2>&1
TEST_EXIT=$?
cat "$LOGDIR/test_all.log" | grep -Ev '^\s*$' | grep -v 'mlx lab' | grep -v 'mlx worker' | grep -v 'mlx upgrade'
echo "  详见 $LOGDIR/test_all.log"

echo "== 6/6  汇总 =="
echo "  PASS=$PASS  FAIL=$FAIL  (vLLM: ${PIDS[*]})  test_all_exit=$TEST_EXIT"
[[ $FAIL == 0 && $TEST_EXIT == 0 ]] && { echo "SMOKE OK"; exit 0; }
echo "SMOKE FAILED"; exit 1