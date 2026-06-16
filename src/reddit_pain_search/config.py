from __future__ import annotations

import os
from collections.abc import Mapping

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    reddit_client_id: str | None = None
    reddit_client_secret: SecretStr | None = None
    reddit_user_agent: str | None = None
    moonshot_api_key: SecretStr
    kimi_model: str = Field(default="kimi for coding", min_length=1)
    database_path: str = "reddit_pain_search.sqlite3"
    web_access_proxy_url: str = Field(default="http://localhost:3456", min_length=1)


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    if env is None:
        load_dotenv()
        env = os.environ

    return AppConfig(
        reddit_client_id=_optional(env, "REDDIT_CLIENT_ID"),
        reddit_client_secret=_optional(env, "REDDIT_CLIENT_SECRET"),
        reddit_user_agent=_optional(env, "REDDIT_USER_AGENT"),
        moonshot_api_key=_required(env, "MOONSHOT_API_KEY"),
        kimi_model=env.get("KIMI_MODEL", "kimi for coding"),
        database_path=env.get("DATABASE_PATH", "reddit_pain_search.sqlite3"),
        web_access_proxy_url=env.get("WEB_ACCESS_PROXY_URL", "http://localhost:3456"),
    )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _optional(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name, "").strip()
    return value or None
