from __future__ import annotations

import os
from collections.abc import Mapping

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    reddit_client_id: str = Field(min_length=1)
    reddit_client_secret: SecretStr
    reddit_user_agent: str = Field(min_length=1)
    moonshot_api_key: SecretStr
    kimi_model: str = Field(default="kimi for coding", min_length=1)
    database_path: str = "reddit_pain_search.sqlite3"


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    if env is None:
        load_dotenv()
        env = os.environ

    return AppConfig(
        reddit_client_id=_required(env, "REDDIT_CLIENT_ID"),
        reddit_client_secret=_required(env, "REDDIT_CLIENT_SECRET"),
        reddit_user_agent=_required(env, "REDDIT_USER_AGENT"),
        moonshot_api_key=_required(env, "MOONSHOT_API_KEY"),
        kimi_model=env.get("KIMI_MODEL", "kimi for coding"),
        database_path=env.get("DATABASE_PATH", "reddit_pain_search.sqlite3"),
    )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value
