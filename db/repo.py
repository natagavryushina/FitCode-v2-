from __future__ import annotations

from typing import Optional, Dict, Any
import json
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from db.models import User, Message, Transcription, LLMRequest, LLMResponse, WorkoutHistory, LoyaltyAccount, UserWorkoutPlan, UserWorkoutDay, MealPlan, MealDay, WorkoutCompletion


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