import logging
import os
from datetime import time, datetime
from typing import Callable

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update, InlineKeyboardMarkup


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=getattr(logging, level, logging.INFO),
    )


async def _reminder_job(context) -> None:
    job = context.job
    try:
        await context.bot.send_message(chat_id=job.chat_id, text=job.data)
    except Exception:
        logging.exception("Failed to send reminder")


def schedule_reminders(app: Application) -> None:
    jq = app.job_queue
    # Example daily reminders at 09:00 local server time
    user_id = os.getenv("TEST_USER_ID")
    if user_id:
        jq.run_daily(_reminder_wrapper(int(user_id), "Пора тренироваться!"), time=time(hour=9, minute=0))
        jq.run_daily(_reminder_wrapper(int(user_id), "Не забудь пить воду 💧"), time=time(hour=12, minute=0))


def _reminder_wrapper(chat_id: int, text: str) -> Callable:
    async def _job(ctx):
        await ctx.bot.send_message(chat_id=chat_id, text=text)
    return _job


async def cmd_remind_water(update, context: ContextTypes.DEFAULT_TYPE):
    jq = context.job_queue
    chat_id = update.effective_chat.id
    jq.run_daily(_reminder_wrapper(chat_id, "Пора пить воду 💧"), time=time(hour=12, minute=0))
    await update.message.reply_text("Напоминание о воде запланировано на 12:00 ежедневно")


async def cmd_remind_train(update, context: ContextTypes.DEFAULT_TYPE):
    jq = context.job_queue
    chat_id = update.effective_chat.id
    jq.run_daily(_reminder_wrapper(chat_id, "Тренировка сегодня!"), time=time(hour=9, minute=0))
    await update.message.reply_text("Напоминание о тренировке запланировано на 09:00 ежедневно")


async def cmd_remind_clear(update, context: ContextTypes.DEFAULT_TYPE):
    jq = context.job_queue
    chat_id = update.effective_chat.id
    # Clear all jobs for this chat
    for job in jq.jobs():
        jq.scheduler.cancel(job)
    await update.message.reply_text("Напоминания очищены")


def register_reminder_commands(app: Application) -> None:
    app.add_handler(CommandHandler("remind_water", cmd_remind_water))
    app.add_handler(CommandHandler("remind_train", cmd_remind_train))
    app.add_handler(CommandHandler("remind_clear", cmd_remind_clear))


# --------- Formatters ---------

def _fmt_weight(kg: float | None) -> str:
    return f"{kg:g} кг" if kg is not None else "—"


def format_daily_workout_message(workout) -> str:
    # Lazy imports to avoid circulars
    from database import ExerciseSession
    message = f"🏋️‍♂️ *Тренировка на сегодня* ({getattr(workout, 'muscle_group', '')})\n\n"
    sessions = getattr(workout, "exercise_sessions", [])
    for exercise in sessions:
        name = getattr(getattr(exercise, "exercise", None), "name", "Упражнение")
        message += f"*{name}*\n"
        message += f"• Подходы: {exercise.target_sets or 0}\n"
        message += f"• Повторы: {exercise.target_reps or '-'}\n"
        message += f"• Вес: {_fmt_weight(exercise.target_weight)}\n"
        message += f"• Отдых: {exercise.rest_time_seconds or 0} сек\n"
        message += f"• RPE: {exercise.rpe or 0}/10\n\n"
    message += f"⏱ Общее время: {int(getattr(workout, 'duration_minutes', 0) or 0)} мин\n"
    message += f"📊 Общий объем: {getattr(workout, 'total_volume', 0) or 0:g} кг\n"
    return message


def format_weekly_schedule_message(plan) -> str:
    message = "📅 *План тренировок на неделю*\n\n"
    days = getattr(plan, "daily_workouts", []) or []
    for day in days:
        message += f"*День {day.day_number}:* {day.muscle_group}\n"
        message += f"Тип: {day.workout_type}\n"
        message += f"Длительность: {int(getattr(day, 'duration_minutes', 0) or 0)} мин\n\n"
    return message


# --------- Chat Manager (cleanup & immersive navigation) ---------

class ChatManager:
    def __init__(self):
        self.user_messages: dict[int, list[int]] = {}

    async def cleanup_previous_messages(self, user_id: int, bot):
        if user_id in self.user_messages:
            for msg_id in self.user_messages[user_id]:
                try:
                    await bot.delete_message(chat_id=user_id, message_id=msg_id)
                except Exception as e:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {e}")
            self.user_messages[user_id] = []

    async def track_new_message(self, user_id: int, message_id: int):
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        self.user_messages[user_id].append(message_id)

    async def send_clean_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ):
        user_id = update.effective_user.id
        await self.cleanup_previous_messages(user_id, context.bot)
        message = await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
        )
        await self.track_new_message(user_id, message.message_id)
        return message


# Singleton instance
chat_manager = ChatManager()


# --------- Navigation Manager (menu stack) ---------

class NavigationManager:
    def __init__(self):
        self.user_navigation: dict[int, list[str]] = {}

    def push_menu(self, user_id: int, menu_name: str):
        if user_id not in self.user_navigation:
            self.user_navigation[user_id] = []
        self.user_navigation[user_id].append(menu_name)

    def pop_menu(self, user_id: int) -> str:
        if user_id in self.user_navigation and self.user_navigation[user_id]:
            return self.user_navigation[user_id].pop()
        return "main_menu"

    def get_current_menu(self, user_id: int) -> str:
        if user_id in self.user_navigation and self.user_navigation[user_id]:
            return self.user_navigation[user_id][-1]
        return "main_menu"

    def clear_navigation(self, user_id: int):
        if user_id in self.user_navigation:
            self.user_navigation[user_id] = []


navigation_manager = NavigationManager()