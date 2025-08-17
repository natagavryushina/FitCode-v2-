from __future__ import annotations

import asyncio
import logging
import json
import tempfile
from pathlib import Path
from typing import Dict, List
import html
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
from services.images import get_image_url

# In-memory store of last bot messages per chat for cleanup
_ephemeral_messages: Dict[int, List[int]] = {}


BIG_BANNER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def format_big_message(title: str, body: str) -> str:
	return (
		f"{BIG_BANNER}\n"
		f"<b>{title}</b>\n"
		f"{BIG_BANNER}\n\n"
		f"{body}\n\n"
		f"{BIG_BANNER}"
	)


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
				InlineKeyboardButton(text="👤 ЛИЧНЫЙ КАБИНЕТ", callback_data="menu_profile"),
				InlineKeyboardButton(text="🏋️ ТРЕНИРОВКИ", callback_data="menu_workouts"),
				InlineKeyboardButton(text="📅 МЕНЮ НЕДЕЛЮ", callback_data="menu_week"),
			],
			[
				InlineKeyboardButton(text="🤖 AI КБЖУ ПО ФОТО", callback_data="menu_ai_kbzhu_photo"),
				InlineKeyboardButton(text="🆘 ПОДДЕРЖКА", callback_data="menu_support"),
				InlineKeyboardButton(text="🎁 БОНУСЫ", callback_data="menu_loyalty"),
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
	body = (
		"— Помогу с тренировками под цель и уровень 💪\n"
		"— Подберу питание и КБЖУ 🥗\n"
		"— Отвечу на вопросы коротко и по делу ✨\n\n"
		"Отправь свой запрос или цели — и я подберу лучшие программы тренировок под твой запрос."
	)
	welcome = format_big_message("Привет! Я твой тренер и нутрициолог", body)
	if settings.bot_logo_url:
		try:
			msg = await context.bot.send_photo(
				chat_id=update.effective_chat.id,
				photo=settings.bot_logo_url or get_image_url("welcome"),
				caption=welcome,
				parse_mode=ParseMode.HTML,
				reply_markup=_main_menu_kb(),
			)
			_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
		except Exception:
			msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
			_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	else:
		img = get_image_url("welcome")
		if img:
			msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=welcome, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
			_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
		else:
			msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
			_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)

	if update.message:
		await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	text = format_big_message(
		"Как начать",
		"Выбери раздел ниже или отправь голос/текст. Я подберу тренировку, меню на неделю и помогу с КБЖУ.",
	)
	await _cleanup_chat_messages(context, update.effective_chat.id)
	msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_main_menu_kb(), parse_mode=ParseMode.HTML)
	_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	if update.message:
		await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)


async def _reply_with_llm(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, title: str, image_topic: str | None = None) -> None:
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
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=format_big_message("LLM отключён", "Включите FEATURE_LLM=1."), parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
		return
	try:
		reply_text, usage = await chat_completion(categories, user_text)
		safe_body = html.escape(reply_text or "")
		big = format_big_message(title, safe_body)
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
		if image_topic:
			img = get_image_url(image_topic)
			if img:
				# Telegram photo caption limit ~1024 chars
				safe_title = html.escape(title)
				caption = safe_title if len(big) > 1000 else big
				msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=caption, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
				_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
				if len(big) > 1000:
					await _send_text_big(context, update.effective_chat.id, big, _main_menu_kb())
				return
		await _send_text_big(context, update.effective_chat.id, big, _main_menu_kb())
	except OpenRouterError as e:
		logging.getLogger("llm").error("OpenRouter error: %s", e)
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=format_big_message("Ошибка", "Сервис рекомендаций временно недоступен. Попробуй позже 🙏"), parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	except Exception as e:
		logging.getLogger("llm").exception("Unexpected error while replying with LLM: %s", e)
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=format_big_message("Не удалось отправить ответ", "Произошёл сбой форматирования. Попробуй ещё раз."), parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if not update.message or not update.message.text:
		return
	user_text = update.message.text.strip()
	await _reply_with_llm(update, context, user_text, title="Ответ готов ✨")
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
	await _reply_with_llm(update, context, text, title="Расшифровал и ответил 🎤")
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
		text = format_big_message("Личный кабинет", "Укажи пол, рост, вес, цель и инвентарь — так рекомендации будут точнее.")
		await _cleanup_chat_messages(context, update.effective_chat.id)
		img = get_image_url("profile")
		if img:
			msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
		else:
			msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_main_menu_kb(), parse_mode=ParseMode.HTML)
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	elif data == "menu_workouts":
		prompt = "Сгенерируй 'тренировку на сегодня' кратко: 5-7 упражнений, подходы/повторы/отдых, разминка и заминка. Учитывай безопасность. Тон: дружелюбный, Пиши, сокращай."
		await _reply_with_llm(update, context, prompt, title="Тренировка на сегодня 💪", image_topic="workout")
	elif data == "menu_week":
		prompt = "Составь 'меню на неделю' кратко: для каждого дня 3-4 приёма пищи, с КБЖУ (суммарно/день) и короткими рецептами. Учитывай диету/аллергии, Пиши, сокращай."
		await _reply_with_llm(update, context, prompt, title="Меню на неделю 🥗", image_topic="week")
	elif data == "menu_ai_kbzhu_photo":
		text = format_big_message("AI КБЖУ по фото", "Пришли фото блюда — оценю КБЖУ и дам советы 🍽️")
		await _cleanup_chat_messages(context, update.effective_chat.id)
		img = get_image_url("kbzhu")
		if img:
			msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
		else:
			msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_main_menu_kb(), parse_mode=ParseMode.HTML)
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	elif data == "menu_support":
		text = format_big_message("Поддержка", "Опиши проблему или цель — отвечу и помогу 💬")
		await _cleanup_chat_messages(context, update.effective_chat.id)
		img = get_image_url("support")
		if img:
			msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
		else:
			msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_main_menu_kb(), parse_mode=ParseMode.HTML)
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	elif data == "menu_loyalty":
		text = format_big_message("Бонусная программа", "Баллы начисляются за активность и отзывы. Скоро подробнее 🎁")
		await _cleanup_chat_messages(context, update.effective_chat.id)
		img = get_image_url("loyalty")
		if img:
			msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
		else:
			msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_main_menu_kb(), parse_mode=ParseMode.HTML)
		_ephemeral_messages.setdefault(update.effective_chat.id, []).append(msg.message_id)
	else:
		await help_command(update, context)


MAX_TG_TEXT = 4000


def _split_text_chunks(text: str, limit: int = MAX_TG_TEXT) -> List[str]:
	if len(text) <= limit:
		return [text]
	chunks: List[str] = []
	start = 0
	while start < len(text):
		end = min(start + limit, len(text))
		# try split on nearest newline for readability
		newline = text.rfind("\n", start, end)
		if newline != -1 and newline > start + 1000:
			end = newline
		chunks.append(text[start:end])
		start = end
	return chunks


async def _send_text_big(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | None) -> None:
	parts = _split_text_chunks(text)
	for part in parts:
		msg = await context.bot.send_message(chat_id=chat_id, text=part, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
		_ephemeral_messages.setdefault(chat_id, []).append(msg.message_id)


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