from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core import DockerModelRunnerClient, GenerateRequest, GenerateResponse, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    dmr_client = DockerModelRunnerClient(settings)
    await dmr_client.wait_until_ready()

    if settings.ensure_model_on_startup:
        await dmr_client.ensure_model()

    app.state.settings = settings
    app.state.dmr_client = dmr_client

    try:
        yield
    finally:
        await dmr_client.aclose()


app = FastAPI(
    title="MLX BitNet API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "service": "mlx-bitnet-api",
        "model": settings.model_name,
    }


@app.get("/health")
async def health(request: Request) -> dict[str, object]:
    dmr_client: DockerModelRunnerClient = request.app.state.dmr_client
    settings = request.app.state.settings

    try:
        models = await dmr_client.list_models()
        return {
            "status": "ok",
            "model": settings.model_name,
            "dmr_base_url": settings.normalized_dmr_base_url,
            "models": models,
        }
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Docker Model Runner is unavailable: {exc}",
        ) from exc


@app.post("/models/ensure")
async def ensure_model(request: Request) -> dict[str, object]:
    dmr_client: DockerModelRunnerClient = request.app.state.dmr_client

    try:
        payload = await dmr_client.ensure_model()
        return {"status": "ok", "result": payload}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or str(exc)
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest, request: Request) -> GenerateResponse:
    dmr_client: DockerModelRunnerClient = request.app.state.dmr_client

    try:
        return await dmr_client.generate(payload)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or str(exc)
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/generate/stream")
async def generate_stream(payload: GenerateRequest, request: Request) -> StreamingResponse:
    dmr_client: DockerModelRunnerClient = request.app.state.dmr_client
    return StreamingResponse(
        dmr_client.stream_generate(payload),
        media_type="text/event-stream",
    )
