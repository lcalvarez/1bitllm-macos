from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from time import perf_counter
from typing import Any, AsyncIterator, Literal

import httpx
from pydantic import AliasChoices, BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("APP_HOST"))
    app_port: int = Field(default=8000, validation_alias=AliasChoices("APP_PORT"))
    dmr_base_url: str = Field(
        default="http://model-runner.docker.internal:12434",
        validation_alias=AliasChoices("DMR_BASE_URL"),
    )
    model_name: str = Field(
        default="hf.co/mlx-community/bitnet-b1.58-2B-4T",
        validation_alias=AliasChoices("MODEL_NAME", "AI_MODEL_NAME"),
    )
    ensure_model_on_startup: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENSURE_MODEL_ON_STARTUP"),
    )
    request_timeout_seconds: float = Field(
        default=900.0,
        validation_alias=AliasChoices("REQUEST_TIMEOUT_SECONDS"),
    )
    startup_wait_timeout_seconds: float = Field(
        default=180.0,
        validation_alias=AliasChoices("STARTUP_WAIT_TIMEOUT_SECONDS"),
    )
    startup_retry_interval_seconds: float = Field(
        default=2.0,
        validation_alias=AliasChoices("STARTUP_RETRY_INTERVAL_SECONDS"),
    )
    default_max_tokens: int = Field(
        default=256,
        validation_alias=AliasChoices("DEFAULT_MAX_TOKENS"),
    )
    default_temperature: float = Field(
        default=0.7,
        validation_alias=AliasChoices("DEFAULT_TEMPERATURE"),
    )
    default_top_p: float = Field(
        default=0.95,
        validation_alias=AliasChoices("DEFAULT_TOP_P"),
    )
    default_system_prompt: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DEFAULT_SYSTEM_PROMPT"),
    )

    @property
    def normalized_dmr_base_url(self) -> str:
        return self.dmr_base_url.rstrip("/")

    @property
    def models_url(self) -> str:
        return f"{self.normalized_dmr_base_url}/models"

    @property
    def create_model_url(self) -> str:
        return f"{self.models_url}/create"

    @property
    def chat_completions_url(self) -> str:
        return f"{self.normalized_dmr_base_url}/engines/v1/chat/completions"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class GenerateRequest(BaseModel):
    prompt: str | None = None
    messages: list[ChatMessage] | None = None
    system_prompt: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    stop: str | list[str] | None = None

    @model_validator(mode="after")
    def validate_input(self) -> "GenerateRequest":
        if not self.prompt and not self.messages:
            raise ValueError("Either `prompt` or `messages` must be provided.")
        return self

    def build_messages(self, default_system_prompt: str | None = None) -> list[dict[str, str]]:
        messages: list[ChatMessage] = []
        system_prompt = self.system_prompt if self.system_prompt is not None else default_system_prompt

        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))

        if self.messages:
            messages.extend(self.messages)
        elif self.prompt:
            messages.append(ChatMessage(role="user", content=self.prompt))

        return [message.model_dump() for message in messages]


class GenerateResponse(BaseModel):
    model: str
    content: str
    latency_ms: float
    usage: dict[str, Any] | None = None
    raw_response: dict[str, Any]


class DockerModelRunnerClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(settings.request_timeout_seconds))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def wait_until_ready(self) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.settings.startup_wait_timeout_seconds
        last_error: Exception | None = None

        while loop.time() < deadline:
            try:
                response = await self._client.get(self.settings.models_url)
                response.raise_for_status()
                return
            except httpx.HTTPError as exc:
                last_error = exc
                await asyncio.sleep(self.settings.startup_retry_interval_seconds)

        raise RuntimeError("Docker Model Runner did not become ready before timeout.") from last_error

    async def list_models(self) -> Any:
        response = await self._client.get(self.settings.models_url)
        response.raise_for_status()
        return self._parse_json(response)

    async def ensure_model(self) -> Any:
        response = await self._client.post(
            self.settings.create_model_url,
            json={"from": self.settings.model_name},
        )
        response.raise_for_status()
        return self._parse_json(response)

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        payload = self._build_payload(request)
        started_at = perf_counter()
        response = await self._client.post(self.settings.chat_completions_url, json=payload)
        response.raise_for_status()
        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        raw_response = self._parse_json(response)
        content = self._extract_content(raw_response)

        return GenerateResponse(
            model=self.settings.model_name,
            content=content,
            latency_ms=latency_ms,
            usage=raw_response.get("usage"),
            raw_response=raw_response,
        )

    async def stream_generate(self, request: GenerateRequest) -> AsyncIterator[str]:
        payload = self._build_payload(request, stream=True)
        async with self._client.stream("POST", self.settings.chat_completions_url, json=payload) as response:
            response.raise_for_status()
            async for chunk in response.aiter_text():
                if chunk:
                    yield chunk

    def _build_payload(self, request: GenerateRequest, *, stream: bool = False) -> dict[str, Any]:
        payload = {
            "model": self.settings.model_name,
            "messages": request.build_messages(self.settings.default_system_prompt),
            "max_tokens": request.max_tokens
            if request.max_tokens is not None
            else self.settings.default_max_tokens,
            "temperature": request.temperature
            if request.temperature is not None
            else self.settings.default_temperature,
            "top_p": request.top_p if request.top_p is not None else self.settings.default_top_p,
        }
        if request.stop is not None:
            payload["stop"] = request.stop
        if stream:
            payload["stream"] = True
        return payload

    @staticmethod
    def _extract_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""

        first_choice = choices[0]
        message = first_choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content

        text = first_choice.get("text")
        if isinstance(text, str):
            return text

        if isinstance(content, list):
            return "".join(
                chunk.get("text", "")
                for chunk in content
                if isinstance(chunk, dict)
            )

        return json.dumps(payload)

    @staticmethod
    def _parse_json(response: httpx.Response) -> Any:
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {
                "text": response.text,
                "content_type": response.headers.get("content-type"),
                "status_code": response.status_code,
            }
