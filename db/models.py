from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, CheckConstraint
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