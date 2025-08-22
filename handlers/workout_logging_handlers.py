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
	
	# ожидание ввода подходов/повторений
	context.user_data.setdefault('logging_workout', {})['step'] = 'sets_reps'
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
	
	# ожидание ввода веса
	context.user_data.setdefault('logging_workout', {})['step'] = 'weight'
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
		
		# ожидание rpe
		context.user_data.setdefault('logging_workout', {})['step'] = 'rpe'
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
	
	# ожидание заметок
	context.user_data.setdefault('logging_workout', {})['step'] = 'notes'
	return WorkoutLoggingStates.ADD_NOTES

async def process_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработка заметок"""
	if update.message and update.message.text:
		context.user_data['exercise_notes'] = update.message.text
	
	# Собираем данные упражнения
	exercise_data = {
		'name': context.user_data.get('current_exercise', 'Упражнение'),
		'sets': context.user_data.get('sets_reps', ''),
		'reps': context.user_data.get('sets_reps', ''),
		'weight': context.user_data.get('weight', 0),
		'rpe': context.user_data.get('rpe'),
		'notes': context.user_data.get('exercise_notes', '')
	}
	
	# Инициализируем workout_data если его нет
	if 'workout_data' not in context.user_data:
		context.user_data['workout_data'] = {
			'type': 'Силовая тренировка',
			'exercises': [],
			'duration': 0,
			'notes': ''
		}
	
	# Добавляем упражнение к тренировке
	context.user_data['workout_data']['exercises'].append(exercise_data)
	
	# Показываем итоговую информацию по упражнению
	exercise_name = exercise_data['name']
	sets_reps = exercise_data['sets']
	weight = exercise_data['weight']
	rpe = exercise_data['rpe'] or 'Не указано'
	notes = exercise_data['notes'] or 'Без заметок'
	
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
	
	# ожидание ввода подходов/повторений
	context.user_data.setdefault('logging_workout', {})['step'] = 'sets_reps'
	await track_message(context, message.message_id)
	return WorkoutLoggingStates.LOG_SETS_REPS

async def finish_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Завершение тренировки"""
	query = update.callback_query
	
	# Запрашиваем длительность тренировки
	text = """
⏱ *Длительность тренировки*

Сколько минут длилась вся тренировка?

💡 *Примеры:*
• 45 (45 минут)
• 60 (1 час)
• 90 (1.5 часа)
"""
	
	keyboard = [
		[InlineKeyboardButton("↩️ Назад", callback_data="back_to_exercise")]
	]
	
	reply_markup = InlineKeyboardMarkup(keyboard)
	
	await query.edit_message_text(
		text=text,
		reply_markup=reply_markup,
		parse_mode='Markdown'
	)
	
	# Устанавливаем состояние ожидания длительности
	context.user_data.setdefault('logging_workout', {})['step'] = 'workout_duration'
	return WorkoutLoggingStates.LOG_DURATION

