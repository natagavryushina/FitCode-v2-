from __future__ import annotations

import asyncio
import logging
import json
import tempfile
from pathlib import Path
from typing import Dict, List
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatAction
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
from services.planner import ensure_week_workouts, ensure_week_meals
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.reminder import setup_scheduler

# In-memory store of last bot messages per chat for cleanup
_ephemeral_messages: Dict[int, List[int]] = {}
_hw_waiting: Dict[int, bool] = {}

# Minimal dictionaries for profile selections
PROFILE_SEX = {"male": "Муж", "female": "Жен"}
PROFILE_LEVEL = {"beginner": "Новичок", "intermediate": "Средний", "advanced": "Продвинутый"}
GOAL_CHOICES = ["похудение", "набор_массы", "выносливость", "здоровье", "осанка"]
EQUIPMENT_CHOICES = ["гантели", "штанга", "турник", "резинки", "без_инвентаря"]


def format_big_message(title: str, body: str) -> str:
	return f"<b>{title}</b>\n\n{body}"


async def on_startup() -> None:
	if settings.feature_db:
		Base.metadata.create_all(bind=engine)


# Healthcheck endpoint for uptime probes and quick diagnostics
async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	await context.bot.send_message(
		chat_id=update.effective_chat.id,
		text="OK",
		parse_mode=ParseMode.HTML,
	)


# Global error handler to avoid crashing on unhandled exceptions
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
	logger = logging.getLogger("errors")
	logger.exception("Unhandled error: %s", context.error)
	try:
		if isinstance(update, Update) and update.effective_chat:
			await context.bot.send_message(
				chat_id=update.effective_chat.id,
				text="Произошла ошибка. Уже чиним 🙏",
				parse_mode=ParseMode.HTML,
			)
	except Exception:
		pass


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


def _days_kb(prefix: str) -> InlineKeyboardMarkup:
	rows = []
	row = []
	for i in range(7):
		btn = InlineKeyboardButton(text=f"Д{i+1}", callback_data=f"{prefix}{i}")
		row.append(btn)
		if len(row) == 4:
			rows.append(row)
			row = []
	if row:
		rows.append(row)
	rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_root")])
	return InlineKeyboardMarkup(rows)


def _workout_day_kb(plan_id: int, day_index: int) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup([
		[
			InlineKeyboardButton(text="✅ Выполнено", callback_data=f"workout_done_{plan_id}_{day_index}"),
			InlineKeyboardButton(text="⬅️ К дням", callback_data="menu_workouts"),
		]
	])


