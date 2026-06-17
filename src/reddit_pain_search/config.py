from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    reddit_client_id: str | None = None
    reddit_client_secret: SecretStr | None = None
    reddit_user_agent: str | None = None
    llm_api_key: SecretStr
    llm_model: str = Field(default="qwen3.7-plus", min_length=1)
    llm_base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", min_length=1)
    database_path: str = "reddit_pain_search.sqlite3"
    web_access_proxy_url: str = Field(default="http://localhost:3456", min_length=1)


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    if env is None:
        load_dotenv(dotenv_path=Path.cwd() / ".env", override=True)
        env = os.environ

    return AppConfig(
        reddit_client_id=_optional(env, "REDDIT_CLIENT_ID"),
        reddit_client_secret=_optional(env, "REDDIT_CLIENT_SECRET"),
        reddit_user_agent=_optional(env, "REDDIT_USER_AGENT"),
        llm_api_key=_required_any(env, ("LLM_API_KEY", "DASHSCOPE_API_KEY", "MOONSHOT_API_KEY")),
        llm_model=_first_present(env, ("LLM_MODEL", "KIMI_MODEL"), "qwen3.7-plus"),
        llm_base_url=_first_present(
            env,
            ("LLM_BASE_URL", "DASHSCOPE_BASE_URL", "KIMI_BASE_URL"),
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        database_path=env.get("DATABASE_PATH", "reddit_pain_search.sqlite3"),
        web_access_proxy_url=env.get("WEB_ACCESS_PROXY_URL", "http://localhost:3456"),
    )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _required_any(env: Mapping[str, str], names: tuple[str, ...]) -> str:
    value = _first_present(env, names, "")
    if not value:
        joined = " or ".join(names)
        raise ValueError(f"{joined} is required")
    return value


def _first_present(env: Mapping[str, str], names: tuple[str, ...], default: str) -> str:
    for name in names:
        value = env.get(name, "").strip()
        if value:
            return value
    return default


def _optional(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name, "").strip()
    return value or None
