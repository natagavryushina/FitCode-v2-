from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import Optional

async def cleanup_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка предыдущих сообщений"""
    # Очистка будет выполнена в основном модуле
    pass

async def track_message(context: ContextTypes.DEFAULT_TYPE, message_id: int):
    """Отслеживание сообщений для очистки"""
    # Отслеживание будет выполнено в основном модуле
    pass

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Поддержка'"""
    await cleanup_previous_messages(update, context)
    
    text = """
🆘 *Поддержка*

Здесь вы можете получить помощь по работе с ботом:

❓ *Частые вопросы:*
• Как изменить цель тренировок?
• Почему не генерируется меню?
• Как работает анализ фото?
• Как отслеживать прогресс?

📞 *Способы связи:*
• Чат с поддержкой: @FitCodesupport
• Ответ в течение 24 часов
• Email: support@fitbot.com

🕒 *Время работы поддержки:*
Пн-Пт: 9:00-18:00
Сб-Вс: 10:00-16:00

💬 *Для быстрой помощи напишите напрямую:* 
👉 @FitCodesupport 👈
"""
    
    keyboard = [
        [InlineKeyboardButton("💬 Написать в поддержку", url="https://t.me/FitCodesupport")],
        [InlineKeyboardButton("❓ Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton("📋 FAQ", callback_data="faq")],
        [InlineKeyboardButton("↩️ Назад в меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)

async def handle_contact_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик прямой связи с поддержкой"""
    await cleanup_previous_messages(update, context)
    
    text = """
💬 *Незамедлительная поддержка*

Для быстрого решения вопроса напишите напрямую нашему менеджеру поддержки:

👉 *@FitCodesupport* 👈

📋 *Чтобы мы могли помочь быстрее, укажите:*
1. Ваш логин/номер в боте
2. Суть проблемы или вопроса
3. Скриншоты (если есть)

⏱ *Среднее время ответа:*
• Простые вопросы: до 1 часа
• Сложные вопросы: до 24 часов
"""
    
    keyboard = [
        [InlineKeyboardButton("💬 Написать @FitCodesupport", url="https://t.me/FitCodesupport")],
        [InlineKeyboardButton("📱 Открыть Telegram", url="tg://resolve?domain=FitCodesupport")],
        [InlineKeyboardButton("↩️ Назад к поддержке", callback_data="support")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)


async def handle_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик FAQ"""
    await cleanup_previous_messages(update, context)
    
    text = """
📋 *Часто задаваемые вопросы*

❓ *Как изменить цель тренировок?*
Перейдите в "Личный кабинет" → "Цели" и выберите новые цели.

❓ *Почему не генерируется меню?*
Убедитесь, что заполнены все необходимые данные в профиле: пол, уровень, рост/вес, цели.

❓ *Как работает анализ фото?*
Отправьте фото еды в раздел "AI КБЖУ ПО ФОТО", и бот автоматически определит калории и макронутриенты.

❓ *Как отслеживать прогресс?*
В разделе "Тренировки" отмечайте выполненные дни, накапливайте баллы лояльности.

❓ *Можно ли изменить время напоминаний?*
Да, в настройках можно изменить время уведомлений о тренировках.

❓ *Как работает система баллов?*
За каждую выполненную тренировку +10 баллов, за достижение целей +50 баллов.
"""
    
    keyboard = [
        [InlineKeyboardButton("💬 Написать в поддержку", url="https://t.me/FitCodesupport")],
        [InlineKeyboardButton("↩️ Назад к поддержке", callback_data="support")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)


async def handle_ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик задавания вопроса"""
    await cleanup_previous_messages(update, context)
    
    text = """
❓ *Задать вопрос*

Для получения персональной помощи по вашему вопросу:

1️⃣ *Напишите напрямую:* @FitCodesupport
2️⃣ *Укажите в сообщении:*
   • Ваш логин в боте
   • Суть вопроса/проблемы
   • Что уже пробовали сделать

3️⃣ *Приложите скриншоты* (если есть)

⏱ *Время ответа:*
• Простые вопросы: до 1 часа
• Сложные вопросы: до 24 часов

💡 *Совет:* Сначала проверьте FAQ - возможно, там уже есть ответ на ваш вопрос.
"""
    
    keyboard = [
        [InlineKeyboardButton("💬 Написать @FitCodesupport", url="https://t.me/FitCodesupport")],
        [InlineKeyboardButton("📋 Посмотреть FAQ", callback_data="faq")],
        [InlineKeyboardButton("↩️ Назад к поддержке", callback_data="support")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)