from __future__ import annotations

import os
from pydantic import BaseSettings, Field
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


class AppSettings(BaseSettings):
	telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
	openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
	openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
	openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
	database_url: str = Field(default="sqlite:////workspace/db/app.db", alias="DATABASE_URL")
	log_level: str = Field(default="INFO", alias="LOG_LEVEL")
	whisper_model: str = Field(default="whisper-1-turbo", alias="WHISPER_MODEL")

	class Config:
		populate_by_name = True
		case_sensitive = False


settings = AppSettings()


def assert_required_settings() -> None:
	missing: list[str] = []
	if not settings.telegram_bot_token:
		missing.append("TELEGRAM_BOT_TOKEN")
	if not settings.openrouter_api_key:
		missing.append("OPENROUTER_API_KEY")
	if missing:
		raised = ", ".join(missing)
		raise RuntimeError(f"Не заданы обязательные переменные окружения: {raised}. См. .env.template")