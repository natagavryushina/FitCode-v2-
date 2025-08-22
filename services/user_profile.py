from __future__ import annotations

from datetime import date
from typing import Dict, Any

from db.database import session_scope
from db import repo


def _calc_age(birth_date_str: str | None) -> int | None:
	if not birth_date_str:
		return None
	try:
		y, m, d = [int(x) for x in birth_date_str.split("-")]
		bd = date(y, m, d)
		today = date.today()
		age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
		return max(0, age)
	except Exception:
		return None


async def get_user_data(tg_user_id: int) -> Dict[str, Any]:
	with session_scope() as s:
		user = repo.get_or_create_user(s, str(tg_user_id), None, None, None)
		prefs = {}
		try:
			prefs = {} if not user.preferences_json else __import__("json").loads(user.preferences_json)
		except Exception:
			prefs = {}
		age = _calc_age(getattr(user, "birth_date", None)) or 0
		streak = 0
		workouts_completed = 0
		achievements = 0
		level = user.level or "не указан"
		goal = ", ".join(prefs.get("goals", [])) or "не указана"
		return {
			"name": user.first_name or user.username or str(tg_user_id),
			"goal": goal,
			"level": level,
			"age": age,
			"weight": user.weight_kg or 0,
			"height": user.height_cm or 0,
			"streak": streak,
			"workouts_completed": workouts_completed,
			"achievements": achievements,
		}