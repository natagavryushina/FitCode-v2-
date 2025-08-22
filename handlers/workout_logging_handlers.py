from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from states.workout_logging_states import WorkoutLoggingStates
from typing import Optional

async def cleanup_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка предыдущих сообщений"""
    # Очистка будет выполнена в основном модуле
    pass

async def track_message(context: ContextTypes.DEFAULT_TYPE, message_id: int):
    """Отслеживание сообщений для очистки"""
    # Отслеживание будет выполнено в основном модуле
    pass

async def get_recent_exercises(user_id: int) -> list[str]:
    """Получение последних упражнений пользователя"""
    # TODO: Реализовать получение из базы данных
    # Пока возвращаем стандартные упражнения
    return [
        "Приседания со штангой",
        "Жим лежа",
        "Становая тяга",
        "Подтягивания",
        "Отжимания"
    ]

async def start_strength_logging(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса внесения силовой тренировки"""
    await cleanup_previous_messages(update, context)
    
    # Получаем последние упражнения пользователя для быстрого выбора
    user_exercises = await get_recent_exercises(update.effective_user.id)
    
    text = "🏋️‍♂️ *Внесение силовой тренировки*\n\nВыберите упражнение:"
    
    keyboard = []
    for exercise in user_exercises[:5]:  # Показываем 5 последних упражнений
        keyboard.append([InlineKeyboardButton(exercise, callback_data=f"select_exercise:{exercise}")])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить новое упражнение", callback_data="add_new_exercise")],
        [InlineKeyboardButton("↩️ Назад", callback_data="log_workout")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)
    return WorkoutLoggingStates.SELECT_EXERCISE

async def log_sets_reps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод подходов и повторений"""
    query = update.callback_query
    exercise_name = query.data.split(":")[1] if ":" in query.data else "Новое упражнение"
    
    context.user_data['current_exercise'] = exercise_name
    
    text = f"""
📊 *Ввод данных для {exercise_name}*

Введите подходы и повторения в формате:
• 3x10 (3 подхода по 10 повторений)
• 4x8-12 (4 подхода по 8-12 повторений)
• 3x5, 1xAMRAP (3 подхода по 5, 1 подход до отказа)
"""
    
    keyboard = [
        [InlineKeyboardButton("↩️ Назад", callback_data="log_strength")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return WorkoutLoggingStates.LOG_SETS_REPS

async def process_sets_reps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенных подходов и повторений"""
    sets_reps = update.message.text
    context.user_data['sets_reps'] = sets_reps
    
    text = "💪 *Введите рабочий вес в кг* (или 0 если без веса):"
    
    keyboard = [
        [InlineKeyboardButton("↩️ Назад", callback_data=f"select_exercise:{context.user_data['current_exercise']}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)
    return WorkoutLoggingStates.LOG_WEIGHT

async def process_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного веса"""
    try:
        weight = float(update.message.text)
        context.user_data['weight'] = weight
        
        text = """
😅 *Оцените сложность (RPE)*:
• 10 - Максимальное усилие
• 9 - Очень тяжело, почти максимум
• 8 - Тяжело, но есть запас
• 7 - Умеренно тяжело
• 6 - Комфортно
• 5 и меньше - Легко
"""
        keyboard = [
            [InlineKeyboardButton("6", callback_data="rpe_6"), 
             InlineKeyboardButton("7", callback_data="rpe_7"), 
             InlineKeyboardButton("8", callback_data="rpe_8")],
            [InlineKeyboardButton("9", callback_data="rpe_9"), 
             InlineKeyboardButton("10", callback_data="rpe_10"),
             InlineKeyboardButton("Пропустить", callback_data="rpe_skip")],
            [InlineKeyboardButton("↩️ Назад", callback_data="back_to_sets_reps")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        await track_message(context, message.message_id)
        return WorkoutLoggingStates.LOG_RPE
        
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число (например: 50 или 27.5)")
        return WorkoutLoggingStates.LOG_WEIGHT

async def process_rpe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка RPE"""
    query = update.callback_query
    rpe = query.data.split("_")[1] if query.data != "rpe_skip" else None
    
    if rpe and rpe != "skip":
        context.user_data['rpe'] = int(rpe)
    
    text = """
📝 *Добавить заметки о технике?*

Напишите заметки или нажмите "Пропустить":
• Ошибки в технике
• Ощущения
• Что получилось/не получилось
"""
    
    keyboard = [
        [InlineKeyboardButton("Пропустить", callback_data="notes_skip")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back_to_weight")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return WorkoutLoggingStates.ADD_NOTES

async def process_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка заметок"""
    if update.message and update.message.text:
        context.user_data['exercise_notes'] = update.message.text
    
    # Показываем итоговую информацию по упражнению
    exercise_name = context.user_data.get('current_exercise', 'Упражнение')
    sets_reps = context.user_data.get('sets_reps', '')
    weight = context.user_data.get('weight', 0)
    rpe = context.user_data.get('rpe', 'Не указано')
    notes = context.user_data.get('exercise_notes', 'Без заметок')
    
    text = f"""
✅ *Упражнение добавлено!*

🏋️‍♂️ **{exercise_name}**
📊 Подходы: {sets_reps}
💪 Вес: {weight} кг
😅 RPE: {rpe}
📝 Заметки: {notes}

Добавить еще одно упражнение?
"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить упражнение", callback_data="add_another_exercise")],
        [InlineKeyboardButton("✅ Завершить тренировку", callback_data="finish_workout")],
        [InlineKeyboardButton("↩️ Назад", callback_data="log_strength")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)
    return WorkoutLoggingStates.CONFIRMATION

async def add_new_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление нового упражнения"""
    query = update.callback_query
    
    text = """
➕ *Новое упражнение*

Введите название упражнения:
"""
    
    keyboard = [
        [InlineKeyboardButton("↩️ Назад", callback_data="log_strength")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Устанавливаем состояние ожидания названия упражнения
    context.user_data['waiting_for_exercise_name'] = True
    return WorkoutLoggingStates.SELECT_EXERCISE

async def process_new_exercise_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка названия нового упражнения"""
    if not update.message or not update.message.text:
        return WorkoutLoggingStates.SELECT_EXERCISE
    
    exercise_name = update.message.text.strip()
    context.user_data['current_exercise'] = exercise_name
    context.user_data['waiting_for_exercise_name'] = False
    
    # Переходим к вводу подходов и повторений
    text = f"""
📊 *Ввод данных для {exercise_name}*

Введите подходы и повторения в формате:
• 3x10 (3 подхода по 10 повторений)
• 4x8-12 (4 подхода по 8-12 повторений)
• 3x5, 1xAMRAP (3 подхода по 5, 1 подход до отказа)
"""
    
    keyboard = [
        [InlineKeyboardButton("↩️ Назад", callback_data="log_strength")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)
    return WorkoutLoggingStates.LOG_SETS_REPS

async def finish_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение тренировки"""
    query = update.callback_query
    
    # TODO: Сохранение тренировки в базу данных
    
    text = """
🎉 *Тренировка завершена!*

Ваша тренировка успешно сохранена.

📊 *Статистика:*
• Количество упражнений: {count}
• Общий объем: {volume} кг
• Время: {duration} мин

+10 баллов за выполненную тренировку! 🎁
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 Посмотреть статистику", callback_data="workout_stats")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="menu_root")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return WorkoutLoggingStates.CONFIRMATION