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
)

from database import init_db
from keyboards import build_main_menu
from modules.onboarding import get_conversation_handler
from modules.training import register_training_handlers
from modules.nutrition import register_nutrition_handlers
from modules.progress import register_progress_handlers
from modules.videos import register_video_handlers
from modules.analysis import register_analysis_handlers
from utils import setup_logging, schedule_reminders


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

    # Conversation / FSM onboarding
    application.add_handler(get_conversation_handler())

    # Feature modules
    register_training_handlers(application)
    register_nutrition_handlers(application)
    register_progress_handlers(application)
    register_video_handlers(application)
    register_analysis_handlers(application)

    # Callback queries for menu are handled inside modules via shared prefix routing

    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()