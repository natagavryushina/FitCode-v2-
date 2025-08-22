from __future__ import annotations

from datetime import date
from typing import Dict, Any

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from database import get_or_create_user
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


async def training_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Раздел тренировки: используйте /train_today для плана на сегодня.")


def register_training_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("train_today", train_today))
    app.add_handler(CallbackQueryHandler(training_menu_handler, pattern=f"^{TRAIN_CB_PREFIX}$"))