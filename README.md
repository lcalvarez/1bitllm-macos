# MLX BitNet FastAPI

FastAPI service that proxies requests to Docker Model Runner for `mlx-community/bitnet-b1.58-2B-4T` on Apple Silicon.

## Prerequisites

- Docker Desktop installed and running
- Docker Model Runner enabled in Docker Desktop
- - Need version 4.64.0
- `just` installed: https://github.com/casey/just
- - `brew install just`
- `jq` installed if you want readable JSON output from the helper commands
- - `brew install jq`
- `uv` installed if you want to run the app locally outside Docker
- - `brew install uv`

## Do you need `uv`?

- Yes, if you want to run `uv sync` or `just run-local`
- No, if you only plan to use `docker compose` and `just` commands for the containerized flow

## Setup

1. Enable Docker Model Runner:

   ```bash
   just enable-runner
   ```

2. Pull the model:

   ```bash
   just pull-model
   ```

3. Start the API:

   ```bash
   just up
   ```

## Health check

```bash
just health
```

## Example request

```bash
just generate hello
```

```bash
just stream hello
```

```bash
just generate "Answer in one sentence: what is FastAPI?"
```

```bash
just generate "hello" max_tokens=32 temperature=0.1 stop="Response:"
```

## Local development

If you want to run the FastAPI app directly on your machine instead of in Docker:

```bash
uv sync
just run-local
```
