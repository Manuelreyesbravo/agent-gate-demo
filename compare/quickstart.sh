#!/usr/bin/env bash
# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
#
# One command: the same gate with and without MCP, from PUBLISHED pieces only -- nothing to
# compile. PostgreSQL with pg_agent_gate comes from the ygg-pg image, the model from a public
# GGUF checked by sha256, the model server from llama.cpp's own image, gated-mcp from the
# pg_agent_gate tag, and the stock baseline from crystaldba/postgres-mcp, every one pinned.
#
#   compare/quickstart.sh                    # CPU, 1 run per task; writes compare-results.json
#   REPEAT=3 compare/quickstart.sh           # 3 runs per task
#   LLAMA_URL=http://127.0.0.1:8080 compare/quickstart.sh   # use a model server you already run
#   compare/quickstart.sh --byo "https://your-mcp/mcp"        # add your own MCP server as an arm
#
# Needs: podman or docker, git, curl, bun, and uv (or python3 with psycopg 3). About 6 GB of
# disk for the model. Everything runs on 127.0.0.1 and is removed when the script ends.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
CT=${CONTAINER:-$(command -v podman || command -v docker || true)}
[ -n "$CT" ] || { echo "need podman or docker"; exit 1; }
for tool in git curl bun; do
    command -v "$tool" >/dev/null || { echo "need $tool"; exit 1; }
done

YGG_IMAGE=${YGG_IMAGE:-ghcr.io/latamflows/ygg-pg@sha256:e9265995356e990ff8b0161a8b1aebfa83c6a4b383885f6ee4b8d7fbdc90e0e1}  # 0.3.4: pg_agent_gate 0.4.1
LLAMA_IMAGE=ghcr.io/ggml-org/llama.cpp@sha256:20c4196fc08b459a34ef78aaa05b101333b2fac687e30ec99f37b3c9dc071b44  # server-b11854
MODEL_URL="https://huggingface.co/unsloth/Qwen3-8B-GGUF/resolve/a6adef130ffb23ddaf1a62fec9dced968c9bc482/Qwen3-8B-Q4_K_M.gguf"
MODEL_SHA256=120307ba529eb2439d6c430d94104dabd578497bc7bfe7e322b5d9933b449bd4
GATE_TAG=${GATE_TAG:-v0.4.1}
WORK=${WORK:-$HOME/.cache/gate-compare}
PG_PORT=${PG_PORT:-55499}
LLAMA_PORT=${LLAMA_PORT:-58099}
PG_NAME=gate-compare-pg
LLAMA_NAME=gate-compare-llm
PW=$(head -c 18 /dev/urandom | od -An -tx1 | tr -d ' \n')

mkdir -p "$WORK"
cleanup() { "$CT" rm -f "$PG_NAME" "$LLAMA_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

echo "== the model (Qwen3-8B Q4, no fine-tuning), checked by sha256"
MODEL=${MODEL_PATH:-$WORK/Qwen3-8B-Q4_K_M.gguf}
if [ -z "${LLAMA_URL:-}" ]; then
    [ -f "$MODEL" ] || curl -fL --progress-bar -o "$MODEL" "$MODEL_URL"
    echo "$MODEL_SHA256  $MODEL" | sha256sum -c - >/dev/null || { echo "model sha256 mismatch: $MODEL"; exit 1; }
fi

echo "== gated-mcp from pg_agent_gate $GATE_TAG"
if [ ! -d "$WORK/pg_agent_gate-$GATE_TAG" ]; then
    git -c advice.detachedHead=false clone -q --depth 1 --branch "$GATE_TAG" \
        https://github.com/Manuelreyesbravo/pg_agent_gate \
        "$WORK/pg_agent_gate-$GATE_TAG"
fi
(cd "$WORK/pg_agent_gate-$GATE_TAG/gated-mcp" && bun install --frozen-lockfile >/dev/null)

echo "== PostgreSQL + pg_agent_gate: $YGG_IMAGE"
"$CT" run -d --name "$PG_NAME" -p "127.0.0.1:$PG_PORT:5432" -e POSTGRES_PASSWORD="$PW" "$YGG_IMAGE" >/dev/null
for _ in $(seq 1 90); do
    "$CT" exec "$PG_NAME" pg_isready -q -U postgres >/dev/null 2>&1 && break
    sleep 1
done
"$CT" exec "$PG_NAME" psql -q -U postgres -c "create database gate_demo" >/dev/null

if [ -z "${LLAMA_URL:-}" ]; then
    echo "== the model server (llama.cpp, CPU, tool calls on)"
    "$CT" run -d --name "$LLAMA_NAME" -p "127.0.0.1:$LLAMA_PORT:8080" \
        -v "$(dirname "$MODEL"):/models:ro,Z" "$LLAMA_IMAGE" \
        -m "/models/$(basename "$MODEL")" -c 4096 --jinja -t "$(nproc)" \
        --host 0.0.0.0 --port 8080 >/dev/null
    LLAMA_URL=http://127.0.0.1:$LLAMA_PORT
    for _ in $(seq 1 180); do
        curl -s "$LLAMA_URL/health" | grep -q '"ok"' && break
        sleep 2
    done
    curl -s "$LLAMA_URL/health" | grep -q '"ok"' || { echo "the model server did not come up"; exit 1; }
fi

echo "== compare: the model, the tasks and the oracle fixed; only the connection varies"
ARGS=(--dsn "postgresql://postgres:$PW@127.0.0.1:$PG_PORT/gate_demo"
      --llama-url "$LLAMA_URL" --lora-off "${LORA_OFF:-0}"
      --gated-mcp-dir "$WORK/pg_agent_gate-$GATE_TAG/gated-mcp"
      --container "$(basename "$CT")" --repeat "${REPEAT:-1}"
      --json "${OUT:-compare-results.json}")
if command -v uv >/dev/null; then
    uv run -q --python 3.12 --with 'psycopg[binary]' "$HERE/run_compare.py" "${ARGS[@]}" "$@"
else
    python3 "$HERE/run_compare.py" "${ARGS[@]}" "$@"
fi
