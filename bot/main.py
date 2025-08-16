from __future__ import annotations

import asyncio
import logging
import json
import tempfile
from pathlib import Path
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from services.config import settings, assert_required_settings
from services.logging import setup_logging
from db.database import engine, session_scope
from db.models import Base
from db import repo
from services.categories import build_categories
from services.openrouter_client import chat_completion, OpenRouterError
from services.asr_whisper import transcribe_audio, ASRUnavailable


async def on_startup() -> None:
	Base.metadata.create_all(bind=engine)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	await update.message.reply_text(
		"Привет! Я твой фитнес-наставник 🤝\n\n"
		"Отправь голосовое или текст — подберу тренировку и питание под твои цели. \n"
		"Команды: /help",
		parse_mode=ParseMode.HTML,
	)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	await update.message.reply_text(
		"Коротко о возможностях:\n"
		"— Голос в текст (Whisper) 🎤 → умный ответ\n"
		"— Персональные тренировки без повторов 🏋️\n"
		"— Планы питания под цели 🥗\n\n"
		"Начни с голосового или расскажи о цели.",
		parse_mode=ParseMode.HTML,
	)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if not update.message or not update.message.text:
		return
	user_text = update.message.text
	with session_scope() as s:
		user = repo.get_or_create_user(
			s,
			tg_user_id=str(update.effective_user.id),
			username=update.effective_user.username,
			first_name=update.effective_user.first_name,
			last_name=update.effective_user.last_name,
		)
		repo.add_message(s, user_id=user.id, direction="in", type_="text", content=user_text)
		categories = build_categories(user)
		categories_json = json.dumps(categories, ensure_ascii=False)
		try:
			reply_text, usage = await chat_completion(categories, user_text)
			repo.add_llm_exchange(
				s,
				user_id=user.id,
				provider="openrouter",
				model=settings.openrouter_model,
				prompt=user_text,
				categories_json=categories_json,
				response_text=reply_text,
				usage=usage,
			)
		except OpenRouterError as e:
			reply_text = "Сервис рекомендаций временно недоступен. Попробуй ещё раз позже 🙏"
			logging.getLogger("llm").error("OpenRouter error: %s", e)
	await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
	with session_scope() as s2:
		user2 = repo.get_or_create_user(
			s2,
			tg_user_id=str(update.effective_user.id),
			username=update.effective_user.username,
			first_name=update.effective_user.first_name,
			last_name=update.effective_user.last_name,
		)
		repo.add_message(s2, user_id=user2.id, direction="out", type_="text", content=reply_text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if not update.message or not update.message.voice:
		return
	voice = update.message.voice
	with tempfile.TemporaryDirectory() as td:
		dl_path = Path(td) / f"{voice.file_unique_id}.oga"
		try:
			file = await context.bot.get_file(voice.file_id)
			await file.download_to_drive(custom_path=str(dl_path))
		except Exception as e:
			logging.getLogger("download").error("Failed to download voice: %s", e)
			await update.message.reply_text("Не удалось скачать голосовое. Попробуй ещё раз 🙏")
			return
		try:
			text, _conf = await transcribe_audio(dl_path)
		except ASRUnavailable:
			await update.message.reply_text("ASR временно недоступен. Добавь текстом, пожалуйста 🙏")
			return
		except Exception as e:
			logging.getLogger("asr").error("Whisper failed: %s", e)
			await update.message.reply_text("Не удалось распознать голос. Попробуй ещё раз 🙏")
			return

	with session_scope() as s:
		user = repo.get_or_create_user(
			s,
			tg_user_id=str(update.effective_user.id),
			username=update.effective_user.username,
			first_name=update.effective_user.first_name,
			last_name=update.effective_user.last_name,
		)
		repo.add_message(s, user_id=user.id, direction="in", type_="voice", content=text)
		repo.add_transcription(s, user_id=user.id, telegram_file_id=voice.file_id, text=text, audio_duration_sec=voice.duration, format_=voice.mime_type)
		categories = build_categories(user)
		categories_json = json.dumps(categories, ensure_ascii=False)
		try:
			reply_text, usage = await chat_completion(categories, text)
			repo.add_llm_exchange(
				s,
				user_id=user.id,
				provider="openrouter",
				model=settings.openrouter_model,
				prompt=text,
				categories_json=categories_json,
				response_text=reply_text,
				usage=usage,
			)
		except OpenRouterError as e:
			reply_text = "Сервис рекомендаций временно недоступен. Попробуй ещё раз позже 🙏"
			logging.getLogger("llm").error("OpenRouter error: %s", e)

	await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
	with session_scope() as s2:
		user2 = repo.get_or_create_user(
			s2,
			tg_user_id=str(update.effective_user.id),
			username=update.effective_user.username,
			first_name=update.effective_user.first_name,
			last_name=update.effective_user.last_name,
		)
		repo.add_message(s2, user_id=user2.id, direction="out", type_="text", content=reply_text)


async def run() -> None:
	setup_logging(settings.log_level)
	logger = logging.getLogger("bot")
	try:
		assert_required_settings()
	except Exception as exc:
		logger.error(str(exc))
		return

	await on_startup()

	app = ApplicationBuilder().token(settings.telegram_bot_token).build()
	app.add_handler(CommandHandler("start", start_command))
	app.add_handler(CommandHandler("help", help_command))
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
	app.add_handler(MessageHandler(filters.VOICE, handle_voice))

	logger.info("Bot is starting (polling)...")
	await app.initialize()
	await app.start()
	try:
		await app.updater.start_polling()
		await asyncio.Event().wait()
	finally:
		await app.stop()
		await app.shutdown()


if __name__ == "__main__":
	asyncio.run(run())