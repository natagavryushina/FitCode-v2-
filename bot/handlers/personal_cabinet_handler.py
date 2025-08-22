from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils.chat_manager import cleanup_previous_messages, track_message
from services.user_profile import get_user_data


async def handle_personal_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработчик кнопки 'Личный кабинет'"""
	await cleanup_previous_messages(update, context)
	if update.effective_chat:
		context.chat_data["last_chat_id"] = update.effective_chat.id

	user_data = await get_user_data(update.effective_user.id)

	text = f"""
🏠 *Ваш личный кабинет*

📊 *Основная информация:*
• Имя: {user_data['name']}
• Цель: {user_data['goal']}
• Уровень: {user_data['level']}
• Возраст: {user_data['age']}
• Вес: {user_data['weight']} кг
• Рост: {user_data['height']} см

🎯 *Прогресс:*
• Текущая streak: {user_data['streak']} дней
• Выполнено тренировок: {user_data['workouts_completed']}
• Достижений: {user_data['achievements']}
	"""

	keyboard = [
		[InlineKeyboardButton("✏️ Редактировать данные", callback_data="profile_edit")],
		[InlineKeyboardButton("📊 Подробная статистика", callback_data="profile_stats")],
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