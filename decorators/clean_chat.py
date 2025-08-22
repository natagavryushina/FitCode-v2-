from __future__ import annotations

from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from utils import ChatManager


def clean_chat_decorator(func):
    """Декоратор для автоматической подготовки ChatManager и ответа на callback перед хэндлером."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_manager = context.chat_data.get('chat_manager')
        if not chat_manager:
            chat_manager = ChatManager()
            context.chat_data['chat_manager'] = chat_manager

        # Если это callback query, корректно отвечаем, чтобы убрать "часики"
        if getattr(update, 'callback_query', None):
            await update.callback_query.answer()

        return await func(update, context, *args, **kwargs)

    return wrapper