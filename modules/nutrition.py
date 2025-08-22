from __future__ import annotations

from typing import Dict, Any

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from database import get_or_create_user
from ai_agents import query_memory, generate_meal_plan


NUTRITION_CB_PREFIX = "menu:nutrition"


def _calc_bmr(sex: str, weight: float, height: int, age: int) -> float:
    if sex == "male":
        return 88.36 + (13.4 * weight) + (4.8 * height) - (5.7 * age)
    else:
        return 447.6 + (9.2 * weight) + (3.1 * height) - (4.3 * age)


def _calc_calories_for_goal(bmr: float, goal: str) -> int:
    mult = 1.4
    if goal == "fat_loss":
        target = bmr * mult - 400
    elif goal == "muscle_gain":
        target = bmr * mult + 300
    else:
        target = bmr * mult
    return int(max(1200, target))


async def daily_meal_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    weight = float(user.weight_kg or 70)
    height = int(user.height_cm or 175)
    age = int(user.age or 25)
    bmr = _calc_bmr(user.sex or "male", weight, height, age)
    calories = _calc_calories_for_goal(bmr, user.goal or "maintain")
    mem = query_memory(user.telegram_id, "питание предпочтения", n=5)
    plan = generate_meal_plan(user, calories=calories, memory_context=mem)

    lines = [f"🍽️ Рекомендуемая калорийность: {calories} ккал"]
    for meal in plan.get("meals", []):
        lines.append(f"\n{meal['name']} ({meal['calories']} ккал):")
        for item in meal.get("items", []):
            lines.append(f"- {item}")
    await update.message.reply_text("\n".join(lines))


async def nutrition_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Раздел питание: используйте /meal_plan для плана на день.")


def register_nutrition_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("meal_plan", daily_meal_plan))
    app.add_handler(CallbackQueryHandler(nutrition_menu_handler, pattern=f"^{NUTRITION_CB_PREFIX}$"))