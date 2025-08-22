from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Any, List

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from database import get_or_create_user, save_weekly_workout_plan
from ai_agents import query_memory, generate_workout


TRAIN_CB_PREFIX = "menu:training"


async def train_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    mem = query_memory(user.telegram_id, "тренировки предпочтения", n=5)
    plan = generate_workout(user, today_weekday=date.today().weekday(), memory_context=mem)

    lines = [f"🏋️ Сегодня: {plan.get('name','')}"]
    for ex in plan.get("exercises", []):
        lines.append(f"- {ex['name']}: {ex['sets']}x{ex['reps']} отдых {ex['rest_s']}с")
        if ex.get("technique"):
            lines.append(f"  техника: {ex['technique']}")
    await update.message.reply_text("\n".join(lines))


async def plan_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    mem = query_memory(user.telegram_id, "история тренировки цели", n=8)
    week_start = date.today() - timedelta(days=date.today().weekday())
    days: List[str] = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    week_plan: Dict[str, Any] = {}
    for i in range(7):
        p = generate_workout(user, today_weekday=i, memory_context=mem)
        week_plan[days[i]] = p
    await save_weekly_workout_plan(user.telegram_id, week_start, week_plan)
    text_lines = ["План на неделю:"]
    for d in days:
        text_lines.append(f"\n{d}: {week_plan[d].get('name','')}")
    await update.message.reply_text("\n".join(text_lines))


async def training_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Раздел тренировки: /train_today или /plan_week.")


def register_training_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("train_today", train_today))
    app.add_handler(CommandHandler("plan_week", plan_week))
    app.add_handler(CallbackQueryHandler(training_menu_handler, pattern=f"^{TRAIN_CB_PREFIX}$"))