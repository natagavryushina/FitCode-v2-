from __future__ import annotations

from typing import Optional, Dict, Any
import json
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from db.models import User, Message, Transcription, LLMRequest, LLMResponse, WorkoutHistory, LoyaltyAccount, UserWorkoutPlan, UserWorkoutDay, MealPlan, MealDay, WorkoutCompletion, CompletedWorkout, CompletedExercise, TrainingProgram, ProgramWorkout, UserProgram


def get_or_create_user(session: Session, tg_user_id: str, username: str | None, first_name: str | None, last_name: str | None) -> User:
	user = session.query(User).filter_by(tg_user_id=tg_user_id).one_or_none()
	if user:
		return user
	user = User(tg_user_id=tg_user_id, username=username, first_name=first_name, last_name=last_name)
	session.add(user)
	session.flush()
	return user


def add_message(session: Session, user_id: int, direction: str, type_: str, content: str) -> Message:
	msg = Message(user_id=user_id, direction=direction, type=type_, content=content)
	session.add(msg)
	session.flush()
	return msg


def add_transcription(session: Session, user_id: int, telegram_file_id: str, text: str, audio_duration_sec: int | None, format_: str | None) -> Transcription:
	tr = Transcription(
		user_id=user_id,
		telegram_file_id=telegram_file_id,
		text=text,
		audio_duration_sec=audio_duration_sec or 0,
		format=format_ or "unknown",
	)
	session.add(tr)
	session.flush()
	return tr


def add_llm_exchange(session: Session, user_id: int | None, provider: str, model: str, prompt: str, categories_json: str, response_text: str, usage: Dict[str, Any] | None) -> tuple[LLMRequest, LLMResponse]:
	req = LLMRequest(user_id=user_id, provider=provider, model=model, prompt=prompt, categories_json=categories_json)
	session.add(req)
	session.flush()
	resp = LLMResponse(request_id=req.id, content=response_text, tokens_prompt=(usage or {}).get("prompt_tokens"), tokens_completion=(usage or {}).get("completion_tokens"))
	session.add(resp)
	session.flush()
	return req, resp


def get_user_pref(session: Session, user: User, key: str, default: Any = None) -> Any:
	try:
		prefs = json.loads(user.preferences_json or "{}")
		return prefs.get(key, default)
	except Exception:
		return default


def set_user_pref(session: Session, user: User, key: str, value: Any) -> None:
	try:
		prefs = json.loads(user.preferences_json or "{}")
	except Exception:
		prefs = {}
	prefs[key] = value
	user.preferences_json = json.dumps(prefs, ensure_ascii=False)
	session.add(user)
	session.flush()


def add_workout_history(session: Session, user_id: int, uniqueness_hash: str, content_text: str, payload: Dict[str, Any] | None = None) -> WorkoutHistory:
	wh = WorkoutHistory(user_id=user_id, uniqueness_hash=uniqueness_hash, content_text=content_text, payload_json=json.dumps(payload or {}, ensure_ascii=False))
	session.add(wh)
	session.flush()
	return wh


def has_recent_workout(session: Session, user_id: int, uniqueness_hash: str) -> bool:
	exists = session.execute(select(WorkoutHistory.id).where(WorkoutHistory.user_id == user_id, WorkoutHistory.uniqueness_hash == uniqueness_hash)).first()
	return exists is not None


def add_loyalty_points(session: Session, user_id: int, delta: int) -> LoyaltyAccount:
	acc = session.get(LoyaltyAccount, user_id)
	if not acc:
		acc = LoyaltyAccount(user_id=user_id, points=0)
		session.add(acc)
		session.flush()
	acc.points = (acc.points or 0) + delta
	session.add(acc)
	session.flush()
	return acc


def get_or_create_active_workout_plan(session: Session, user_id: int, start_date_str: str, end_date_str: str) -> UserWorkoutPlan:
	plan = session.execute(
		select(UserWorkoutPlan).where(
			and_(UserWorkoutPlan.user_id == user_id, UserWorkoutPlan.start_date == start_date_str, UserWorkoutPlan.is_active == 1)
		)
	).scalar_one_or_none()
	if plan:
		return plan
	plan = UserWorkoutPlan(user_id=user_id, start_date=start_date_str, end_date=end_date_str, is_active=1)
	session.add(plan)
	session.flush()
	return plan


def upsert_workout_day(session: Session, plan_id: int, day_index: int, title: str, content_text: str) -> UserWorkoutDay:
	day = session.execute(select(UserWorkoutDay).where(and_(UserWorkoutDay.plan_id == plan_id, UserWorkoutDay.day_index == day_index))).scalar_one_or_none()
	if day:
		day.title = title
		day.content_text = content_text
	else:
		day = UserWorkoutDay(plan_id=plan_id, day_index=day_index, title=title, content_text=content_text)
		session.add(day)
	session.flush()
	return day


