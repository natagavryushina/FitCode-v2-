from __future__ import annotations

from typing import Dict, Any

from db.database import session_scope
from db import repo
from services.planner import ensure_week_meals


async def generate_weekly_menu(tg_user_id: int) -> Dict[str, Any]:
	with session_scope() as s:
		user = repo.get_or_create_user(s, str(tg_user_id), None, None, None)
		prefs = {}
		try:
			prefs = {} if not user.preferences_json else __import__("json").loads(user.preferences_json)
		except Exception:
			prefs = {}
	# Ensure a weekly meal plan exists
	plan_id, today_idx = await ensure_week_meals(user)
	with session_scope() as s2:
		days = []
		for i in range(7):
			day = repo.get_meal_day(s2, plan_id, i)
			days.append({
				"title": (day.title if day else f"День {i+1}"),
				"text": (day.content_text if day else "~2200 ккал, 3–4 приёма пищи"),
				"calories": 2200,  # Default
			})
	# Determine calories based on user goals
	goals = prefs.get("goals", [])
	base_calories = 2200
	if "похудение" in goals:
		base_calories = 1800
	elif "набор_массы" in goals:
		base_calories = 2500
	return {
		"goal": ", ".join(goals) or "поддержание формы",
		"calories": base_calories,
		"protein": int(base_calories * 0.25 / 4),  # 25% of calories
		"carbs": int(base_calories * 0.45 / 4),   # 45% of calories
		"fat": int(base_calories * 0.30 / 9),     # 30% of calories
		"days": days,
	}