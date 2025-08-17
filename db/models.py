from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, CheckConstraint, UniqueConstraint
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