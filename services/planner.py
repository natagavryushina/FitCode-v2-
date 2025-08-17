from __future__ import annotations

import json
import html
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

from services.openrouter_client import chat_completion, OpenRouterError
from services.utils import extract_json_block
from db.database import session_scope
from db import repo


def _week_range(today: date) -> Tuple[str, str]:
	start = today
	end = today + timedelta(days=6)
	return start.isoformat(), end.isoformat()


async def ensure_week_workouts(user) -> Tuple[int, int]:
	"""Ensure workout plan exists for current week. Returns (plan_id, today_index)."""
	today = date.today()
	start_str, end_str = _week_range(today)
	with session_scope() as s:
		plan = repo.get_or_create_active_workout_plan(s, user.id, start_str, end_str)
		# if days missing, try to generate
		missing = False
		for i in range(7):
			if not repo.get_workout_day(s, plan.id, i):
				missing = True
				break
	if missing:
		# prompt LLM to return JSON
		prompt = (
			"Составь недельный план тренировок на 7 дней в JSON. Формат: {\n"
			"  \"days\": [ {\"title\": str, \"text\": str}, ... 7 элементов ]\n}"
			". Пиши кратко, безопасно, Пиши, сокращай."
		)
		try:
			content, _ = await chat_completion({}, prompt)
			data = extract_json_block(content) or {}
			days = data.get("days") or []
		except OpenRouterError:
			days = []
		if not days or len(days) < 7:
			# fallback minimal plan
			days = [
				{"title": f"День {i+1}", "text": "Разминка 5 мин. Базовые упражнения 20–30 мин. Растяжка 5 мин."}
				for i in range(7)
			]
		with session_scope() as s2:
			plan = repo.get_or_create_active_workout_plan(s2, user.id, start_str, end_str)
			for i in range(7):
				d = days[i] if i < len(days) else {"title": f"День {i+1}", "text": "Отдых/мобилити 20 мин"}
				repo.upsert_workout_day(s2, plan.id, i, d.get("title") or f"День {i+1}", d.get("text") or "...")
	return plan.id, (today - date.fromisoformat(start_str)).days


async def ensure_week_meals(user) -> Tuple[int, int]:
	"""Ensure meal plan exists for current week. Returns (meal_plan_id, today_index)."""
	today = date.today()
	start_str, end_str = _week_range(today)
	with session_scope() as s:
		plan = repo.get_or_create_active_meal_plan(s, user.id, start_str, end_str)
		missing = False
		for i in range(7):
			if not repo.get_meal_day(s, plan.id, i):
				missing = True
				break
	if missing:
		prompt = (
			"Составь недельный план питания на 7 дней в JSON. Формат: {\n"
			"  \"days\": [ {\"title\": str, \"text\": str}, ... ]\n}"
			". Укажи КБЖУ суммарно на день. Пиши кратко."
		)
		try:
			content, _ = await chat_completion({}, prompt)
			data = extract_json_block(content) or {}
			days = data.get("days") or []
		except OpenRouterError:
			days = []
		if not days or len(days) < 7:
			days = [
				{"title": f"День {i+1}", "text": "~2200 ккал. 3–4 приёма пищи: завтрак/обед/ужин и перекус."}
				for i in range(7)
			]
		with session_scope() as s2:
			plan = repo.get_or_create_active_meal_plan(s2, user.id, start_str, end_str)
			for i in range(7):
				d = days[i] if i < len(days) else {"title": f"День {i+1}", "text": "Свободный день, пей воду"}
				repo.upsert_meal_day(s2, plan.id, i, d.get("title") or f"День {i+1}", d.get("text") or "...")
	return plan.id, (today - date.fromisoformat(start_str)).days