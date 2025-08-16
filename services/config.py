from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


def env_bool(name: str, default: str = "0") -> bool:
	val = os.getenv(name, default).strip().lower()
	return val in ("1", "true", "yes", "y", "on")


@dataclass
class AppSettings:
	telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
	openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
	openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
	openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
	openrouter_model: str = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
	database_url: str = os.getenv("DATABASE_URL", "sqlite:////workspace/db/app.db")
	log_level: str = os.getenv("LOG_LEVEL", "INFO")
	whisper_model: str = os.getenv("WHISPER_MODEL", "whisper-1")
	bot_logo_url: str | None = os.getenv("BOT_LOGO_URL")

	# Feature flags for staged rollout
	feature_db: bool = env_bool("FEATURE_DB", "0")
	feature_asr: bool = env_bool("FEATURE_ASR", "0")
	feature_llm: bool = env_bool("FEATURE_LLM", "0")


settings = AppSettings()


def assert_required_settings() -> None:
	missing: list[str] = []
	if not settings.telegram_bot_token:
		missing.append("TELEGRAM_BOT_TOKEN")
	if missing:
		raised = ", ".join(missing)
		raise RuntimeError(f"Не заданы обязательные переменные окружения: {raised}. См. .env.template")