def get_workout_day(session: Session, plan_id: int, day_index: int) -> Optional[UserWorkoutDay]:
	return session.execute(select(UserWorkoutDay).where(and_(UserWorkoutDay.plan_id == plan_id, UserWorkoutDay.day_index == day_index))).scalar_one_or_none()


def get_or_create_active_meal_plan(session: Session, user_id: int, start_date_str: str, end_date_str: str) -> MealPlan:
	plan = session.execute(
		select(MealPlan).where(and_(MealPlan.user_id == user_id, MealPlan.start_date == start_date_str, MealPlan.is_active == 1))
	).scalar_one_or_none()
	if plan:
		return plan
	plan = MealPlan(user_id=user_id, start_date=start_date_str, end_date=end_date_str, is_active=1)
	session.add(plan)
	session.flush()
	return plan


def upsert_meal_day(session: Session, meal_plan_id: int, day_index: int, title: str, content_text: str) -> MealDay:
	day = session.execute(select(MealDay).where(and_(MealDay.meal_plan_id == meal_plan_id, MealDay.day_index == day_index))).scalar_one_or_none()
	if day:
		day.title = title
		day.content_text = content_text
	else:
		day = MealDay(meal_plan_id=meal_plan_id, day_index=day_index, title=title, content_text=content_text)
		session.add(day)
	session.flush()
	return day


def get_meal_day(session: Session, meal_plan_id: int, day_index: int) -> Optional[MealDay]:
	return session.execute(select(MealDay).where(and_(MealDay.meal_plan_id == meal_plan_id, MealDay.day_index == day_index))).scalar_one_or_none()


def mark_workout_completed(session: Session, user_id: int, plan_id: int, day_index: int) -> WorkoutCompletion:
	rec = session.execute(select(WorkoutCompletion).where(and_(WorkoutCompletion.user_id == user_id, WorkoutCompletion.plan_id == plan_id, WorkoutCompletion.day_index == day_index))).scalar_one_or_none()
	if rec:
		return rec
	rec = WorkoutCompletion(user_id=user_id, plan_id=plan_id, day_index=day_index, status="done")
	session.add(rec)
	session.flush()
	return rec


def is_workout_completed(session: Session, user_id: int, plan_id: int, day_index: int) -> bool:
	rec = session.execute(select(WorkoutCompletion.id).where(and_(WorkoutCompletion.user_id == user_id, WorkoutCompletion.plan_id == plan_id, WorkoutCompletion.day_index == day_index))).first()
	return rec is not None


def update_user_fields(session: Session, user: User, **fields: Any) -> User:
	for k, v in fields.items():
		setattr(user, k, v)
	session.add(user)
	session.flush()
	return user


def set_user_list_pref(session: Session, user: User, key: str, values: list[str]) -> None:
	prefs = {}
	try:
		prefs = json.loads(user.preferences_json or "{}")
	except Exception:
		prefs = {}
	prefs[key] = values
	user.preferences_json = json.dumps(prefs, ensure_ascii=False)
	session.add(user)
	session.flush()


# Новые функции для работы с выполненными тренировками
def create_completed_workout(session: Session, user_id: int, plan_id: int | None, workout_type: str, duration: int, notes: str | None = None) -> 'CompletedWorkout':
	"""Создание новой выполненной тренировки"""
	
	workout = CompletedWorkout(
		user_id=user_id,
		plan_id=plan_id,
		workout_type=workout_type,
		duration=duration,
		notes=notes
	)
	session.add(workout)
	session.flush()
	return workout


def add_completed_exercise(session: Session, workout_id: int, exercise_name: str, sets: int, reps: int, weight: float | None = None, rpe: int | None = None, notes: str | None = None) -> 'CompletedExercise':
	"""Добавление выполненного упражнения к тренировке"""
	
	exercise = CompletedExercise(
		workout_id=workout_id,
		exercise_name=exercise_name,
		sets=sets,
		reps=reps,
		weight=weight,
		rpe=rpe,
		notes=notes
	)
	session.add(exercise)
	session.flush()
	return exercise


def update_workout_volume(session: Session, workout_id: int) -> None:
	"""Обновление общего объема тренировки на основе упражнений"""
	
	workout = session.get(CompletedWorkout, workout_id)
	if not workout:
		return
	
	# Вычисляем общий объем
	total_volume = 0
	exercises = session.query(CompletedExercise).filter_by(workout_id=workout_id).all()
	
	for exercise in exercises:
		if exercise.weight and exercise.sets and exercise.reps:
			total_volume += exercise.weight * exercise.sets * exercise.reps
	
	workout.total_volume = total_volume
	session.add(workout)
	session.flush()


def get_user_workout_history(session: Session, user_id: int, limit: int = 10) -> list['CompletedWorkout']:
	"""Получение истории тренировок пользователя"""
	
	return session.query(CompletedWorkout).filter_by(user_id=user_id).order_by(CompletedWorkout.workout_date.desc()).limit(limit).all()


