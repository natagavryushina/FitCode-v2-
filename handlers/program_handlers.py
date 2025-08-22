from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from db.repo import (
    get_all_training_programs, get_training_program_by_id, get_program_workouts, 
    get_user_active_program, start_user_program, get_user_program_progress, 
    complete_program_workout, get_training_programs_by_goal
)
from db.database import SessionLocal
from db.models import UserProgram
import json

# Состояния для ConversationHandler
class ProgramStates:
    SELECT_PROGRAM = 1
    VIEW_PROGRAM = 2
    START_PROGRAM = 3
    VIEW_WORKOUT = 4
    FILTER_PROGRAMS = 5

async def handle_training_programs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Готовые программы'"""
    await cleanup_previous_messages(update, context)
    
    text = """
🏆 *Готовые тренировочные программы*

Выберите программу, которая соответствует вашим целям:

Каждая программа включает:
• 📅 Полный план на несколько недель
• 🏋️‍♂️ Детальные тренировки на каждый день
• 📊 Прогрессию нагрузок
• 🎯 Четкие цели и метрики
"""
    
    # Получаем доступные программы
    programs = await get_available_programs()
    
    keyboard = []
    for program in programs:
        keyboard.append([InlineKeyboardButton(
            f"{program['name']} - {program['goal']}", 
            callback_data=f"program_{program['id']}"
        )])
    
    keyboard.extend([
        [InlineKeyboardButton("🔍 Фильтр по цели", callback_data="programs_filter")],
        [InlineKeyboardButton("📊 Мои текущие программы", callback_data="my_programs")],
        [InlineKeyboardButton("↩️ Назад к тренировкам", callback_data="workouts")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)

async def show_program_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать детали программы"""
    query = update.callback_query
    program_id = int(query.data.split("_")[1])
    
    program = await get_program_details(program_id)
    
    text = f"""
🏆 *{program['name']}*

🎯 *Цель:* {program['goal']}
📊 *Уровень:* {program['level']}
⏱ *Продолжительность:* {program['duration_weeks']} недель
📅 *Тренировок в неделю:* {program['days_per_week']}
🏋️ *Оборудование:* {program['equipment']}

📝 *Описание:*
{program['description']}

*Что включено:*
• Полный план тренировок на {program['duration_weeks']} недель
• Детальные инструкции для каждого упражнения
• Прогрессия нагрузок
• Рекомендации по питанию
• Поддержка и мотивация
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Начать эту программу", callback_data=f"start_program_{program_id}")],
        [InlineKeyboardButton("📋 Посмотреть план", callback_data=f"view_program_plan_{program_id}")],
        [InlineKeyboardButton("💬 Отзывы", callback_data=f"program_reviews_{program_id}")],
        [InlineKeyboardButton("↩️ Назад к программам", callback_data="training_programs")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_programs_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать фильтр программ по целям"""
    query = update.callback_query
    
    text = """
🔍 *Фильтр программ*

Выберите критерии для подбора программы:
"""
    
    keyboard = [
        [InlineKeyboardButton("🎯 По цели", callback_data="filter_goal")],
        [InlineKeyboardButton("📊 По уровню", callback_data="filter_level")],
        [InlineKeyboardButton("⏱ По длительности", callback_data="filter_duration")],
        [InlineKeyboardButton("🏋️ По оборудованию", callback_data="filter_equipment")],
        [InlineKeyboardButton("↩️ Назад к программам", callback_data="training_programs")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_programs_by_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фильтр программ по цели"""
    query = update.callback_query
    
    text = "🎯 *Выберите цель:*"
    
    keyboard = [
        [InlineKeyboardButton("💪 Набор массы", callback_data="filter_goal_mass")],
        [InlineKeyboardButton("🔥 Похудение", callback_data="filter_goal_weightloss")],
        [InlineKeyboardButton("⚡️ Поддержание тонуса", callback_data="filter_goal_tonus")],
        [InlineKeyboardButton("🏃‍♂️ Выносливость", callback_data="filter_goal_endurance")],
        [InlineKeyboardButton("↩️ Назад к фильтрам", callback_data="programs_filter")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_programs_by_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фильтр программ по уровню сложности"""
    query = update.callback_query
    
    text = "📊 *Выберите уровень сложности:*"
    
    keyboard = [
        [InlineKeyboardButton("🟢 Начинающий", callback_data="filter_level_beginner")],
        [InlineKeyboardButton("🟡 Средний", callback_data="filter_level_intermediate")],
        [InlineKeyboardButton("🔴 Продвинутый", callback_data="filter_level_advanced")],
        [InlineKeyboardButton("↩️ Назад к фильтрам", callback_data="programs_filter")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_programs_by_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фильтр программ по длительности"""
    query = update.callback_query
    
    text = "⏱ *Выберите длительность программы:*"
    
    keyboard = [
        [InlineKeyboardButton("📅 4-6 недель", callback_data="filter_duration_short")],
        [InlineKeyboardButton("📅 8-10 недель", callback_data="filter_duration_medium")],
        [InlineKeyboardButton("📅 12+ недель", callback_data="filter_duration_long")],
        [InlineKeyboardButton("↩️ Назад к фильтрам", callback_data="programs_filter")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_programs_by_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фильтр программ по оборудованию"""
    query = update.callback_query
    
    text = "🏋️ *Выберите доступное оборудование:*"
    
    keyboard = [
        [InlineKeyboardButton("🚶‍♂️ Без оборудования", callback_data="filter_equipment_none")],
        [InlineKeyboardButton("🏋️ Гантели", callback_data="filter_equipment_dumbbells")],
        [InlineKeyboardButton("🏋️ Штанга + скамья", callback_data="filter_equipment_barbell")],
        [InlineKeyboardButton("🏋️ Полный зал", callback_data="filter_equipment_full")],
        [InlineKeyboardButton("↩️ Назад к фильтрам", callback_data="programs_filter")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_filtered_programs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать программы по выбранным критериям"""
    query = update.callback_query
    filter_data = query.data.split("_")
    
    if len(filter_data) < 3:
        await query.answer("Неверный формат фильтра")
        return
    
    filter_type = filter_data[1]
    filter_value = filter_data[2]
    
    session = SessionLocal()
    
    try:
        if filter_type == "goal":
            # Маппинг целей
            goal_mapping = {
                "mass": "muscle_gain",
                "weightloss": "fat_loss", 
                "tonus": "strength",
                "endurance": "endurance"
            }
            mapped_goal = goal_mapping.get(filter_value, filter_value)
            programs = get_training_programs_by_goal(session, mapped_goal)
            filter_name = {
                "mass": "Набор массы",
                "weightloss": "Похудение",
                "tonus": "Поддержание тонуса",
                "endurance": "Выносливость"
            }.get(filter_value, filter_value)
            
        elif filter_type == "level":
            # Фильтр по уровню
            programs = [p for p in get_all_training_programs(session) if p.level == filter_value]
            filter_name = {
                "beginner": "Начинающий",
                "intermediate": "Средний", 
                "advanced": "Продвинутый"
            }.get(filter_value, filter_value)
            
        elif filter_type == "duration":
            # Фильтр по длительности
            all_programs = get_all_training_programs(session)
            if filter_value == "short":
                programs = [p for p in all_programs if p.duration_weeks <= 6]
                filter_name = "4-6 недель"
            elif filter_value == "medium":
                programs = [p for p in all_programs if 7 <= p.duration_weeks <= 10]
                filter_name = "8-10 недель"
            elif filter_value == "long":
                programs = [p for p in all_programs if p.duration_weeks >= 11]
                filter_name = "12+ недель"
            else:
                programs = []
                filter_name = "Неизвестная длительность"
                
        elif filter_type == "equipment":
            # Фильтр по оборудованию
            all_programs = get_all_training_programs(session)
            if filter_value == "none":
                programs = [p for p in all_programs if "bodyweight_only" in p.equipment]
                filter_name = "Без оборудования"
            elif filter_value == "dumbbells":
                programs = [p for p in all_programs if "dumbbells" in p.equipment]
                filter_name = "Гантели"
            elif filter_value == "barbell":
                programs = [p for p in all_programs if "barbell" in p.equipment or "bench" in p.equipment]
                filter_name = "Штанга + скамья"
            elif filter_value == "full":
                programs = [p for p in all_programs if "barbell" in p.equipment and "bench" in p.equipment]
                filter_name = "Полный зал"
            else:
                programs = []
                filter_name = "Неизвестное оборудование"
        else:
            programs = []
            filter_name = "Неизвестный фильтр"
            
    finally:
        session.close()
    
    text = f"🎯 *Программы для: {filter_name}*\n\n"
    
    if not programs:
        text += "К сожалению, программы для выбранных критериев пока недоступны.\n\n"
        text += "💡 *Рекомендации:*\n"
        text += "• Попробуйте другие критерии\n"
        text += "• Посмотрите все доступные программы\n"
        text += "• Обратитесь к персональному тренеру"
        
        keyboard = [
            [InlineKeyboardButton("🔍 Другие фильтры", callback_data="programs_filter")],
            [InlineKeyboardButton("📚 Все программы", callback_data="training_programs")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
    else:
        text += f"Найдено {len(programs)} программ:\n\n"
        
        for i, program in enumerate(programs[:5], 1):  # Показываем первые 5
            text += f"{i}. **{program.name}**\n"
            text += f"   🎯 {program.goal} • 📊 {program.level}\n"
            text += f"   ⏱ {program.duration_weeks} недель • 📅 {program.days_per_week} дня/неделю\n\n"
        
        if len(programs) > 5:
            text += f"... и еще {len(programs) - 5} программ\n\n"
        
        keyboard = []
        for program in programs[:5]:
            keyboard.append([InlineKeyboardButton(
                f"🏋️ {program.name}",
                callback_data=f"program_{program.id}"
            )])
        
        keyboard.extend([
            [InlineKeyboardButton("🔍 Другие фильтры", callback_data="programs_filter")],
            [InlineKeyboardButton("📚 Все программы", callback_data="training_programs")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_my_programs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущие программы пользователя"""
    query = update.callback_query
    
    session = SessionLocal()
    user_program = get_user_active_program(session, update.effective_user.id)
    session.close()
    
    if not user_program:
        text = """
📊 *Мои программы*

У вас пока нет активных программ.

Выберите программу из каталога, чтобы начать тренировки по структурированному плану!
"""
        keyboard = [
            [InlineKeyboardButton("📚 Выбрать программу", callback_data="training_programs")],
            [InlineKeyboardButton("↩️ Назад", callback_data="workouts")]
        ]
    else:
        session = SessionLocal()
        progress = get_user_program_progress(session, user_program.id)
        session.close()
        
        text = f"""
📊 *Моя текущая программа*

🏋️ *{user_program.program.name}*
📅 *Неделя:* {progress['current_week']} из {progress['total_weeks']}
📅 *День:* {progress['current_day']} из {progress['days_per_week']}
✅ *Прогресс:* {progress['progress_percent']:.1f}%
📈 *Выполнено:* {progress['completed_workouts']}/{progress['total_workouts']} тренировок

"""
        
        if progress['is_completed']:
            text += "🎉 *Программа завершена! Поздравляем!*"
            keyboard = [
                [InlineKeyboardButton("📚 Выбрать новую программу", callback_data="training_programs")],
                [InlineKeyboardButton("📊 Статистика", callback_data="program_stats")],
                [InlineKeyboardButton("↩️ Назад", callback_data="workouts")]
            ]
        else:
            text += "💪 *Продолжайте тренировки!*"
            keyboard = [
                [InlineKeyboardButton("📋 Текущая тренировка", callback_data=f"current_workout:{user_program.program_id}")],
                [InlineKeyboardButton("📊 Детальный прогресс", callback_data=f"my_progress:{user_program.program_id}")],
                [InlineKeyboardButton("⏸️ Приостановить программу", callback_data=f"pause_program:{user_program.id}")],
                [InlineKeyboardButton("↩️ Назад", callback_data="workouts")]
            ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def view_program_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать план программы по неделям"""
    query = update.callback_query
    program_id = int(query.data.split("_")[2])
    
    session = SessionLocal()
    program = get_training_program_by_id(session, program_id)
    workouts = get_program_workouts(session, program_id)
    session.close()
    
    if not program:
        await query.answer("Программа не найдена")
        return
    
    text = f"📋 *План программы '{program.name}'*\n\n"
    
    # Группируем тренировки по неделям
    weeks = {}
    for workout in workouts:
        if workout.week_number not in weeks:
            weeks[workout.week_number] = []
        weeks[workout.week_number].append(workout)
    
    for week_num in sorted(weeks.keys()):
        text += f"📅 *Неделя {week_num}*\n"
        week_workouts = sorted(weeks[week_num], key=lambda x: x.day_number)
        
        for workout in week_workouts:
            text += f"  • День {workout.day_number}: {workout.workout_type}"
            if workout.muscle_groups:
                text += f" ({workout.muscle_groups})"
            if workout.duration_minutes:
                text += f" - {workout.duration_minutes} мин"
            text += "\n"
        text += "\n"
    
    keyboard = [
        [InlineKeyboardButton("✅ Начать программу", callback_data=f"start_program_{program_id}")],
        [InlineKeyboardButton("↩️ К программе", callback_data=f"program_{program_id}")],
        [InlineKeyboardButton("↩️ Все программы", callback_data="training_programs")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def start_program_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение начала программы"""
    query = update.callback_query
    program_id = int(query.data.split("_")[2])
    
    session = SessionLocal()
    program = get_training_program_by_id(session, program_id)
    existing_program = get_user_active_program(session, update.effective_user.id)
    session.close()
    
    if not program:
        await query.answer("Программа не найдена")
        return
    
    if existing_program:
        text = f"""
⚠️ *У вас уже есть активная программа*

Текущая программа: *{existing_program.program.name}*

Чтобы начать новую программу '{program.name}', нужно:
• Завершить текущую программу
• Или отменить её

Что хотите сделать?
"""
        keyboard = [
            [InlineKeyboardButton("📊 Продолжить текущую", callback_data=f"my_progress:{existing_program.program_id}")],
            [InlineKeyboardButton("❌ Отменить текущую", callback_data=f"cancel_program:{existing_program.id}")],
            [InlineKeyboardButton("↩️ Назад", callback_data=f"program_{program_id}")]
        ]
    else:
        text = f"""
🚀 *Подтверждение начала программы*

Вы собираетесь начать:
🏋️ *{program.name}*
🎯 *Цель:* {program.goal}
⏱ *Длительность:* {program.duration_weeks} недель
📅 *Тренировок в неделю:* {program.days_per_week}

📋 *Что это означает:*
• Вы получите структурированный план тренировок
• Сможете отслеживать прогресс
• Получите рекомендации по технике
• В любой момент можете вернуться к свободным тренировкам

Готовы начать?
"""
        keyboard = [
            [InlineKeyboardButton("✅ Да, начать программу!", callback_data=f"confirm_start_{program_id}")],
            [InlineKeyboardButton("📋 Ещё раз посмотреть план", callback_data=f"view_program_plan_{program_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"program_{program_id}")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def confirm_start_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и начало программы"""
    query = update.callback_query
    program_id = int(query.data.split("_")[2])
    
    try:
        session = SessionLocal()
        user_program = start_user_program(session, update.effective_user.id, program_id)
        program = get_training_program_by_id(session, program_id)
        session.commit()
        session.close()
        
        text = f"""
🎉 *Программа успешно начата!*

🏋️ *{program.name}*
📅 *Дата начала:* {user_program.start_date.strftime('%d.%m.%Y')}
📊 *Текущий этап:* Неделя {user_program.current_week}, День {user_program.current_day}

🎯 *Ваши следующие шаги:*
1. Изучите первую тренировку
2. Выполните её в удобное время
3. Отметьте выполнение в боте
4. Переходите к следующей тренировке

Удачи в достижении целей! 💪
"""
        
        keyboard = [
            [InlineKeyboardButton("📋 Первая тренировка", callback_data=f"current_workout:{program_id}")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data=f"my_progress:{program_id}")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except ValueError as e:
        await query.answer(f"Ошибка: {str(e)}")
    except Exception as e:
        await query.answer(f"Произошла ошибка: {str(e)}")

async def show_current_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущую тренировку пользователя"""
    query = update.callback_query
    program_id = int(query.data.split(":")[1])
    
    session = SessionLocal()
    user_program = get_user_active_program(session, update.effective_user.id)
    program = get_training_program_by_id(session, program_id)
    
    if not user_program or user_program.program_id != program_id:
        await query.answer("Программа не найдена")
        session.close()
        return
    
    # Получаем текущую тренировку
    current_workouts = get_program_workouts(session, program_id, user_program.current_week)
    current_workout = next((w for w in current_workouts if w.day_number == user_program.current_day), None)
    session.close()
    
    if not current_workout:
        text = "❌ Текущая тренировка не найдена"
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data=f"my_progress:{program_id}")]]
    else:
        text = f"""
📋 *Текущая тренировка*

🏋️ *Программа:* {program.name}
📅 *Неделя {user_program.current_week}, День {user_program.current_day}*
🎯 *Тип тренировки:* {current_workout.workout_type}
💪 *Целевые мышцы:* {current_workout.muscle_groups or "Общая"}
⏱ *Примерная длительность:* {current_workout.duration_minutes or 45} мин

"""
        
        if current_workout.exercises:
            text += "*📋 План тренировки:*\n"
            for i, exercise in enumerate(current_workout.exercises, 1):
                text += f"{i}. **{exercise.get('name', 'Упражнение')}**\n"
                if exercise.get('sets') and exercise.get('reps'):
                    text += f"   • {exercise['sets']} подходов x {exercise['reps']} повторений\n"
                if exercise.get('weight'):
                    text += f"   • Рабочий вес: {exercise['weight']} кг\n"
                if exercise.get('rest'):
                    text += f"   • Отдых: {exercise['rest']} сек\n"
                if exercise.get('notes'):
                    text += f"   • Примечание: {exercise['notes']}\n"
                text += "\n"
        
        text += "💡 *Совет:* Выполните тренировку и отметьте её как завершённую для перехода к следующей!"
        
        keyboard = [
            [InlineKeyboardButton("✅ Выполнил тренировку", callback_data=f"complete_workout:{program_id}")],
            [InlineKeyboardButton("📝 Внести детали", callback_data=f"log_program_workout:{program_id}")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data=f"my_progress:{program_id}")],
            [InlineKeyboardButton("↩️ К программе", callback_data=f"program_{program_id}")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_program_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать детальный прогресс по программе"""
    query = update.callback_query
    program_id = int(query.data.split(":")[1])
    
    session = SessionLocal()
    user_program = get_user_active_program(session, update.effective_user.id)
    
    if not user_program or user_program.program_id != program_id:
        await query.answer("Программа не найдена")
        session.close()
        return
    
    progress = get_user_program_progress(session, user_program.id)
    program = get_training_program_by_id(session, program_id)
    session.close()
    
    # Создаем визуальный прогресс-бар
    progress_percent = progress['progress_percent']
    filled_blocks = int(progress_percent / 10)
    progress_bar = "█" * filled_blocks + "░" * (10 - filled_blocks)
    
    text = f"""
📊 *Детальный прогресс*

🏋️ *Программа:* {program.name}
📅 *Начата:* {user_program.start_date.strftime('%d.%m.%Y')}

📈 *Общий прогресс:*
{progress_bar} {progress_percent:.1f}%

📋 *Статистика:*
• Текущая неделя: {progress['current_week']} из {progress['total_weeks']}
• Текущий день: {progress['current_day']} из {progress['days_per_week']}
• Выполнено тренировок: {progress['completed_workouts']} из {progress['total_workouts']}
• Осталось тренировок: {progress['total_workouts'] - progress['completed_workouts']}

"""
    
    if progress['is_completed']:
        text += "🎊 *Поздравляем! Программа полностью завершена!*"
        keyboard = [
            [InlineKeyboardButton("📚 Новая программа", callback_data="training_programs")],
            [InlineKeyboardButton("📈 Статистика", callback_data="program_stats")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
    else:
        days_left = (progress['total_weeks'] - progress['current_week'] + 1) * progress['days_per_week'] - progress['current_day'] + 1
        text += f"🎯 *Осталось примерно {days_left} дней до завершения*"
        
        keyboard = [
            [InlineKeyboardButton("📋 Текущая тренировка", callback_data=f"current_workout:{program_id}")],
            [InlineKeyboardButton("📅 План на неделю", callback_data=f"week_plan:{program_id}:{progress['current_week']}")],
            [InlineKeyboardButton("⏸️ Приостановить", callback_data=f"pause_program:{user_program.id}")],
            [InlineKeyboardButton("↩️ К программе", callback_data=f"program_{program_id}")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def complete_program_workout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отметить программную тренировку как выполненную"""
    query = update.callback_query
    program_id = int(query.data.split(":")[1])
    
    session = SessionLocal()
    user_program = get_user_active_program(session, update.effective_user.id)
    program = get_training_program_by_id(session, program_id)
    
    if not user_program or user_program.program_id != program_id:
        await query.answer("Программа не найдена")
        session.close()
        return
    
    # Сохраняем текущие значения
    current_week = user_program.current_week
    current_day = user_program.current_day
    
    # Отмечаем тренировку как выполненную
    complete_program_workout(session, user_program.id, current_week, current_day)
    
    # Получаем обновленные данные
    user_program = session.get(UserProgram, user_program.id)
    session.commit()
    session.close()
    
    text = f"""
✅ *Тренировка выполнена!*

🎉 Отличная работа! Вы завершили:
📅 *Неделя {current_week}, День {current_day}*
🏋️ *Программа:* {program.name}

"""
    
    if user_program.is_completed:
        text += """
🎊 *ПОЗДРАВЛЯЕМ!*
Вы успешно завершили всю программу!

🏆 *Ваши достижения:*
• Прошли полный курс тренировок
• Развили дисциплину и постоянство
• Достигли поставленной цели

Теперь можете выбрать новую программу или продолжить свободные тренировки.
"""
        keyboard = [
            [InlineKeyboardButton("🎉 Мои достижения", callback_data="program_achievements")],
            [InlineKeyboardButton("📚 Новая программа", callback_data="training_programs")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
    else:
        text += f"""
📊 *Следующая тренировка:*
Неделя {user_program.current_week}, День {user_program.current_day}

Продолжайте в том же духе! 💪
"""
        keyboard = [
            [InlineKeyboardButton("📋 Следующая тренировка", callback_data=f"current_workout:{program_id}")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data=f"my_progress:{program_id}")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Вспомогательные функции
async def get_available_programs():
    """Получить доступные программы"""
    session = SessionLocal()
    programs = get_all_training_programs(session)
    session.close()
    
    return [
        {
            'id': p.id,
            'name': p.name,
            'goal': p.goal,
            'level': p.level,
            'duration_weeks': p.duration_weeks,
            'days_per_week': p.days_per_week,
            'equipment': p.equipment,
            'description': p.description
        }
        for p in programs
    ]

async def get_program_details(program_id: int):
    """Получить детали программы"""
    session = SessionLocal()
    program = get_training_program_by_id(session, program_id)
    session.close()
    
    if not program:
        return None
    
    return {
        'id': program.id,
        'name': program.name,
        'goal': program.goal,
        'level': program.level,
        'duration_weeks': program.duration_weeks,
        'days_per_week': program.days_per_week,
        'equipment': program.equipment,
        'description': program.description
    }

# Заглушки для функций очистки и отслеживания сообщений
async def cleanup_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка предыдущих сообщений"""
    pass

async def track_message(context: ContextTypes.DEFAULT_TYPE, message_id: int):
    """Отслеживание сообщения"""
    pass