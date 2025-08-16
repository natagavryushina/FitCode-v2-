from __future__ import annotations

import json
import logging
from typing import Any, Dict, Tuple
import httpx

from services.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
	"Ты — профессиональный фитнес-наставник и копирайтер. Пиши кратко и ясно, по принципам «Пиши, сокращай». "
	"Тон — дружелюбный, мотивирующий, без назидания. Добавляй уместные эмодзи. Соблюдай безопасность движений и мед. ограничения. "
	"Если данных мало — задай 1–2 уточняющих вопроса. Форматируй ответ для Телеграм: короткие абзацы и списки."
)


class OpenRouterError(Exception):
	pass


async def chat_completion(categories: Dict[str, Any], user_text: str) -> Tuple[str, Dict[str, Any]]:
	if not settings.openrouter_api_key:
		raise OpenRouterError("Отсутствует OPENROUTER_API_KEY")

	model = getattr(settings, "openrouter_model", None) or "openai/gpt-4o-mini"
	url = settings.openrouter_base_url.rstrip("/") + "/chat/completions"
	headers = {
		"Authorization": f"Bearer {settings.openrouter_api_key}",
		"Content-Type": "application/json",
		"HTTP-Referer": "https://example.local/",
		"X-Title": "FitnessCoachBot",
	}
	payload = {
		"model": model,
		"messages": [
			{"role": "system", "content": SYSTEM_PROMPT},
			{
				"role": "user",
				"content": (
					"Контекст пользователя (JSON):\n" + json.dumps(categories, ensure_ascii=False) +
					"\n\nСообщение пользователя:\n\n" + user_text +
					"\n\nЗадача: дай конкретный, безопасный и краткий ответ + предложи следующий шаг (кнопка/команда)."
				),
			},
		],
		"temperature": 0.4,
	}

	async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
		resp = await client.post(url, headers=headers, json=payload)
		if resp.status_code >= 400:
			logger.error("OpenRouter error %s: %s", resp.status_code, resp.text[:500])
			raise OpenRouterError(f"Ошибка OpenRouter: {resp.status_code}")
		data = resp.json()

	choices = data.get("choices", [])
	if not choices:
		raise OpenRouterError("Пустой ответ от LLM")

	text = choices[0].get("message", {}).get("content", "")
	usage = data.get("usage", {})
	return text, usage