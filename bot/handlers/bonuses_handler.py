from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils.chat_manager import cleanup_previous_messages, track_message
from services.bonuses import get_user_bonuses, format_achievements


async def handle_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработчик кнопки 'Бонусы'"""
	await cleanup_previous_messages(update, context)
	if update.effective_chat:
		context.chat_data["last_chat_id"] = update.effective_chat.id

	user_id = update.effective_user.id
	bonuses = await get_user_bonuses(user_id)

	text = f"""
🎁 *Бонусная программа*

💰 *Ваши бонусы:* {bonuses['points']} баллов

🏆 *Достижения:*
{format_achievements(bonuses['achievements'])}

🎯 *Текущие акции:*
• Приведи друга +100 баллов
• 7 дней подряд +50 баллов
• 10 тренировок +30 баллов

🛍 *Магазин наград:*
• 100 баллов - персональная тренировка
• 200 баллов - план питания на месяц
• 500 баллов - консультация нутрициолога
"""

	keyboard = [
		[InlineKeyboardButton("🎁 Магазин наград", callback_data="rewards_shop")],
		[InlineKeyboardButton("🏆 Мои достижения", callback_data="my_achievements")],
		[InlineKeyboardButton("📊 История начислений", callback_data="bonus_history")],
		[InlineKeyboardButton("👫 Пригласить друга", callback_data="invite_friend")],
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