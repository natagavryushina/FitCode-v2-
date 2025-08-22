from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from db.repo import get_all_training_programs, get_training_program_by_id, get_program_workouts, get_user_active_program, start_user_program, get_user_program_progress, complete_program_workout
from db.database import Session
import json
from db.models import UserProgram

# Состояния для ConversationHandler
class ReadyProgramStates:
    SELECT_PROGRAM = 1
    VIEW_PROGRAM = 2
    START_PROGRAM = 3
    VIEW_WORKOUT = 4

async def handle_ready_programs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список готовых программ"""
    await cleanup_previous_messages(update, context)
    
    session = Session()
    programs = get_all_training_programs(session)
    session.close()
    
    if not programs:
        text = "📚 *Готовые программы*\n\nК сожалению, пока нет доступных программ."
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="workouts")]]
    else:
        text = "📚 *Готовые тренировочные программы*\n\nВыберите программу для просмотра:"
        keyboard = []
        
        for program in programs:
            keyboard.append([
                InlineKeyboardButton(
                    f"🏋️ {program.name} ({program.duration_weeks} нед.)",
                    callback_data=f"view_program:{program.id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="workouts")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await track_message(context, message.message_id)
    return ReadyProgramStates.SELECT_PROGRAM

async def view_program_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать детали программы"""
    query = update.callback_query
    program_id = int(query.data.split(":")[1])
    
    session = Session()
    program = get_training_program_by_id(session, program_id)
    session.close()
    
    if not program:
        await query.answer("Программа не найдена")
        return ConversationHandler.END
    
    # Проверяем, есть ли у пользователя активная программа
    session = Session()
    user_program = get_user_active_program(session, update.effective_user.id)
    session.close()
    
    text = f"""🏋️ *{program.name}*

📝 *Описание:* {program.description or "Описание отсутствует"}

🎯 *Цель:* {program.goal or "Не указана"}
📊 *Уровень:* {program.level or "Не указан"}
⏱ *Длительность:* {program.duration_weeks} недель
📅 *Тренировок в неделю:* {program.days_per_week}
🏋️‍♂️ *Оборудование:* {program.equipment or "Не указано"}

"""
    
    keyboard = []
    
    if user_program:
        if user_program.program_id == program.id:
            # Пользователь уже проходит эту программу
            keyboard.append([InlineKeyboardButton("📊 Мой прогресс", callback_data=f"my_progress:{program.id}")])
        else:
            # У пользователя другая активная программа
            keyboard.append([InlineKeyboardButton("⚠️ У вас уже есть активная программа", callback_data="active_program_warning")])
    else:
        # Пользователь может начать программу
        keyboard.append([InlineKeyboardButton("🚀 Начать программу", callback_data=f"start_program:{program.id}")])
    
    keyboard.extend([
        [InlineKeyboardButton("📋 Посмотреть тренировки", callback_data=f"view_workouts:{program.id}")],
        [InlineKeyboardButton("↩️ К списку программ", callback_data="ready_programs")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ReadyProgramStates.VIEW_PROGRAM

async def view_program_workouts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать тренировки программы"""
    query = update.callback_query
    program_id = int(query.data.split(":")[1])
    
    session = Session()
    program = get_training_program_by_id(session, program_id)
    workouts = get_program_workouts(session, program_id)
    session.close()
    
    if not program:
        await query.answer("Программа не найдена")
        return ConversationHandler.END
    
    text = f"📋 *Тренировки программы '{program.name}'*\n\n"
    
    if not workouts:
        text += "Тренировки не найдены."
    else:
        current_week = None
        for workout in workouts:
            if workout.week_number != current_week:
                current_week = workout.week_number
                text += f"\n📅 *Неделя {current_week}*\n"
            
            text += f"  • День {workout.day_number}: {workout.workout_type}"
            if workout.muscle_groups:
                text += f" ({workout.muscle_groups})"
            if workout.duration_minutes:
                text += f" - {workout.duration_minutes} мин"
            text += "\n"
    
    keyboard = [
        [InlineKeyboardButton("↩️ К программе", callback_data=f"view_program:{program_id}")],
        [InlineKeyboardButton("↩️ К списку программ", callback_data="ready_programs")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ReadyProgramStates.VIEW_PROGRAM

async def start_program_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение начала программы"""
    query = update.callback_query
    program_id = int(query.data.split(":")[1])
    
    session = Session()
    program = get_training_program_by_id(session, program_id)
    session.close()
    
    if not program:
        await query.answer("Программа не найдена")
        return ConversationHandler.END
    
    text = f"""🚀 *Подтверждение начала программы*

Вы собираетесь начать программу:
🏋️ *{program.name}*
⏱ *Длительность:* {program.duration_weeks} недель
📅 *Тренировок в неделю:* {program.days_per_week}

⚠️ *Важно:* 
• Программа заменит текущий план тренировок
• Вы сможете отслеживать прогресс
• В любой момент можно вернуться к свободным тренировкам

Подтверждаете начало программы?"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, начать!", callback_data=f"confirm_start:{program_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"view_program:{program_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ReadyProgramStates.START_PROGRAM

async def confirm_start_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Подтверждение и начало программы"""
	query = update.callback_query
	program_id = int(query.data.split(":")[1])
	
	try:
		session = Session()
		user_program = start_user_program(session, update.effective_user.id, program_id)
		
		# Получаем программу для отображения имени
		program = get_training_program_by_id(session, program_id)
		
		session.commit()
		session.close()
		
		text = f"""🎉 *Программа успешно начата!*

🏋️ *{program.name}*
📅 *Начало:* {user_program.start_date.strftime('%d.%m.%Y')}
📊 *Текущая неделя:* {user_program.current_week}
📅 *Текущий день:* {user_program.current_day}

Теперь вы можете:
• Просматривать текущую тренировку
• Отмечать выполненные тренировки
• Отслеживать прогресс по программе

Удачи в достижении целей! 💪"""
		
		keyboard = [
			[InlineKeyboardButton("📋 Текущая тренировка", callback_data=f"current_workout:{program_id}")],
			[InlineKeyboardButton("📊 Мой прогресс", callback_data=f"my_progress:{program_id}")],
			[InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
		]
		
		reply_markup = InlineKeyboardMarkup(keyboard)
		
		await query.edit_message_text(
			text=text,
			reply_markup=reply_markup,
			parse_mode='Markdown'
		)
		
		return ConversationHandler.END
		
	except ValueError as e:
		await query.answer(str(e))
		return ConversationHandler.END
	except Exception as e:
		await query.answer(f"Ошибка: {str(e)}")
		return ConversationHandler.END

async def show_my_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать прогресс пользователя по программе"""
    query = update.callback_query
    program_id = int(query.data.split(":")[1])
    
    session = Session()
    user_program = get_user_active_program(session, update.effective_user.id)
    
    if not user_program or user_program.program_id != program_id:
        await query.answer("Программа не найдена")
        session.close()
        return ConversationHandler.END
    
    progress = get_user_program_progress(session, user_program.id)
    session.close()
    
    text = f"""📊 *Мой прогресс по программе*

🏋️ *{user_program.program.name}*
📅 *Текущая неделя:* {progress['current_week']} из {progress['total_weeks']}
📅 *Текущий день:* {progress['current_day']} из {progress['days_per_week']}
✅ *Выполнено тренировок:* {progress['completed_workouts']} из {progress['total_workouts']}
📈 *Прогресс:* {progress['progress_percent']:.1f}%

"""
    
    if progress['is_completed']:
        text += "🎉 *Поздравляем! Программа завершена!*"
    else:
        text += "💪 *Продолжайте в том же духе!*"
    
    keyboard = [
        [InlineKeyboardButton("📋 Текущая тренировка", callback_data=f"current_workout:{program_id}")],
        [InlineKeyboardButton("↩️ К программе", callback_data=f"view_program:{program_id}")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ReadyProgramStates.VIEW_PROGRAM

async def show_current_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Показать текущую тренировку пользователя"""
	query = update.callback_query
	program_id = int(query.data.split(":")[1])
	
	session = Session()
	user_program = get_user_active_program(session, update.effective_user.id)
	
	if not user_program or user_program.program_id != program_id:
		await query.answer("Программа не найдена")
		session.close()
		return ConversationHandler.END
	
	# Получаем программу отдельно
	program = get_training_program_by_id(session, program_id)
	
	# Получаем текущую тренировку
	current_workout = get_program_workouts(
		session, 
		program_id, 
		user_program.current_week
	)
	
	current_workout = [w for w in current_workout if w.day_number == user_program.current_day]
	session.close()
	
	if not current_workout:
		text = "❌ Текущая тренировка не найдена"
		keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data=f"my_progress:{program_id}")]]
	else:
		workout = current_workout[0]
		
		text = f"""📋 *Текущая тренировка*

🏋️ *Программа:* {program.name}
📅 *Неделя {user_program.current_week}, День {user_program.current_day}*
🎯 *Тип:* {workout.workout_type}
💪 *Группы мышц:* {workout.muscle_groups or "Не указаны"}
⏱ *Длительность:* {workout.duration_minutes or "Не указана"} мин

"""
		
		if workout.exercises:
			text += "*Упражнения:*\n"
			for i, exercise in enumerate(workout.exercises, 1):
				text += f"{i}. {exercise.get('name', 'Упражнение')}\n"
				if exercise.get('sets') and exercise.get('reps'):
					text += f"   {exercise['sets']} x {exercise['reps']}\n"
				if exercise.get('weight'):
					text += f"   Вес: {exercise['weight']} кг\n"
				text += "\n"
		
		keyboard = [
			[InlineKeyboardButton("✅ Выполнил тренировку", callback_data=f"complete_workout:{program_id}")],
			[InlineKeyboardButton("📊 Мой прогресс", callback_data=f"my_progress:{program_id}")],
			[InlineKeyboardButton("↩️ К программе", callback_data=f"view_program:{program_id}")]
		]
	
	reply_markup = InlineKeyboardMarkup(keyboard)
	
	await query.edit_message_text(
		text=text,
		reply_markup=reply_markup,
		parse_mode='Markdown'
	)
	
	return ReadyProgramStates.VIEW_WORKOUT

async def complete_current_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Отметить текущую тренировку как выполненную"""
	query = update.callback_query
	program_id = int(query.data.split(":")[1])
	
	session = Session()
	user_program = get_user_active_program(session, update.effective_user.id)
	
	if not user_program or user_program.program_id != program_id:
		await query.answer("Программа не найдена")
		session.close()
		return ConversationHandler.END
	
	# Сохраняем текущие значения перед обновлением
	current_week = user_program.current_week
	current_day = user_program.current_day
	days_per_week = user_program.program.days_per_week
	duration_weeks = user_program.program.duration_weeks
	
	# Получаем программу для отображения имени
	program = get_training_program_by_id(session, program_id)
	
	# Отмечаем тренировку как выполненную
	complete_program_workout(
		session, 
		user_program.id, 
		current_week, 
		current_day
	)
	
	session.commit()
	
	# Получаем обновленные данные
	user_program = session.get(UserProgram, user_program.id)
	session.close()
	
	text = f"""✅ *Тренировка выполнена!*

🎉 Отличная работа! Вы завершили:
📅 *Неделя {current_week}, День {current_day}*
🏋️ *Программа:* {program.name}

"""
	
	# Проверяем, завершена ли программа
	if user_program.is_completed:
		text += "🎊 *Поздравляем! Вы завершили всю программу!*\n\nТеперь вы можете выбрать новую программу или вернуться к свободным тренировкам."
		keyboard = [
			[InlineKeyboardButton("📚 Новые программы", callback_data="ready_programs")],
			[InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
		]
	else:
		text += f"📊 *Следующая тренировка:* Неделя {user_program.current_week}, День {user_program.current_day}"
		keyboard = [
			[InlineKeyboardButton("📋 Следующая тренировка", callback_data=f"current_workout:{program_id}")],
			[InlineKeyboardButton("📊 Мой прогресс", callback_data=f"my_progress:{program_id}")],
			[InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
		]
	
	reply_markup = InlineKeyboardMarkup(keyboard)
	
	await query.edit_message_text(
		text=text,
		reply_markup=reply_markup,
		parse_mode='Markdown'
	)
	
	return ConversationHandler.END

async def handle_active_program_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Предупреждение о наличии активной программы"""
    query = update.callback_query
    
    text = """⚠️ *У вас уже есть активная программа*

Для начала новой программы необходимо сначала завершить текущую или отменить её.

Вы можете:
• Продолжить текущую программу
• Отменить текущую программу
• Дождаться её завершения"""
    
    keyboard = [
        [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton("❌ Отменить программу", callback_data="cancel_program")],
        [InlineKeyboardButton("↩️ Назад", callback_data="ready_programs")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

# Заглушки для функций очистки и отслеживания сообщений
async def cleanup_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка предыдущих сообщений"""
    pass

async def track_message(context: ContextTypes.DEFAULT_TYPE, message_id: int):
    """Отслеживание сообщения"""
    pass