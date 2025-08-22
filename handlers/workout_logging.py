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

async def handle_log_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Внести тренировку'"""
    await cleanup_previous_messages(update, context)
    
    text = """
✅ *Внесение выполненной тренировки*

Выберите тип тренировки, которую вы выполнили:
"""
    
    keyboard = [
        [InlineKeyboardButton("🏋️‍♂️ Силовая тренировка", callback_data="log_strength")],
        [InlineKeyboardButton("🏃‍♂️ Кардио тренировка", callback_data="log_cardio")],
        [InlineKeyboardButton("🧘‍♂️ Йога/Растяжка", callback_data="log_yoga")],
        [InlineKeyboardButton("⚡️ Функциональная тренировка", callback_data="log_functional")],
        [InlineKeyboardButton("📅 Из плана тренировок", callback_data="log_from_plan")],
        [InlineKeyboardButton("↩️ Назад к тренировкам", callback_data="workouts")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)


async def handle_log_strength_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик силовой тренировки"""
    await cleanup_previous_messages(update, context)
    
    # Устанавливаем состояние для сбора данных о силовой тренировке
    context.user_data['logging_workout'] = {
        'type': 'strength',
        'step': 'duration',
        'data': {}
    }
    
    text = """
🏋️‍♂️ *Силовая тренировка*

Сколько минут длилась ваша тренировка?

💡 *Примеры:*
• 45 (45 минут)
• 60 (1 час)
• 90 (1.5 часа)
"""
    
    keyboard = [
        [InlineKeyboardButton("❌ Отменить", callback_data="log_workout")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)


async def handle_log_cardio_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кардио тренировки"""
    await cleanup_previous_messages(update, context)
    
    # Устанавливаем состояние для сбора данных о кардио тренировке
    context.user_data['logging_workout'] = {
        'type': 'cardio',
        'step': 'duration',
        'data': {}
    }
    
    text = """
🏃‍♂️ *Кардио тренировка*

Сколько минут длилась ваша тренировка?

💡 *Примеры:*
• 30 (30 минут)
• 45 (45 минут)
• 60 (1 час)
"""
    
    keyboard = [
        [InlineKeyboardButton("❌ Отменить", callback_data="log_workout")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)


async def handle_log_yoga_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик йоги/растяжки"""
    await cleanup_previous_messages(update, context)
    
    # Устанавливаем состояние для сбора данных о йоге
    context.user_data['logging_workout'] = {
        'type': 'yoga',
        'step': 'duration',
        'data': {}
    }
    
    text = """
🧘‍♂️ *Йога/Растяжка*

Сколько минут длилась ваша тренировка?

💡 *Примеры:*
• 20 (20 минут)
• 45 (45 минут)
• 60 (1 час)
"""
    
    keyboard = [
        [InlineKeyboardButton("❌ Отменить", callback_data="log_workout")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)


async def handle_log_functional_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик функциональной тренировки"""
    await cleanup_previous_messages(update, context)
    
    # Устанавливаем состояние для сбора данных о функциональной тренировке
    context.user_data['logging_workout'] = {
        'type': 'functional',
        'step': 'duration',
        'data': {}
    }
    
    text = """
⚡️ *Функциональная тренировка*

Сколько минут длилась ваша тренировка?

💡 *Примеры:*
• 30 (30 минут)
• 45 (45 минут)
• 60 (1 час)
"""
    
    keyboard = [
        [InlineKeyboardButton("❌ Отменить", callback_data="log_workout")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)


async def handle_log_from_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик тренировки из плана"""
    await cleanup_previous_messages(update, context)
    
    text = """
📅 *Тренировка из плана*

Выберите день недели, который вы выполнили:
"""
    
    keyboard = [
        [
            InlineKeyboardButton("Пн", callback_data="log_plan_0"),
            InlineKeyboardButton("Вт", callback_data="log_plan_1"),
            InlineKeyboardButton("Ср", callback_data="log_plan_2"),
            InlineKeyboardButton("Чт", callback_data="log_plan_3")
        ],
        [
            InlineKeyboardButton("Пт", callback_data="log_plan_4"),
            InlineKeyboardButton("Сб", callback_data="log_plan_5"),
            InlineKeyboardButton("Вс", callback_data="log_plan_6")
        ],
        [InlineKeyboardButton("↩️ Назад", callback_data="log_workout")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)