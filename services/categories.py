from __future__ import annotations

from typing import Any, Dict
from db.models import User


def build_categories(user: User | None) -> Dict[str, Any]:
	if not user:
		return {
			"profile": {},
			"goals": [],
			"equipment": [],
			"schedule": {},
			"nutrition": {},
			"history": {},
			"constraints": {},
		}
	return {
		"profile": {
			"sex": user.sex,
			"height_cm": user.height_cm,
			"weight_kg": user.weight_kg,
			"level": user.level,
		},
		"goals": [],
		"equipment": [],
		"schedule": {"timezone": user.timezone},
		"nutrition": {"diet_type": user.diet_type, "allergies": user.allergies},
		"history": {},
		"constraints": {"injuries": user.injuries},
	}