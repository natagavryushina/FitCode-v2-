from __future__ import annotations

from typing import Dict, Any, List

from db.database import session_scope
from db import repo


def format_achievements(achievements: List[Dict[str, Any]]) -> str:
	"""Format achievements list for display"""
	if not achievements:
		return "• Пока нет достижений"
	
	formatted = []
	for achievement in achievements:
		formatted.append(f"• {achievement['name']} - {achievement['description']}")
	return "\n".join(formatted)


async def get_user_bonuses(tg_user_id: int) -> Dict[str, Any]:
	with session_scope() as s:
		user = repo.get_or_create_user(s, str(tg_user_id), None, None, None)
		# Get loyalty points
		loyalty = repo.get_loyalty_points(s, user.id)
		# Mock achievements for now
		achievements = [
			{"name": "Первые шаги", "description": "Завершил первую тренировку"},
			{"name": "Неделя тренировок", "description": "7 дней подряд"},
			{"name": "Цель достигнута", "description": "Выполнил 10 тренировок"},
		]
		return {
			"points": loyalty,
			"achievements": achievements,
		}