set shell := ["bash", "-cu"]

model_name := "hf.co/mlx-community/bitnet-b1.58-2B-4T"

default:
    @just --list

versions:
    @echo "Docker Desktop: $(docker --version)"
    @echo "Docker Model Runner:"
    @docker model version
    @echo "Just: $(just --version)"
    @echo "UV: $(uv --version)"
    @echo "JQ: $(jq --version)"

sync:
    uv sync

build:
    docker compose build

up:
    docker compose up --build

up-d:
    docker compose up --build -d

down:
    docker compose down

restart:
    docker compose down
    docker compose up --build -d

logs:
    docker compose logs -f api

ps:
    docker compose ps

install-runner:
    docker model install-runner --backend vllm-metal

enable-runner:
    docker desktop enable model-runner --tcp=12434

pull-model:
    docker model pull {{model_name}}

health:
    curl -s http://localhost:8000/health | jq .

ensure-model:
    curl -s -X POST http://localhost:8000/models/ensure | jq .

validate:
    bash scripts/validate_model.sh

generate prompt="hello" max_tokens="64" temperature="0.2" top_p="0.95" stop="<|im_sep|>":
    payload=$(jq -nc \
      --arg prompt '{{prompt}}' \
      --arg stop '{{stop}}' \
      --argjson max_tokens {{max_tokens}} \
      --argjson temperature {{temperature}} \
      --argjson top_p {{top_p}} \
      '{prompt: $prompt, max_tokens: $max_tokens, temperature: $temperature, top_p: $top_p} + (if $stop == "" then {} else {stop: [$stop]} end)'); \
    curl -s http://localhost:8000/generate \
      -H 'Content-Type: application/json' \
      -d "$payload" | jq .

stream prompt="hello" max_tokens="64" temperature="0.2" top_p="0.95" stop="<|im_sep|>":
    payload=$(jq -nc \
      --arg prompt '{{prompt}}' \
      --arg stop '{{stop}}' \
      --argjson max_tokens {{max_tokens}} \
      --argjson temperature {{temperature}} \
      --argjson top_p {{top_p}} \
      '{prompt: $prompt, max_tokens: $max_tokens, temperature: $temperature, top_p: $top_p} + (if $stop == "" then {} else {stop: [$stop]} end)'); \
    curl -N -s http://localhost:8000/generate/stream \
      -H 'Content-Type: application/json' \
      -d "$payload"
