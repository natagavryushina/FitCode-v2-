from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, CheckConstraint, UniqueConstraint, Float, Boolean, DateTime, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
	__tablename__ = "users"

	id = Column(Integer, primary_key=True)
	tg_user_id = Column(String, unique=True, nullable=False)
	username = Column(String)
	first_name = Column(String)
	last_name = Column(String)
	sex = Column(String)
	birth_date = Column(String)
	height_cm = Column(Integer)
	weight_kg = Column(Integer)
	level = Column(String)
	activity_level = Column(String)
	injuries = Column(Text)
	allergies = Column(Text)
	diet_type = Column(String)
	preferences_json = Column(Text)
	timezone = Column(String)
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
	updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())

	messages = relationship("Message", back_populates="user")
	transcriptions = relationship("Transcription", back_populates="user")


class Message(Base):
	__tablename__ = "messages"

	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
	direction = Column(String)
	type = Column(String)
	content = Column(Text)
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())

	__table_args__ = (
		CheckConstraint("direction in ('in','out')", name="messages_direction_chk"),
		CheckConstraint("type in ('text','voice','system')", name="messages_type_chk"),
	)

	user = relationship("User", back_populates="messages")


class Transcription(Base):
	__tablename__ = "transcriptions"

	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
	telegram_file_id = Column(String)
	audio_duration_sec = Column(Integer)
	format = Column(String)
	text = Column(Text)
	confidence = Column(Integer)
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())

	user = relationship("User", back_populates="transcriptions")


class LLMRequest(Base):
	__tablename__ = "llm_requests"

	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey("users.id"))
	provider = Column(String)
	model = Column(String)
	prompt = Column(Text)
	categories_json = Column(Text)
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class LLMResponse(Base):
	__tablename__ = "llm_responses"

	id = Column(Integer, primary_key=True)
	request_id = Column(Integer, ForeignKey("llm_requests.id"), nullable=False)
	content = Column(Text)
	tokens_prompt = Column(Integer)
	tokens_completion = Column(Integer)
	metadata_json = Column(Text)
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class WorkoutHistory(Base):
	__tablename__ = "workout_history"

	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
	uniqueness_hash = Column(String, nullable=False)
	payload_json = Column(Text)
	content_text = Column(Text)
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())

	__table_args__ = (
		UniqueConstraint("user_id", "uniqueness_hash", name="uq_user_workout_hash"),
	)


class LoyaltyAccount(Base):
	__tablename__ = "loyalty_accounts"

	user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
	points = Column(Integer, default=0)
	updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class UserWorkoutPlan(Base):
	__tablename__ = "user_workout_plans"

	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
	start_date = Column(String)
	end_date = Column(String)
	is_active = Column(Integer, default=1)
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class UserWorkoutDay(Base):
	__tablename__ = "user_workout_days"

	id = Column(Integer, primary_key=True)
	plan_id = Column(Integer, ForeignKey("user_workout_plans.id"), nullable=False)
	day_index = Column(Integer)  # 0..6
	title = Column(String)
	content_text = Column(Text)

	__table_args__ = (
		UniqueConstraint("plan_id", "day_index", name="uq_workout_day_unique"),
	)


class MealPlan(Base):
	__tablename__ = "meal_plans"

	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
	start_date = Column(String)
	end_date = Column(String)
	is_active = Column(Integer, default=1)
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class MealDay(Base):
	__tablename__ = "meal_days"

	id = Column(Integer, primary_key=True)
	meal_plan_id = Column(Integer, ForeignKey("meal_plans.id"), nullable=False)
	day_index = Column(Integer)
	title = Column(String)
	content_text = Column(Text)

	__table_args__ = (
		UniqueConstraint("meal_plan_id", "day_index", name="uq_meal_day_unique"),
	)


class WorkoutCompletion(Base):
	__tablename__ = "workout_completions"

	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
	plan_id = Column(Integer, ForeignKey("user_workout_plans.id"), nullable=False)
	day_index = Column(Integer, nullable=False)
	status = Column(String, default="done")
	completed_at = Column(String, default=lambda: datetime.utcnow().isoformat())

	__table_args__ = (
		UniqueConstraint("user_id", "plan_id", "day_index", name="uq_workout_completion_unique"),
	)