def _profile_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup([
		[InlineKeyboardButton(text="⚧ Пол", callback_data="profile_sex"), InlineKeyboardButton(text="📈 Уровень", callback_data="profile_level")],
		[InlineKeyboardButton(text="📏 Рост/Вес", callback_data="profile_hw")],
		[InlineKeyboardButton(text="🎯 Цели", callback_data="profile_goals"), InlineKeyboardButton(text="🏋️ Инвентарь", callback_data="profile_eq")],
		[InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_root")],
	])


def _toggle_list_kb(prefix: str, choices: List[str], selected: set[str]) -> InlineKeyboardMarkup:
	rows: List[List[InlineKeyboardButton]] = []
	row: List[InlineKeyboardButton] = []
	for idx, item in enumerate(choices):
		is_on = item in selected
		label = ("✅ " if is_on else "⬜ ") + item.replace("_", " ")
		row.append(InlineKeyboardButton(text=label, callback_data=f"{prefix}{item}"))
		if len(row) == 2:
			rows.append(row)
			row = []
	if row:
		rows.append(row)
	rows.append([InlineKeyboardButton(text="Готово", callback_data=f"{prefix}done")])
	rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")])
	return InlineKeyboardMarkup(rows)


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
			sent = await _send_photo_safe(context, update.effective_chat.id, img, welcome, _main_menu_kb())
			if not sent:
				msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
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


async def _reply_with_llm(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, title: str, image_topic: str | None = None, fallback_body: str | None = None) -> None:
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
	await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
	if not settings.feature_llm:
		body = fallback_body or "LLM отключён. Включите FEATURE_LLM=1."
		msg_text = format_big_message(title, html.escape(body))
		msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=msg_text, parse_mode=ParseMode.HTML, reply_markup=_main_menu_kb())
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
				safe_title = html.escape(title)
				caption = safe_title if len(big) > 1000 else big
				ok = await _send_photo_safe(context, update.effective_chat.id, img, caption, _main_menu_kb())
				if ok and len(big) > 1000:
					await _send_text_big(context, update.effective_chat.id, big, _main_menu_kb())
				if ok:
					return
		await _send_text_big(context, update.effective_chat.id, big, _main_menu_kb())
	except (OpenRouterError, Exception) as e:
		logging.getLogger("llm").exception("LLM error: %s", e)
		body = fallback_body or "LLM временно недоступен. Попробуй позже 🙏"
		big = format_big_message(title, html.escape(body))
		if image_topic:
			img = get_image_url(image_topic)
			if img:
				cap = big if len(big) <= 1000 else html.escape(title)
				ok = await _send_photo_safe(context, update.effective_chat.id, img, cap, _main_menu_kb())
				if ok and len(big) > 1000:
					await _send_text_big(context, update.effective_chat.id, big, _main_menu_kb())
				if ok:
					return
		await _send_text_big(context, update.effective_chat.id, big, _main_menu_kb())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if not update.message or not update.message.text:
		return
	user_text = update.message.text.strip()
	# Handle HW input if awaiting
	if _hw_waiting.get(update.effective_chat.id):
		parts = user_text.replace(",", ".").split()
		if len(parts) >= 2:
			try:
				h = int(float(parts[0]))
				w = int(float(parts[1]))
				if 100 <= h <= 250 and 35 <= w <= 300:
					with session_scope() as s:
						user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
						repo.update_user_fields(s, user, height_cm=h, weight_kg=w)
					_hw_waiting[update.effective_chat.id] = False
					await _cleanup_chat_messages(context, update.effective_chat.id)
					await _send_text_big(context, update.effective_chat.id, format_big_message("Готово", f"Рост: {h} см, Вес: {w} кг"), _profile_kb())
					await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)
					return
			except Exception:
				pass
		await _send_text_big(context, update.effective_chat.id, format_big_message("Ошибка", "Формат: 180 75. Попробуй ещё раз."), InlineKeyboardMarkup([[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]]))
		await _safe_delete_message(context, update.effective_chat.id, update.message.message_id)
		return
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
	try:
		data = query.data or ""
		_ephemeral_messages.setdefault(query.message.chat_id, []).append(query.message.message_id)
		if data == "menu_profile":
			# Show profile menu
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
			text = format_big_message("Личный кабинет", "Измени параметры профиля: пол, уровень, рост/вес, цели и инвентарь.")
			await _cleanup_chat_messages(context, update.effective_chat.id)
			await _send_text_big(context, update.effective_chat.id, text, _profile_kb())
		elif data == "profile_sex":
			kb = InlineKeyboardMarkup([[InlineKeyboardButton(text="Муж", callback_data="profile_sex_set_male"), InlineKeyboardButton(text="Жен", callback_data="profile_sex_set_female")], [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]])
			await _cleanup_chat_messages(context, update.effective_chat.id)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Пол", "Выбери пол"), kb)
		elif data.startswith("profile_sex_set_"):
			sex = data.split("_")[-1]
			if sex not in PROFILE_SEX:
				await help_command(update, context)
				return
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
				repo.update_user_fields(s, user, sex=sex)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Готово", f"Пол: {sex}"), _profile_kb())
		elif data == "profile_level":
			kb = InlineKeyboardMarkup([[InlineKeyboardButton(text=lbl, callback_data=f"profile_level_set_{key}") for lbl, key in [("Новичок","beginner"),("Средний","intermediate"),("Продвинутый","advanced")]], [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]])
			await _cleanup_chat_messages(context, update.effective_chat.id)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Уровень", "Выбери тренировочный уровень"), kb)
		elif data.startswith("profile_level_set_"):
			lvl = data.split("_")[-1]
			if lvl not in PROFILE_LEVEL:
				await help_command(update, context)
				return
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
				repo.update_user_fields(s, user, level=lvl)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Готово", f"Уровень: {lvl}"), _profile_kb())
		elif data == "profile_hw":
			await _cleanup_chat_messages(context, update.effective_chat.id)
			_hw_waiting[update.effective_chat.id] = True
			await _send_text_big(context, update.effective_chat.id, format_big_message("Рост/Вес", "Отправь текстом в формате: 180 75"), InlineKeyboardMarkup([[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]]))
		elif data == "profile_goals":
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
				prefs = json.loads(user.preferences_json or "{}")
				selected = set(prefs.get("goals", []))
			await _cleanup_chat_messages(context, update.effective_chat.id)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Цели", "Выбери одну или несколько целей"), _toggle_list_kb("goals_", GOAL_CHOICES, selected))
		elif data.startswith("goals_"):
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
				prefs = json.loads(user.preferences_json or "{}")
				selected = set(prefs.get("goals", []))
				val = data.split("_")[-1]
				if val == "done":
					repo.set_user_list_pref(s, user, "goals", list(selected))
					await _send_text_big(context, update.effective_chat.id, format_big_message("Готово", "Цели сохранены"), _profile_kb())
					return
				if val in GOAL_CHOICES:
					if val in selected:
						selected.remove(val)
					else:
						selected.add(val)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Цели", "Выбери одну или несколько целей"), _toggle_list_kb("goals_", GOAL_CHOICES, selected))
		elif data == "profile_eq":
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
				prefs = json.loads(user.preferences_json or "{}")
				selected = set(prefs.get("equipment", []))
			await _cleanup_chat_messages(context, update.effective_chat.id)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Инвентарь", "Отметь доступный инвентарь"), _toggle_list_kb("eq_", EQUIPMENT_CHOICES, selected))
		elif data.startswith("eq_"):
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
				prefs = json.loads(user.preferences_json or "{}")
				selected = set(prefs.get("equipment", []))
				val = data.split("_")[-1]
				if val == "done":
					repo.set_user_list_pref(s, user, "equipment", list(selected))
					await _send_text_big(context, update.effective_chat.id, format_big_message("Готово", "Инвентарь сохранён"), _profile_kb())
					return
				if val in EQUIPMENT_CHOICES:
					if val in selected:
						selected.remove(val)
					else:
						selected.add(val)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Инвентарь", "Отметь доступный инвентарь"), _toggle_list_kb("eq_", EQUIPMENT_CHOICES, selected))
		elif data == "menu_workouts":
			# Ensure plan and show today
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
			if not user:
				await help_command(update, context)
				return
			plan_id, today_idx = await ensure_week_workouts(user)
			with session_scope() as s:
				day = repo.get_workout_day(s, plan_id, today_idx)
				title = day.title if day else f"День {today_idx+1}"
				body = day.content_text if day else "Сегодня отдых/мобилити 20 мин"
			text = format_big_message(f"Тренировки — {title}", html.escape(body))
			await _cleanup_chat_messages(context, update.effective_chat.id)
			img = get_image_url("workout")
			if img:
				ok = await _send_photo_safe(context, update.effective_chat.id, img, text if len(text) <= 1000 else "Тренировки", _days_kb("workout_day_"))
				if ok and len(text) > 1000:
					await _send_text_big(context, update.effective_chat.id, text, _days_kb("workout_day_"))
					return
			await _send_text_big(context, update.effective_chat.id, text, _days_kb("workout_day_"))
		elif data.startswith("workout_day_"):
			idx = int(data.split("_")[-1])
			user = None
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
			plan_id, _ = await ensure_week_workouts(user)
			with session_scope() as s2:
				day = repo.get_workout_day(s2, plan_id, idx)
				title = day.title if day else f"День {idx+1}"
				body = day.content_text if day else "Отдых/мобилити"
			text = format_big_message(f"Тренировки — {title}", html.escape(body))
			await _cleanup_chat_messages(context, update.effective_chat.id)
			await _send_text_big(context, update.effective_chat.id, text, _workout_day_kb(plan_id, idx))
		elif data.startswith("workout_done_"):
			_, _, plan_id_str, idx_str = data.split("_")
			plan_id = int(plan_id_str)
			idx = int(idx_str)
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
				repo.mark_workout_completed(s, user.id, plan_id, idx)
				repo.add_loyalty_points(s, user.id, 10)
			text = format_big_message("Отлично!", f"День {idx+1} отмечен как выполненный. +10 баллов 🎉")
			await _cleanup_chat_messages(context, update.effective_chat.id)
			await _send_text_big(context, update.effective_chat.id, text, _days_kb("workout_day_"))
		elif data == "menu_week":
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
			if not user:
				await help_command(update, context)
				return
			meal_plan_id, today_idx = await ensure_week_meals(user)
			with session_scope() as s:
				day = repo.get_meal_day(s, meal_plan_id, today_idx)
				title = day.title if day else f"День {today_idx+1}"
				body = day.content_text if day else "~2200 ккал, 3–4 приёма пищи"
			text = format_big_message(f"Меню — {title}", html.escape(body))
			await _cleanup_chat_messages(context, update.effective_chat.id)
			img = get_image_url("week")
			if img:
				ok = await _send_photo_safe(context, update.effective_chat.id, img, text if len(text) <= 1000 else "Меню недели", _days_kb("meals_day_"))
				if ok and len(text) > 1000:
					await _send_text_big(context, update.effective_chat.id, text, _days_kb("meals_day_"))
					return
			await _send_text_big(context, update.effective_chat.id, text, _days_kb("meals_day_"))
		elif data == "menu_ai_kbzhu_photo":
			await _cleanup_chat_messages(context, update.effective_chat.id)
			kb = InlineKeyboardMarkup([[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_root")]])
			text = format_big_message("AI КБЖУ по фото", "Отправь фото блюда, я оценю КБЖУ и дам рекомендации.")
			img = get_image_url("kbzhu")
			if img:
				ok = await _send_photo_safe(context, update.effective_chat.id, img, text if len(text) <= 1000 else "AI КБЖУ", kb)
				if ok and len(text) > 1000:
					await _send_text_big(context, update.effective_chat.id, text, kb)
					return
			await _send_text_big(context, update.effective_chat.id, text, kb)
		elif data == "menu_support":
			await _cleanup_chat_messages(context, update.effective_chat.id)
			kb = InlineKeyboardMarkup([[InlineKeyboardButton(text="📨 Написать в поддержку", callback_data="support_contact")],[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_root")]])
			await _send_text_big(context, update.effective_chat.id, format_big_message("Поддержка", "Опиши проблему — я помогу или передам оператору."), kb)
		elif data == "support_contact":
			await _cleanup_chat_messages(context, update.effective_chat.id)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Поддержка", "Напишите свой вопрос текстом или голосом. Мы ответим в ближайшее время."), InlineKeyboardMarkup([[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_support")]]))
		elif data == "menu_loyalty":
			with session_scope() as s:
				user = repo.get_or_create_user(s, str(update.effective_user.id), update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
				points = repo.get_loyalty_points(s, user.id)
			await _cleanup_chat_messages(context, update.effective_chat.id)
			kb = InlineKeyboardMarkup([[InlineKeyboardButton(text="🏆 Использовать баллы скоро", callback_data="menu_root")],[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_root")]])
			await _send_text_big(context, update.effective_chat.id, format_big_message("Бонусы", f"Твои баллы: {points} 🎉"), kb)
		elif data == "menu_root":
			await start_command(update, context)
		else:
			await _cleanup_chat_messages(context, update.effective_chat.id)
			await _send_text_big(context, update.effective_chat.id, format_big_message("Неизвестная команда", "Кнопка обновлена. Откройте меню и попробуйте снова."), _main_menu_kb())
	except Exception as e:
		logging.getLogger("cb").exception("Callback handling failed: %s", e)
		await _send_text_big(context, update.effective_chat.id, format_big_message("Упс", "Что-то пошло не так. Открой меню и попробуй ещё раз."), _main_menu_kb())


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


async def _send_photo_safe(context: ContextTypes.DEFAULT_TYPE, chat_id: int, photo_url: str, caption_html: str, reply_markup: InlineKeyboardMarkup | None) -> bool:
	try:
		msg = await context.bot.send_photo(chat_id=chat_id, photo=photo_url, caption=caption_html, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
		_ephemeral_messages.setdefault(chat_id, []).append(msg.message_id)
		return True
	except Exception as e:
		logging.getLogger("ui").warning("send_photo failed: %s", e)
		return False


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
	scheduler: AsyncIOScheduler | None = None
	if settings.feature_reminder:
		scheduler = AsyncIOScheduler()
		scheduler.start()
		setup_scheduler(scheduler, app.bot, settings.reminder_hour)

	app.add_handler(CommandHandler("start", start_command))
	app.add_handler(CommandHandler("help", help_command))
	app.add_handler(CommandHandler("health", health_command))
	app.add_handler(CallbackQueryHandler(handle_menu_callback))
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
	app.add_handler(MessageHandler(filters.VOICE, handle_voice))
	app.add_error_handler(error_handler)

	logger.info("Bot is starting (polling)...")
	await app.initialize()
	await app.start()
	try:
		await app.updater.start_polling()
		await asyncio.Event().wait()
	finally:
		await app.stop()
		await app.shutdown()
		if scheduler:
			scheduler.shutdown(wait=False)


if __name__ == "__main__":
	asyncio.run(run())