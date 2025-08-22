from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils.chat_manager import cleanup_previous_messages, track_message
from services.weekly_menu import generate_weekly_menu


async def handle_weekly_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработчик кнопки 'Меню на неделю'"""
	await cleanup_previous_messages(update, context)
	if update.effective_chat:
		context.chat_data["last_chat_id"] = update.effective_chat.id

	user_id = update.effective_user.id
	weekly_menu = await generate_weekly_menu(user_id)

	text = f"""
📅 *Ваше меню на неделю*

🍽 *План питания разработан с учетом:*
• Цели: {weekly_menu['goal']}
• Суточная норма: {weekly_menu['calories']} ккал
• БЖУ: {weekly_menu['protein']}г белка, {weekly_menu['carbs']}г углеводов, {weekly_menu['fat']}г жиров

📋 *Дни недели:*
"""

	# Добавляем дни недели
	days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
	for i, day in enumerate(days):
		text += f"• {day}: {weekly_menu['days'][i]['calories']} ккал\\n"

	keyboard = [
		[InlineKeyboardButton("📋 Понедельник", callback_data="menu_monday")],
		[InlineKeyboardButton("📋 Вторник", callback_data="menu_tuesday")],
		[InlineKeyboardButton("📋 Среда", callback_data="menu_wednesday")],
		[InlineKeyboardButton("📋 Четверг", callback_data="menu_thursday")],
		[InlineKeyboardButton("📋 Пятница", callback_data="menu_friday")],
		[InlineKeyboardButton("📋 Суббота", callback_data="menu_saturday")],
		[InlineKeyboardButton("📋 Воскресенье", callback_data="menu_sunday")],
		[InlineKeyboardButton("🔄 Сгенерировать новое меню", callback_data="generate_new_menu")],
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