def get_workout_exercises(session: Session, workout_id: int) -> list['CompletedExercise']:
	"""Получение всех упражнений для конкретной тренировки"""
	
	return session.query(CompletedExercise).filter_by(workout_id=workout_id).order_by(CompletedExercise.created_at).all()


def get_user_exercise_stats(session: Session, user_id: int, exercise_name: str, days: int = 30) -> list[tuple]:
	"""Получение статистики по конкретному упражнению за последние N дней"""
	from datetime import datetime, timedelta
	
	# Вычисляем дату начала периода
	start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
	
	# Получаем все тренировки пользователя за период
	workouts = session.query(CompletedWorkout).filter(
		CompletedWorkout.user_id == user_id,
		CompletedWorkout.workout_date >= start_date
	).all()
	
	workout_ids = [w.id for w in workouts]
	
	# Получаем упражнения
	exercises = session.query(CompletedExercise).filter(
		CompletedExercise.workout_id.in_(workout_ids),
		CompletedExercise.exercise_name == exercise_name
	).all()
	
	# Возвращаем данные для анализа прогресса
	stats = []
	for exercise in exercises:
		stats.append((
			exercise.workout.workout_date,
			exercise.sets,
			exercise.reps,
			exercise.weight,
			exercise.rpe
		))
	
	return stats


# Функции для работы с готовыми тренировочными программами
def get_all_training_programs(session: Session, active_only: bool = True) -> list['TrainingProgram']:
	"""Получение всех доступных тренировочных программ"""
	
	query = session.query(TrainingProgram)
	if active_only:
		query = query.filter_by(is_active=True)
	
	return query.order_by(TrainingProgram.name).all()


def get_training_program_by_id(session: Session, program_id: int) -> Optional['TrainingProgram']:
	"""Получение программы по ID"""
	
	return session.get(TrainingProgram, program_id)


def get_training_programs_by_goal(session: Session, goal: str, level: str | None = None) -> list['TrainingProgram']:
	"""Получение программ по цели и уровню"""
	
	query = session.query(TrainingProgram).filter_by(goal=goal, is_active=True)
	if level:
		query = query.filter_by(level=level)
	
	return query.order_by(TrainingProgram.name).all()


def get_program_workouts(session: Session, program_id: int, week_number: int | None = None) -> list['ProgramWorkout']:
	"""Получение тренировок программы для конкретной недели или всех"""
	
	query = session.query(ProgramWorkout).filter_by(program_id=program_id)
	if week_number is not None:
		query = query.filter_by(week_number=week_number)
	
	return query.order_by(ProgramWorkout.week_number, ProgramWorkout.day_number).all()


def get_user_active_program(session: Session, user_id: int) -> Optional['UserProgram']:
	"""Получение активной программы пользователя"""
	
	return session.query(UserProgram).filter_by(
		user_id=user_id,
		is_completed=False
	).first()


def start_user_program(session: Session, user_id: int, program_id: int) -> 'UserProgram':
	"""Начало программы пользователем"""
	
	# Проверяем, нет ли уже активной программы
	existing = get_user_active_program(session, user_id)
	if existing:
		raise ValueError("У пользователя уже есть активная программа")
	
	user_program = UserProgram(
		user_id=user_id,
		program_id=program_id,
		start_date=datetime.utcnow(),
		current_week=1,
		current_day=1,
		completed_workouts=[]
	)
	
	session.add(user_program)
	session.flush()
	return user_program


def complete_program_workout(session: Session, user_program_id: int, week: int, day: int) -> None:
	"""Отметка тренировки как выполненной"""
	
	user_program = session.get(UserProgram, user_program_id)
	if not user_program:
		return
	
	# Добавляем тренировку в список выполненных
	completed = user_program.completed_workouts or []
	workout_key = f"{week}_{day}"
	
	if workout_key not in completed:
		completed.append(workout_key)
		user_program.completed_workouts = completed
	
	# Обновляем текущий день/неделю
	if day < user_program.program.days_per_week:
		user_program.current_day = day + 1
	else:
		user_program.current_week += 1
		user_program.current_day = 1
	
	# Проверяем завершение программы
	if user_program.current_week > user_program.program.duration_weeks:
		user_program.is_completed = True
	
	session.add(user_program)
	session.flush()


def get_user_program_progress(session: Session, user_program_id: int) -> Dict[str, Any]:
	"""Получение прогресса пользователя по программе"""
	
	user_program = session.get(UserProgram, user_program_id)
	if not user_program:
		return {}
	
	program = user_program.program
	total_workouts = program.duration_weeks * program.days_per_week
	completed_count = len(user_program.completed_workouts or [])
	
	return {
		'current_week': user_program.current_week,
		'current_day': user_program.current_day,
		'total_weeks': program.duration_weeks,
		'days_per_week': program.days_per_week,
		'completed_workouts': completed_count,
		'total_workouts': total_workouts,
		'progress_percent': (completed_count / total_workouts * 100) if total_workouts > 0 else 0,
		'is_completed': user_program.is_completed
	}