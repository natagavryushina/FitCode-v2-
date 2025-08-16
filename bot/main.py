from __future__ import annotations

import asyncio
import logging
import json
import tempfile
from pathlib import Path
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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
	await _cleanup_chat_messages(context, chat_id)
	sent = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
	_ephemeral_messages.setdefault(chat_id, []).append(sent.message_id)


def _main_reply_kb() -> ReplyKeyboardMarkup:
	return ReplyKeyboardMarkup(
		[[KeyboardButton(text="📋 Меню")]],
		resize_keyboard=True,
		one_time_keyboard=False,
	)


def _main_menu_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		[
			[InlineKeyboardButton(text="👤 Личный кабинет", callback_data="menu_profile")],
			[InlineKeyboardButton(text="🏋️ Тренировки", callback_data="menu_workouts")],
			[InlineKeyboardButton(text="📅 Меню неделю", callback_data="menu_week")],
			[InlineKeyboardButton(text="🤖 AI КБЖУ по фото", callback_data="menu_ai_kbzhu_photo")],
			[InlineKeyboardButton(text="🆘 Поддержка", callback_data="menu_support")],
			[InlineKeyboardButton(text="🎁 Бонусная программа", callback_data="menu_loyalty")],
		]
	)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	await _send_ephemeral(update, context, "Меню открыто. Выбирай раздел 👇", reply_markup=_main_menu_kb())


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if settings.feature_db:
		with session_scope() as s:
			user = repo.get_or_create_user(
				s,
				tg_user_id=str(update.effective_user.id),
				username=update.effective_user.username,
				first_name=update.effective_user.first_name,
				last_name=update.effective_user.last_name,
			)
			seen = repo.get_user_pref(s, user, "start_seen", False)
			if not seen:
				repo.set_user_pref(s, user, "start_seen", True)
				await _cleanup_chat_messages(context, update.effective_chat.id)
				await context.bot.send_message(
					chat_id=update.effective_chat.id,
					text="Добро пожаловать! Нажми <b>📋 Меню</b>, чтобы открыть разделы.",
					parse_mode=ParseMode.HTML,
					reply_markup=_main_reply_kb(),
				)
				return
	# fallback or repeated /start
	await _cleanup_chat_messages(context, update.effective_chat.id)
	await context.bot.send_message(
		chat_id=update.effective_chat.id,
		text="Нажми <b>📋 Меню</b>, чтобы открыть разделы.",
		parse_mode=ParseMode.HTML,
		reply_markup=_main_reply_kb(),
	)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	await _send_ephemeral(update, context, "Подсказка: нажми <b>📋 Меню</b> внизу, чтобы открыть разделы.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if not update.message or not update.message.text:
		return
	user_text = update.message.text.strip()

	# Open menu when user taps the persistent button
	if user_text.lower() in {"📋 меню", "меню", "/menu", "menu"}:
		await show_main_menu(update, context)
		return

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

	reply_text = "Принял! Нажми <b>📋 Меню</b> для навигации."
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

	await _send_ephemeral(update, context, reply_text)

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
		await _send_ephemeral(update, context, "Голос пока не подключён. Отправь текст ✍️")
		return

	voice = update.message.voice
	with tempfile.TemporaryDirectory() as td:
		dl_path = Path(td) / f"{voice.file_unique_id}.oga"
		try:
			file = await context.bot.get_file(voice.file_id)
			await file.download_to_drive(custom_path=str(dl_path))
		except Exception as e:
			logging.getLogger("download").error("Failed to download voice: %s", e)
			await _send_ephemeral(update, context, "Не удалось скачать голосовое. Попробуй ещё раз 🙏")
			return
		try:
			text, _conf = await transcribe_audio(dl_path)
		except ASRUnavailable:
			await _send_ephemeral(update, context, "ASR временно недоступен. Добавь текстом, пожалуйста 🙏")
			return
		except Exception as e:
			logging.getLogger("asr").error("Whisper failed: %s", e)
			await _send_ephemeral(update, context, "Не удалось распознать голос. Попробуй ещё раз 🙏")
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

	await _send_ephemeral(update, context, reply_text)

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
	_ephemeral_messages.setdefault(query.message.chat_id, []).append(query.message.message_id)
	if data == "menu_profile":
		await _send_ephemeral(update, context, "Личный кабинет — скоро здесь можно будет настраивать профиль 👤")
	elif data == "menu_workouts":
		await _send_ephemeral(update, context, "Тренировки — персональные планы в разработке 💪")
	elif data == "menu_week":
		await _send_ephemeral(update, context, "Меню на неделю — скоро подберём рацион под цель 🥗")
	elif data == "menu_ai_kbzhu_photo":
		await _send_ephemeral(update, context, "AI КБЖУ по фото — загрузка снимка и анализ скоро будут доступны 📸")
	elif data == "menu_support":
		await _send_ephemeral(update, context, "Поддержка — напиши вопрос, мы поможем 🆘")
	elif data == "menu_loyalty":
		await _send_ephemeral(update, context, "Бонусная программа — копи баллы и получай плюсы 🎁")
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