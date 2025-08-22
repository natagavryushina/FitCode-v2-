from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils.chat_manager import cleanup_previous_messages, track_message


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработчик главного меню"""
	await cleanup_previous_messages(update, context)
	if update.effective_chat:
		context.chat_data["last_chat_id"] = update.effective_chat.id

	keyboard = [
		[InlineKeyboardButton("🏠 Личный кабинет", callback_data="menu_profile")],
		[InlineKeyboardButton("💪 Тренировки", callback_data="menu_workouts")],
		[InlineKeyboardButton("📅 Меню на неделю", callback_data="menu_week")],
		[InlineKeyboardButton("📸 AI КБЖУ по фото", callback_data="menu_ai_kbzhu_photo")],
		[InlineKeyboardButton("🆘 Поддержка", callback_data="menu_support")],
		[InlineKeyboardButton("🎁 Бонусы", callback_data="menu_loyalty")],
	]

	reply_markup = InlineKeyboardMarkup(keyboard)

	message = await context.bot.send_message(
		chat_id=update.effective_chat.id,
		text="🏠 <b>Главное меню</b>\n\nВыберите раздел:",
		reply_markup=reply_markup,
		parse_mode="HTML",
	)

	await track_message(context, message.message_id)