class CompletedWorkout(Base):
	__tablename__ = 'completed_workouts'
	
	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	plan_id = Column(Integer, ForeignKey('user_workout_plans.id'), nullable=True)  # может быть null для свободных тренировок
	workout_date = Column(String, default=lambda: datetime.utcnow().isoformat())
	workout_type = Column(String)  # сила, кардио, выносливость, мобилити и т.д.
	duration = Column(Integer)  # длительность в минутах
	total_volume = Column(Float)  # общий объем (вес × повторения × подходы)
	rating = Column(Integer)  # оценка тренировки (1-5)
	notes = Column(Text)  # общие заметки
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
	
	# Связи
	exercises = relationship("CompletedExercise", back_populates="workout", cascade="all, delete-orphan")
	user = relationship("User")


class CompletedExercise(Base):
	__tablename__ = 'completed_exercises'
	
	id = Column(Integer, primary_key=True)
	workout_id = Column(Integer, ForeignKey('completed_workouts.id'), nullable=False)
	exercise_name = Column(String, nullable=False)
	sets = Column(Integer)  # количество подходов
	reps = Column(Integer)  # количество повторений
	weight = Column(Float)  # вес в кг
	rpe = Column(Integer)  # субъективная сложность (1-10)
	notes = Column(Text)  # заметки о технике
	created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
	
	# Связи
	workout = relationship("CompletedWorkout", back_populates="exercises")
	
	__table_args__ = (
		CheckConstraint("rpe >= 1 AND rpe <= 10", name="rpe_range_check"),
		CheckConstraint("sets > 0", name="sets_positive_check"),
		CheckConstraint("reps > 0", name="reps_positive_check"),
		CheckConstraint("weight >= 0", name="weight_non_negative_check"),
	)


class TrainingProgram(Base):
	__tablename__ = 'training_programs'
	
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)  # Название программы
	description = Column(Text)  # Описание программы
	goal = Column(String)  # Цель программы (похудение, масса, тонус)
	level = Column(String)  # Уровень сложности (начальный, средний, продвинутый)
	duration_weeks = Column(Integer)  # Продолжительность в неделях
	days_per_week = Column(Integer)  # Тренировок в неделю
	equipment = Column(String)  # Необходимое оборудование
	image_url = Column(String)  # URL изображения программы
	is_active = Column(Boolean, default=True)  # Активна ли программа
	created_at = Column(DateTime, default=datetime.utcnow)
	
	# Связи
	workouts = relationship("ProgramWorkout", back_populates="program", cascade="all, delete-orphan")
	user_programs = relationship("UserProgram", back_populates="program")


class ProgramWorkout(Base):
	__tablename__ = 'program_workouts'
	
	id = Column(Integer, primary_key=True)
	program_id = Column(Integer, ForeignKey('training_programs.id'), nullable=False)
	week_number = Column(Integer)  # Номер недели
	day_number = Column(Integer)  # Номер дня в неделе
	workout_type = Column(String)  # Тип тренировки
	muscle_groups = Column(String)  # Целевые группы мышц
	duration_minutes = Column(Integer)  # Примерная длительность
	exercises = Column(JSON)  # Упражнения в формате JSON
	
	# Связи
	program = relationship("TrainingProgram", back_populates="workouts")


class UserProgram(Base):
	__tablename__ = 'user_programs'
	
	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	program_id = Column(Integer, ForeignKey('training_programs.id'), nullable=False)
	start_date = Column(DateTime)  # Дата начала программы
	current_week = Column(Integer, default=1)  # Текущая неделя
	current_day = Column(Integer, default=1)  # Текущий день
	is_completed = Column(Boolean, default=False)  # Завершена ли программа
	completed_workouts = Column(JSON)  # Завершенные тренировки
	created_at = Column(DateTime, default=datetime.utcnow)
	
	# Связи
	user = relationship("User")
	program = relationship("TrainingProgram", back_populates="user_programs")