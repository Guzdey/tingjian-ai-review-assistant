from __future__ import annotations

import os
from dataclasses import dataclass

from .schemas import RuntimeMode


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration read only from process environment variables."""

    ai_mode: str
    dashscope_api_key: str
    qwen_base_url: str
    qwen_parse_model: str
    qwen_report_model: str
    request_timeout_seconds: float
    cors_origins: tuple[str, ...]

    @property
    def qwen_enabled(self) -> bool:
        return self.ai_mode != "local" and bool(self.dashscope_api_key)

    @property
    def runtime_mode(self) -> RuntimeMode:
        return RuntimeMode.QWEN if self.qwen_enabled else RuntimeMode.LOCAL_RULES


def load_settings() -> Settings:
    ai_mode = _env("TINGJIAN_AI_MODE", "auto").lower()
    if ai_mode not in {"auto", "local", "qwen"}:
        raise ValueError("TINGJIAN_AI_MODE must be one of: auto, local, qwen")
    key = _env("DASHSCOPE_API_KEY")
    if ai_mode == "qwen" and not key:
        raise ValueError("TINGJIAN_AI_MODE=qwen requires DASHSCOPE_API_KEY")

    origins = tuple(
        origin.strip()
        for origin in _env(
            "TINGJIAN_CORS_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5500,http://127.0.0.1:5500",
        ).split(",")
        if origin.strip()
    )
    return Settings(
        ai_mode=ai_mode,
        dashscope_api_key=key,
        qwen_base_url=_env("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        qwen_parse_model=_env("QWEN_PARSE_MODEL", "qwen-flash"),
        qwen_report_model=_env("QWEN_REPORT_MODEL", "qwen-plus"),
        request_timeout_seconds=float(_env("TINGJIAN_REQUEST_TIMEOUT_SECONDS", "20")),
        cors_origins=origins,
    )
