from __future__ import annotations

from typing import Dict, Any
import uuid


async def analyze_food_photo(photo_path: str) -> Dict[str, Any]:
	"""Analyze food photo and return nutrition data. Mock implementation for now."""
	# TODO: Integrate with actual AI vision service
	# For now, return mock data based on common dishes
	import random
	dishes = [
		{
			"name": "Куриная грудка с овощами",
			"weight": 250,
			"calories": 320,
			"protein": 35,
			"fat": 8,
			"carbs": 15,
			"recommendations": "Отличный выбор для похудения! Высокий белок, низкие углеводы."
		},
		{
			"name": "Паста карбонара",
			"weight": 300,
			"calories": 450,
			"protein": 18,
			"fat": 22,
			"carbs": 45,
			"recommendations": "Умеренно калорийно. Для набора массы - добавьте белок."
		},
		{
			"name": "Салат Цезарь",
			"weight": 200,
			"calories": 280,
			"protein": 12,
			"fat": 18,
			"carbs": 20,
			"recommendations": "Хороший баланс. Осторожно с соусом - много жира."
		}
	]
	dish = random.choice(dishes)
	return {
		"id": str(uuid.uuid4()),
		"dish_name": dish["name"],
		"weight": dish["weight"],
		"calories": dish["calories"],
		"protein": dish["protein"],
		"fat": dish["fat"],
		"carbs": dish["carbs"],
		"recommendations": dish["recommendations"],
	}