import asyncio
import logging
import os
from datetime import time

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import init_db
from database import log_message
from ai_agents import add_memory
from keyboards import build_main_menu
from modules.onboarding import get_conversation_handler
from modules.training import register_training_handlers
from modules.nutrition import register_nutrition_handlers
from modules.progress import register_progress_handlers
from modules.videos import register_video_handlers
from modules.analysis import register_analysis_handlers
from utils import setup_logging, schedule_reminders, register_reminder_commands


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = build_main_menu()
    await update.message.reply_text("Главное меню", reply_markup=keyboard)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.exception("Error while handling update", exc_info=context.error)


def get_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var not set")
    return token


async def on_startup(app: Application) -> None:
    await init_db()
    schedule_reminders(app)


def main() -> None:
    setup_logging()

    application: Application = (
        ApplicationBuilder()
        .token(get_token())
        .post_init(on_startup)
        .build()
    )

    # Core commands
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("start", menu_command))
    
    # Global text logger (skip commands)
    async def _log_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message and update.message.text:
            text = update.message.text
            await log_message(update.effective_user.id, "user", text)
            add_memory(update.effective_user.id, [text], metadatas=[{"type": "user_msg"}])
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _log_any))

    # Conversation / FSM onboarding
    application.add_handler(get_conversation_handler())

    # Feature modules
    register_training_handlers(application)
    register_nutrition_handlers(application)
    register_progress_handlers(application)
    register_video_handlers(application)
    register_analysis_handlers(application)
    register_reminder_commands(application)

    # Callback queries for menu are handled inside modules via shared prefix routing

    application.add_error_handler(error_handler)

    application.run_polling()


if __name__ == "__main__":
    main()