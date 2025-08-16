from __future__ import annotations

import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from services.config import settings, assert_required_settings
from services.logging import setup_logging
from db.database import engine
from db.models import Base


async def on_startup() -> None:
	# Create tables if not exist
	Base.metadata.create_all(bind=engine)


async def start_bot() -> None:
	setup_logging(settings.log_level)
	logger = logging.getLogger("bot")

	try:
		assert_required_settings()
	except Exception as exc:
		logger.error(str(exc))
		return

	bot = Bot(token=settings.telegram_bot_token, parse_mode=ParseMode.HTML)
	dp = Dispatcher()

	@dp.message(Command("start"))
	async def cmd_start(message: Message) -> None:
		await message.answer(
			"Привет! Я твой фитнес-наставник 🤝\n\n" \
			"Отправь голосовое или текст — подберу тренировку и питание под твои цели. \n" \
			"Команды: /help"
		)

	@dp.message(Command("help"))
	async def cmd_help(message: Message) -> None:
		await message.answer(
			"Коротко о возможностях:\n" \
			"— Голос в текст (Whisper) 🎤 → умный ответ\n" \
			"— Персональные тренировки без повторов 🏋️\n" \
			"— Планы питания под цели 🥗\n\n" \
			"Начни с голосового или расскажи о цели."
		)

	# Echo text as a placeholder
	@dp.message(F.text)
	async def handle_text(message: Message) -> None:
		await message.answer("Принял! Работаю над персональным ответом 💡")

	await on_startup()
	logger.info("Bot is starting (polling)...")
	await dp.start_polling(bot)


if __name__ == "__main__":
	asyncio.run(start_bot())