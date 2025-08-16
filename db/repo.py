from __future__ import annotations

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from db.models import User, Message, Transcription, LLMRequest, LLMResponse


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