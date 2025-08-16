from __future__ import annotations

import asyncio
import logging
import json
import tempfile
from pathlib import Path
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from services.config import settings, assert_required_settings
from services.logging import setup_logging
from db.database import engine, session_scope
from db.models import Base
from db import repo
from services.categories import build_categories
from services.openrouter_client import chat_completion, OpenRouterError
from services.asr_whisper import transcribe_audio, ASRUnavailable

# In-memory store of last bot messages per chat for cleanup
_ephemeral_messages: Dict[int, List[int]] = {}


async def on_startup() -> None:
	if settings.feature_db:
		Base.metadata.create_all(bind=engine)


async def _cleanup_chat_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
	msg_ids = _ephemeral_messages.get(chat_id) or []
	if not msg_ids:
		return
	for mid in msg_ids:
		try:
			await context.bot.delete_message(chat_id=chat_id, message_id=mid)
		except Exception:
			pass
	_ephemeral_messages[chat_id] = []


async def _send_ephemeral(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
	chat_id = update.effective_chat.id
	# Delete previous ephemeral messages
	await _cleanup_chat_messages(context, chat_id)
	# Send fresh message
	sent = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
	_ephemeral_messages.setdefault(chat_id, []).append(sent.message_id)


def _main_menu_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		[
			[
				InlineKeyboardButton(text="🏋️ Тренировка сегодня", callback_data="menu_workout"),
				InlineKeyboardButton(text="🥗 Питание сегодня", callback_data="menu_nutrition"),
			],
			[
				InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu_help"),
			]
		]
	)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	await _send_ephemeral(
		update,
		context,
		"Выбирай, чем займёмся сейчас 👇",
		reply_markup=_main_menu_kb(),
	)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	await show_main_menu(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	await _send_ephemeral(
		update,
		context,
		"Коротко о возможностях:\n— Голос в текст (Whisper) 🎤\n— Персональные тренировки без повторов 🏋️\n— Планы питания под цели 🥗\n\nНажми кнопку ниже, чтобы продолжить.",
		reply_markup=_main_menu_kb(),
	)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if not update.message or not update.message.text:
		return
	user_text = update.message.text

	if settings.feature_db:
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
	else:
		user = None
		categories = build_categories(None)
		categories_json = json.dumps(categories, ensure_ascii=False)

	reply_text = "Принял! Работаю над персональным ответом 💡\n\nНажми кнопку, чтобы выбрать действие."
	if settings.feature_llm:
		try:
			reply_text, usage = await chat_completion(categories, user_text)
			if settings.feature_db and user:
				with session_scope() as s:
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

	await _send_ephemeral(update, context, reply_text, reply_markup=_main_menu_kb())

	if settings.feature_db:
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

	if not settings.feature_asr:
		await _send_ephemeral(update, context, "Голос пока не подключён. Отправь текст ✍️", reply_markup=_main_menu_kb())
		return

	voice = update.message.voice
	with tempfile.TemporaryDirectory() as td:
		dl_path = Path(td) / f"{voice.file_unique_id}.oga"
		try:
			file = await context.bot.get_file(voice.file_id)
			await file.download_to_drive(custom_path=str(dl_path))
		except Exception as e:
			logging.getLogger("download").error("Failed to download voice: %s", e)
			await _send_ephemeral(update, context, "Не удалось скачать голосовое. Попробуй ещё раз 🙏", reply_markup=_main_menu_kb())
			return
		try:
			text, _conf = await transcribe_audio(dl_path)
		except ASRUnavailable:
			await _send_ephemeral(update, context, "ASR временно недоступен. Добавь текстом, пожалуйста 🙏", reply_markup=_main_menu_kb())
			return
		except Exception as e:
			logging.getLogger("asr").error("Whisper failed: %s", e)
			await _send_ephemeral(update, context, "Не удалось распознать голос. Попробуй ещё раз 🙏", reply_markup=_main_menu_kb())
			return

	user = None
	if settings.feature_db:
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

	categories = build_categories(user if settings.feature_db else None)
	categories_json = json.dumps(categories, ensure_ascii=False)
	reply_text = text
	if settings.feature_llm:
		try:
			reply_text, usage = await chat_completion(categories, text)
			if settings.feature_db and user:
				with session_scope() as s:
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

	await _send_ephemeral(update, context, reply_text, reply_markup=_main_menu_kb())

	if settings.feature_db:
		with session_scope() as s2:
			user2 = repo.get_or_create_user(
				s2,
				tg_user_id=str(update.effective_user.id),
				username=update.effective_user.username,
				first_name=update.effective_user.first_name,
				last_name=update.effective_user.last_name,
			)
			repo.add_message(s2, user_id=user2.id, direction="out", type_="text", content=reply_text)


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	query = update.callback_query
	if not query:
		return
	await query.answer()
	data = query.data or ""
	# Also record the original message for cleanup
	_ephemeral_messages.setdefault(query.message.chat_id, []).append(query.message.message_id)
	if data == "menu_workout":
		await _send_ephemeral(update, context, "Тренировка на сегодня скоро будет готова 💪\n\nПока доступен демо-режим.", reply_markup=_main_menu_kb())
	elif data == "menu_nutrition":
		await _send_ephemeral(update, context, "Рацион на сегодня — в разработке 🥗\n\nВыбери другой раздел.", reply_markup=_main_menu_kb())
	elif data == "menu_help":
		await help_command(update, context)
	else:
		await show_main_menu(update, context)


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
	app.add_handler(CommandHandler("menu", show_main_menu))
	app.add_handler(CommandHandler("help", help_command))
	app.add_handler(CallbackQueryHandler(handle_menu_callback))
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