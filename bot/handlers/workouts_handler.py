from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils.chat_manager import cleanup_previous_messages, track_message
from services.workouts import get_user_workouts


async def handle_workouts(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработчик кнопки 'Тренировки'"""
	await cleanup_previous_messages(update, context)
	if update.effective_chat:
		context.chat_data["last_chat_id"] = update.effective_chat.id

	user_id = update.effective_user.id
	workouts = await get_user_workouts(user_id)

	text = (
		"""
💪 *Ваши тренировки*

Выберите тип тренировки или просмотрите расписание:
"""
	)

	keyboard = [
		[InlineKeyboardButton("🏋️‍♂️ Силовые тренировки", callback_data="strength_workouts")],
		[InlineKeyboardButton("🏃‍♂️ Кардио тренировки", callback_data="cardio_workouts")],
		[InlineKeyboardButton("📅 Расписание на неделю", callback_data="workout_schedule")],
		[InlineKeyboardButton("✅ Отметить выполнение", callback_data="log_workout")],
		[InlineKeyboardButton("📊 История тренировок", callback_data="workout_history")],
		[InlineKeyboardButton("↩️ Назад в меню", callback_data="menu_root")],
	]

	reply_markup = InlineKeyboardMarkup(keyboard)

	message = await context.bot.send_message(
		chat_id=update.effective_chat.id,
		text=text,
		reply_markup=reply_markup,
		parse_mode='Markdown'
	)

	await track_message(context, message.message_id)