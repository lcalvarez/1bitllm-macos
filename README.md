# MLX BitNet FastAPI

FastAPI service that proxies requests to Docker Model Runner for `[mlx-community/bitnet-b1.58-2B-4T](https://huggingface.co/mlx-community/bitnet-b1.58-2B-4T)` on Apple Silicon.

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
just generate "hello"
```

```bash
just stream "hello"
```

```bash
just generate "Answer in one sentence: what is FastAPI?"
```

```bash
just generate "hello" 32 0.1 0.95 "Response:"
```

```bash
just stream "Write a haiku about Apple Silicon" 48 0.7
```
