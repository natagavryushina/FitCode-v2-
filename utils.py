import logging
import os
from datetime import time, datetime
from typing import Callable

from telegram.ext import Application, CommandHandler, ContextTypes


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