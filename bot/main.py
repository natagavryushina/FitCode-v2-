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


async def _safe_delete_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int) -> None:
	try:
		await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
	except Exception:
		pass


def _main_menu_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		[
			[
				InlineKeyboardButton(text="👤 Личный кабинет", callback_data="menu_profile"),
				InlineKeyboardButton(text="🏋️ Тренировки", callback_data="menu_workouts"),
				InlineKeyboardButton(text="📅 Меню неделю", callback_data="menu_week"),
			],
			[
				InlineKeyboardButton(text="🤖 AI КБЖУ по фото", callback_data="menu_ai_kbzhu_photo"),
				InlineKeyboardButton(text="🆘 Поддержка", callback_data="menu_support"),
				InlineKeyboardButton(text="🎁 Бонусная программа", callback_data="menu_loyalty"),
			],
		]
	)


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
	welcome = (
		"<b>Привет!</b> Я твой персональный тренер и нутрициолог.\n\n"
		"— Помогу с тренировками под цель и уровень 💪\n"
		"— Подберу питание и КБЖУ 🥗\n"
		"— Отвечу на вопросы коротко и по делу ✨\n\n"
		"Отправь свой запрос или цели — и я подберу лучшие программы тренировок под твой запрос."
	)
	if settings.bot_logo_url:
		try:
			msg = await context.bot.send_photo(
				chat_id=update.effective_chat.id,
				photo=settings.bot_logo_url,
				caption=welcome,
				parse_mode=ParseMode.HTML,
				reply_markup=_main_menu_kb(),
			)
			_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
		except Exception:
			msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
			_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	else:
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)

	if update.message:
		await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	text = (
		"Выбери раздел в меню ниже или отправь голос/текст.\n"
		"Я подберу тренировку, меню на неделю и помогу с КБЖУ."
	)
	await _cleanup_chat_messages(context, update.effective_chat.id)
	msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_main_menu_kb())
	_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	if update.message:
		await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)


async def _reply_with_llm(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str) -> None:
	categories = build_categories(None)
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
			categories = build_categories(user)
	await _cleanup_chat_messages(context, update.effective_chat.id)
	if not settings.feature_llm:
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="LLM отключён. Включите FEATURE_LLM=1.")
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
		return
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
					categories_json=json.dumps(categories, ensure_ascii=False),
					response_text=reply_text,
					usage=usage,
				)
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	except OpenRouterError as e:
		logging.getLogger("llm").error("OpenRouter error: %s", e)
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="Сервис рекомендаций временно недоступен. Попробуй позже 🙏", reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if not update.message or not update.message.text:
		return
	user_text = update.message.text.strip()
	await _reply_with_llm(update, context, user_text)
	await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if not update.message or not update.message.voice:
		return
	if not settings.feature_asr:
		await help_command(update, context)
		if update.message:
			await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)
		return
	voice = update.message.voice
	with tempfile.TemporaryDirectory() as td:
		dl_path = Path(td) / f"{voice.file_unique_id}.oga"
		try:
			file = await context.bot.get_file(voice.file_id)
			await file.download_to_drive(custom_path=str(dl_path))
		except Exception as e:
			logging.getLogger("download").error("Failed to download voice: %s", e)
			await help_command(update, context)
			if update.message:
				await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)
			return
		try:
			text, _conf = await transcribe_audio(dl_path)
		except Exception:
			await help_command(update, context)
			if update.message:
				await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)
			return
	await _reply_with_llm(update, context, text)
	if update.message:
		await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	query = update.callback_query
	if not query:
		return
	await query.answer()
	data = query.data or ""
	_ephemeral_messages.setdefault(query.message.chat_id, []).append(query.message.message_id)
	if data == "menu_profile":
		text = "Профиль: укажи пол, рост, вес, цель, инвентарь. Это поможет точнее подбирать тренировки и питание."
		await _cleanup_chat_messages(context, update.effective_chat.id)
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	elif data == "menu_workouts":
		await _reply_with_llm(update, context, "Сгенерируй 'тренировку на сегодня' кратко: 5-7 упражнений, подходы/повторы/отдых, разминка и заминка. Учитывай безопасность. Тон: дружелюбный, Пиши, сокращай.")
	elif data == "menu_week":
		await _reply_with_llm(update, context, "Составь 'меню на неделю' кратко: для каждого дня 3-4 приёма пищи, с КБЖУ (суммарно/день) и короткими рецептами. Учитывай диету/аллергии, Пиши, сокращай.")
	elif data == "menu_ai_kbzhu_photo":
		await _cleanup_chat_messages(context, update.effective_chat.id)
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="Пришли фото блюда — оценю КБЖУ и дам советы 🍽️", reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	elif data == "menu_support":
		await _cleanup_chat_messages(context, update.effective_chat.id)
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="Поддержка: опиши проблему или цель — отвечу и помогу 💬", reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	elif data == "menu_loyalty":
		await _cleanup_chat_messages(context, update.effective_chat.id)
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="Бонусы: за активность и отзывы — баллы и плюсы. Скоро подробнее 🎁", reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	else:
		await help_command(update, context)


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