# --- Кардио ---
async def start_cardio_logging(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Начало процесса внесения кардио тренировки"""
	await cleanup_previous_messages(update, context)
	
	text = """
🏃‍♂️ *Внесение кардио тренировки*

Выберите тип кардио:
"""
	
	keyboard = [
		[InlineKeyboardButton("🏃‍♂️ Бег", callback_data="cardio_run"),
		 InlineKeyboardButton("🚴‍♂️ Велосипед", callback_data="cardio_bike")],
		[InlineKeyboardButton("🏊‍♂️ Плавание", callback_data="cardio_swim"),
		 InlineKeyboardButton("🏃‍♂️ Ходьба", callback_data="cardio_walk")],
		[InlineKeyboardButton("🎯 Другое", callback_data="cardio_other"),
		 InlineKeyboardButton("↩️ Назад", callback_data="log_workout")]
	]
	
	reply_markup = InlineKeyboardMarkup(keyboard)
	
	message = await context.bot.send_message(
		chat_id=update.effective_chat.id,
		text=text,
		reply_markup=reply_markup,
		parse_mode='Markdown'
	)
	
	await track_message(context, message.message_id)
	return WorkoutLoggingStates.LOG_DURATION

async def process_cardio_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработка выбора типа кардио"""
	query = update.callback_query
	cardio_type = query.data
	
	# Преобразуем callback_data в читаемый формат
	cardio_types = {
		"cardio_run": "Бег",
		"cardio_bike": "Велосипед",
		"cardio_swim": "Плавание",
		"cardio_walk": "Ходьба",
		"cardio_other": "Другое"
	}
	
	context.user_data['cardio_type'] = cardio_types.get(cardio_type, "Кардио")
	
	text = f"⏱ *Введите продолжительность {context.user_data['cardio_type']} в минутах:*"
	
	keyboard = [
		[InlineKeyboardButton("↩️ Назад", callback_data="log_cardio")]
	]
	
	reply_markup = InlineKeyboardMarkup(keyboard)
	
	await query.edit_message_text(
		text=text,
		reply_markup=reply_markup,
		parse_mode='Markdown'
	)
	
	# ожидание длительности
	context.user_data['awaiting_cardio_duration'] = True
	context.user_data.setdefault('logging_workout', {})['step'] = 'duration'
	return WorkoutLoggingStates.LOG_DURATION

async def process_cardio_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработка введенной длительности кардио и сохранение тренировки"""
	from db import repo
	from db.database import session_scope
	
	try:
		duration = int(float(update.message.text))
		if duration <= 0 or duration > 600:
			raise ValueError
	except Exception:
		await update.message.reply_text("Введите длительность в минутах, например: 30")
		return WorkoutLoggingStates.LOG_DURATION
	
	context.user_data['awaiting_cardio_duration'] = False
	
	# Сохраняем тренировку
	user_id_str = str(update.effective_user.id)
	with session_scope() as s:
		user = repo.get_or_create_user(s, user_id_str, update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
		workout = repo.create_completed_workout(
			session=s,
			user_id=user.id,
			plan_id=None,
			workout_type=context.user_data.get('cardio_type', 'Кардио'),
			duration=duration,
			notes=None,
		)
		repo.add_loyalty_points(s, user.id, 10)
	
	text = f"""
✅ *Кардио сохранено!*

Тип: {context.user_data.get('cardio_type', 'Кардио')}
Длительность: {duration} мин

+10 баллов за активность 🎁
"""
	
	keyboard = [
		[InlineKeyboardButton("↩️ К тренировкам", callback_data="menu_workouts")],
		[InlineKeyboardButton("🏠 В меню", callback_data="menu_root")]
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

async def process_workout_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Обработка введенной длительности тренировки и сохранение"""
	try:
		duration = int(float(update.message.text))
		if duration <= 0 or duration > 600:
			raise ValueError
	except Exception:
		await update.message.reply_text("Введите длительность в минутах, например: 45")
		return WorkoutLoggingStates.LOG_DURATION
	
	# Сохраняем длительность в workout_data
	context.user_data.setdefault('workout_data', {})['duration'] = duration
	
	# Сохраняем тренировку в базу данных
	return await save_completed_workout(update, context)

async def save_completed_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Сохранение завершенной тренировки в базу данных"""
	from db import repo
	from db.database import session_scope
	from datetime import datetime
	
	user_id_str = str(update.effective_user.id)
	workout_data = context.user_data.get('workout_data', {})
	
	# Сохраняем тренировку в базу
	with session_scope() as s:
		user = repo.get_or_create_user(s, user_id_str, update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
		
		workout = repo.create_completed_workout(
			session=s,
			user_id=user.id,
			plan_id=workout_data.get('plan_id'),
			workout_type=workout_data.get('type'),
			duration=workout_data.get('duration'),
			notes=workout_data.get('notes')
		)
		
		# Сохраняем упражнения
		for exercise in workout_data.get('exercises', []):
			repo.add_completed_exercise(
				session=s,
				workout_id=workout.id,
				exercise_name=exercise['name'],
				sets=exercise['sets'],
				reps=exercise['reps'],
				weight=exercise['weight'],
				rpe=exercise.get('rpe'),
				notes=exercise.get('notes')
			)
		
		# Обновляем общий объем тренировки
		repo.update_workout_volume(s, workout.id)
		
		# Добавляем баллы лояльности
		repo.add_loyalty_points(s, user.id, 10)
	
	# Очищаем временные данные
	context.user_data.pop('workout_data', None)
	context.user_data.pop('current_exercise', None)
	context.user_data.pop('logging_workout', None)
	
	return await show_workout_summary(update, context, workout)

async def show_workout_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, workout):
	"""Показать сводку по завершенной тренировке"""
	text = f"""
✅ *Тренировка сохранена!*

🏋️‍♂️ *Тип:* {workout.workout_type}
⏱ *Длительность:* {workout.duration} мин
📊 *Общий объем:* {workout.total_volume or 0} кг
⭐ *Оценка:* {workout.rating or 'Не указана'}/5

*Отличная работа! 💪*
"""
	
	keyboard = [
		[InlineKeyboardButton("📊 Посмотреть статистику", callback_data="view_stats")],
		[InlineKeyboardButton("📅 Запланировать следующую", callback_data="schedule_next")],
		[InlineKeyboardButton("🏠 В главное меню", callback_data="menu_root")]
	]
	
	reply_markup = InlineKeyboardMarkup(keyboard)
	
	if update.callback_query:
		await update.callback_query.edit_message_text(
			text=text,
			reply_markup=reply_markup,
			parse_mode='Markdown'
		)
	else:
		message = await context.bot.send_message(
			chat_id=update.effective_chat.id,
			text=text,
			reply_markup=reply_markup,
			parse_mode='Markdown'
		)
		await track_message(context, message.message_id)
	
	return WorkoutLoggingStates.CONFIRMATION

async def add_another_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
	"""Добавление еще одного упражнения к тренировке"""
	query = update.callback_query
	
	# Очищаем данные текущего упражнения, но оставляем workout_data
	context.user_data.pop('current_exercise', None)
	context.user_data.pop('sets_reps', None)
	context.user_data.pop('weight', None)
	context.user_data.pop('rpe', None)
	context.user_data.pop('exercise_notes', None)
	
	# Возвращаемся к выбору упражнения
	text = "🏋️‍♂️ *Внесение силовой тренировки*\n\nВыберите упражнение:"
	
	user_exercises = await get_recent_exercises(update.effective_user.id)
	
	keyboard = []
	for exercise in user_exercises[:5]:
		keyboard.append([InlineKeyboardButton(exercise, callback_data=f"select_exercise:{exercise}")])
	
	keyboard.extend([
		[InlineKeyboardButton("➕ Добавить новое упражнение", callback_data="add_new_exercise")],
		[InlineKeyboardButton("✅ Завершить тренировку", callback_data="finish_workout")]
	])
	
	reply_markup = InlineKeyboardMarkup(keyboard)
	
	await query.edit_message_text(
		text=text,
		reply_markup=reply_markup,
		parse_mode='Markdown'
	)
	
	return WorkoutLoggingStates.SELECT_EXERCISE