from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils.chat_manager import cleanup_previous_messages, track_message
from services.photo_nutrition import analyze_food_photo


async def handle_photo_nutrition(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработчик кнопки 'AI КБЖУ по фото'"""
	await cleanup_previous_messages(update, context)
	if update.effective_chat:
		context.chat_data["last_chat_id"] = update.effective_chat.id

	text = """
📸 *AI анализ питания по фото*

Отправьте фото вашего блюда, и я проанализирую:
• Калорийность
• Белки, жиры, углеводы
• Примерный вес порции
• Пищевую ценность

📝 *Как сделать хорошее фото:*
1. Хорошее освещение
2. Блюдо в центре кадра
3. Вид сверху или под углом 45°
4. Избегайте бликов и теней

⚠️ *Ограничения:*
• Сложные многокомпонентные блюда
• Нетипичные рецепты
• Плохое качество фото
"""

	keyboard = [
		[InlineKeyboardButton("📸 Отправить фото", callback_data="send_photo")],
		[InlineKeyboardButton("❓ Как это работает?", callback_data="how_it_works")],
		[InlineKeyboardButton("📊 Последние анализы", callback_data="recent_analyses")],
		[InlineKeyboardButton("↩️ Назад в меню", callback_data="menu_root")],
	]

	reply_markup = InlineKeyboardMarkup(keyboard)

	message = await context.bot.send_message(
		chat_id=update.effective_chat.id,
		text=text,
		reply_markup=reply_markup,
		parse_mode='Markdown'
	)

	# Устанавливаем состояние ожидания фото
	context.user_data['waiting_for_photo'] = True
	await track_message(context, message.message_id)


async def handle_food_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработчик загруженного фото еды"""
	if not context.user_data.get('waiting_for_photo', False):
		return

	# Сбрасываем состояние ожидания
	context.user_data['waiting_for_photo'] = False

	# Показываем сообщение о обработке
	processing_msg = await context.bot.send_message(
		chat_id=update.effective_chat.id,
		text="🔄 Анализирую фото...",
		parse_mode='Markdown'
	)

	# Анализ фото через AI
	photo_file = await update.message.photo[-1].get_file()
	analysis = await analyze_food_photo(photo_file.file_path)

	# Удаляем сообщение о обработке
	await context.bot.delete_message(
		chat_id=update.effective_chat.id,
		message_id=processing_msg.message_id
	)

	# Отправляем результаты анализа
	text = f"""
📊 *Результаты анализа*

🍽 *Блюдо:* {analysis['dish_name']}
⚖️ *Вес порции:* ~{analysis['weight']}г

📈 *Пищевая ценность:*
• Калории: {analysis['calories']} ккал
• Белки: {analysis['protein']}г
• Жиры: {analysis['fat']}г
• Углеводы: {analysis['carbs']}г

💡 *Рекомендации:*
{analysis['recommendations']}
"""

	keyboard = [
		[InlineKeyboardButton("✅ Добавить в дневник", callback_data=f"add_to_diary:{analysis['id']}")],
		[InlineKeyboardButton("🔄 Проанализировать другое фото", callback_data="photo_nutrition")],
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