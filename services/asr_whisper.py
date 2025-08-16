from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from services.config import settings

logger = logging.getLogger(__name__)


class ASRUnavailable(Exception):
	pass


async def transcribe_audio(file_path: Path) -> tuple[str, Optional[float]]:
	if not settings.openai_api_key:
		raise ASRUnavailable("Отсутствует OPENAI_API_KEY для Whisper")

	client = AsyncOpenAI(api_key=settings.openai_api_key)
	model = settings.whisper_model or "whisper-1"

	# OpenAI expects a real file handle
	with open(file_path, "rb") as f:
		result = await client.audio.transcriptions.create(
			model=model,
			file=f,
		)
		text = getattr(result, "text", None) or result.get("text", "")  # type: ignore[attr-defined]
		confidence = None
		return text, confidence