from __future__ import annotations

from typing import Dict, Any
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from database import get_or_create_user, update_user_profile
from ai_agents import add_memory
from keyboards import build_main_menu

(GOAL, LEVEL, ANTHRO_AGE, ANTHRO_HEIGHT, ANTHRO_WEIGHT, SEX, DIET, EQUIPMENT, SESSIONS) = range(9)


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await get_or_create_user(update.effective_user.id)
    await update.message.reply_text(
        "Какая у тебя цель? (похудение/набор/поддержание/мероприятие)", reply_markup=ReplyKeyboardRemove()
    )
    return GOAL


async def set_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").lower()
    mapping = {
        "похудение": "fat_loss",
        "набор": "muscle_gain",
        "поддержание": "maintain",
        "мероприятие": "event_prep",
    }
    goal = mapping.get(text, "maintain")
    context.user_data["goal"] = goal
    await update.message.reply_text("Укажи уровень подготовки (новичок/любитель/профессионал)")
    return LEVEL


async def set_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").lower()
    mapping = {
        "новичок": "beginner",
        "любитель": "intermediate",
        "профессионал": "advanced",
    }
    level = mapping.get(text, "beginner")
    context.user_data["level"] = level
    await update.message.reply_text("Возраст (лет):")
    return ANTHRO_AGE


async def set_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
    except Exception:
        age = 25
    context.user_data["age"] = age
    await update.message.reply_text("Рост (см):")
    return ANTHRO_HEIGHT


async def set_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = int(update.message.text)
    except Exception:
        height = 175
    context.user_data["height_cm"] = height
    await update.message.reply_text("Вес (кг):")
    return ANTHRO_WEIGHT


async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text)
    except Exception:
        weight = 70.0
    context.user_data["weight_kg"] = weight
    await update.message.reply_text("Пол (м/ж):")
    return SEX


async def set_sex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").lower()
    sex = "male" if text.startswith("м") else "female"
    context.user_data["sex"] = sex
    await update.message.reply_text("Предпочтения в питании (веган/keto/палео/без глютена/нет)")
    return DIET


async def set_diet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    diet = (update.message.text or "").lower()
    context.user_data["diet_pref"] = diet
    await update.message.reply_text("Какое оборудование доступно? (перечисли через запятую)")
    return EQUIPMENT


async def set_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.message.text or "").lower()
    equipment = [x.strip() for x in raw.split(",") if x.strip()]
    context.user_data["equipment"] = equipment
    await update.message.reply_text("Сколько тренировок в неделю планируешь?")
    return SESSIONS


async def set_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sessions = int(update.message.text)
    except Exception:
        sessions = 3
    context.user_data["sessions_per_week"] = sessions

    # Persist to DB
    tg_id = update.effective_user.id
    await update_user_profile(
        tg_id,
        goal=context.user_data.get("goal"),
        level=context.user_data.get("level"),
        age=context.user_data.get("age"),
        height_cm=context.user_data.get("height_cm"),
        weight_kg=context.user_data.get("weight_kg"),
        sex=context.user_data.get("sex"),
        diet_pref=context.user_data.get("diet_pref"),
        equipment=context.user_data.get("equipment"),
        sessions_per_week=context.user_data.get("sessions_per_week"),
    )

    # Save onboarding summary into memory
    summary = f"goal={context.user_data['goal']}, level={context.user_data['level']}, diet={context.user_data['diet_pref']}, equipment={context.user_data['equipment']}, sessions={sessions}"
    add_memory(tg_id, [summary], metadatas=[{"type": "onboarding"}])

    await update.message.reply_text("Спасибо! Профиль сохранён. Открываю главное меню…", reply_markup=build_main_menu())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_onboarding)],
        states={
            GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_goal)],
            LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_level)],
            ANTHRO_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_age)],
            ANTHRO_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_height)],
            ANTHRO_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_weight)],
            SEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_sex)],
            DIET: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_diet)],
            EQUIPMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_equipment)],
            SESSIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_sessions)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="onboarding",
        persistent=False,
    )