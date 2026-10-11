"""Warden configuration and environment settings."""

from __future__ import annotations

import sys
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI

_CURRENT_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _CURRENT_DIR.parent.parent
_ENV_FILES = (
    str(_WORKSPACE_ROOT / ".env"),
    str(_CURRENT_DIR / ".env"),
    ".env",
)


class Settings(BaseSettings):
    """Runtime settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "groq_api_key"),
        description="API key for Groq LLM inference.",
    )
    groq_model: str = Field(
        default="openai/gpt-oss-20b",
        validation_alias=AliasChoices("GROQ_MODEL", "groq_model"),
        description="Model identifier to use with Groq.",
    )
    postgres_uri: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CONNECTION_STRING",
            "DATABASE_URL",
            "POSTGRES_URI",
            "POSTGRES_URL",
            "WARDEN_PG_URI",
            "postgres_uri",
        ),
        description="PostgreSQL connection string.",
    )


settings = Settings()


def get_groq_llm(model: str | None = None) -> ChatOpenAI | None:
    """Return configured Groq ChatOpenAI client if groq_api_key is available."""
    if not settings.groq_api_key:
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model or settings.groq_model,
        api_key=SecretStr(settings.groq_api_key),
        base_url="https://api.groq.com/openai/v1",
        temperature=0.0,
    )
