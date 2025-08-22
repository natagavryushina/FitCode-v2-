from __future__ import annotations

from typing import Dict, Any

from db.database import session_scope
from db import repo
from services.planner import ensure_week_workouts


async def get_user_workouts(tg_user_id: int) -> Dict[str, Any]:
	with session_scope() as s:
		user = repo.get_or_create_user(s, str(tg_user_id), None, None, None)
	# Ensure a weekly plan exists and fetch today's index
	plan_id, today_idx = await ensure_week_workouts(user)
	with session_scope() as s2:
		day = repo.get_workout_day(s2, plan_id, today_idx)
		today = {
			"title": (day.title if day else f"День {today_idx+1}"),
			"text": (day.content_text if day else "Отдых/мобилити 20 мин"),
		}
	return {"plan_id": plan_id, "today_idx": today_idx, "today": today}