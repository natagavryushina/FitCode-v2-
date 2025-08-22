from __future__ import annotations

import os
from datetime import datetime, date
from typing import Optional, Dict, Any
from enum import Enum as PyEnum

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    Date,
    JSON,
    Float,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    async_sessionmaker,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


DATA_DIR = os.path.join(os.getcwd(), "data")
DB_PATH = os.path.join(DATA_DIR, "bot.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"


class Base(AsyncAttrs, DeclarativeBase):
    pass


class SexEnum(str, PyEnum):
    MALE = "male"
    FEMALE = "female"


class LevelEnum(str, PyEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class GoalEnum(str, PyEnum):
    LOSS = "fat_loss"
    GAIN = "muscle_gain"
    MAINTAIN = "maintain"
    EVENT = "event_prep"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    goal: Mapped[Optional[str]] = mapped_column(String(50))
    level: Mapped[Optional[str]] = mapped_column(String(50))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    height_cm: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    sex: Mapped[Optional[str]] = mapped_column(String(10))
    diet_pref: Mapped[Optional[str]] = mapped_column(String(50))
    equipment: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    sessions_per_week: Mapped[Optional[int]] = mapped_column(Integer)

    workout_plans: Mapped[list[WorkoutPlan]] = relationship(back_populates="user")
    nutrition_plans: Mapped[list[NutritionPlan]] = relationship(back_populates="user")


class OnboardingState(Base):
    __tablename__ = "onboarding_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    state_name: Mapped[str] = mapped_column(String(50))
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, default={})


class WorkoutPlan(Base):
    __tablename__ = "workout_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    week_start: Mapped[date] = mapped_column(Date)
    plan: Mapped[Dict[str, Any]] = mapped_column(JSON)

    user: Mapped[User] = relationship(back_populates="workout_plans")


class NutritionPlan(Base):
    __tablename__ = "nutrition_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    calories: Mapped[int] = mapped_column(Integer)
    macros: Mapped[Dict[str, Any]] = mapped_column(JSON)
    menu: Mapped[Dict[str, Any]] = mapped_column(JSON)

    user: Mapped[User] = relationship(back_populates="nutrition_plans")


class ProgressEntry(Base):
    __tablename__ = "progress_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entry_date: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    chest_cm: Mapped[Optional[float]] = mapped_column(Float)
    waist_cm: Mapped[Optional[float]] = mapped_column(Float)
    hips_cm: Mapped[Optional[float]] = mapped_column(Float)
    photo_path: Mapped[Optional[str]] = mapped_column(String(255))


class MessageLog(Base):
    __tablename__ = "message_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


_engine = None
_Session: Optional[async_sessionmaker[AsyncSession]] = None


async def init_db() -> None:
    global _engine, _Session
    os.makedirs(DATA_DIR, exist_ok=True)
    _engine = create_async_engine(DB_URL, echo=False, future=True)
    _Session = async_sessionmaker(bind=_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    assert _Session is not None, "DB not initialized"
    return _Session


async def get_or_create_user(telegram_id: int) -> User:
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalar_one_or_none()
        if user:
            return user
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def update_user_profile(telegram_id: int, **fields: Any) -> User:
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalar_one()
        for k, v in fields.items():
            setattr(user, k, v)
        await session.commit()
        await session.refresh(user)
        return user


async def log_message(telegram_id: int, role: str, content: str) -> None:
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_id)
            session.add(user)
            await session.flush()
        entry = MessageLog(user_id=user.id, role=role, content=content)
        session.add(entry)
        await session.commit()


async def save_weekly_workout_plan(telegram_id: int, week_start: date, plan: Dict[str, Any]) -> WorkoutPlan:
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalar_one()
        # upsert by week_start
        res2 = await session.execute(
            select(WorkoutPlan).where(WorkoutPlan.user_id == user.id, WorkoutPlan.week_start == week_start)
        )
        existing = res2.scalar_one_or_none()
        if existing:
            existing.plan = plan
            await session.commit()
            await session.refresh(existing)
            return existing
        wp = WorkoutPlan(user_id=user.id, week_start=week_start, plan=plan)
        session.add(wp)
        await session.commit()
        await session.refresh(wp)
        return wp