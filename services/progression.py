from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta

from sqlalchemy import select

from database import (
    get_sessionmaker,
    Exercise,
    WeeklyWorkoutPlan,
    DailyWorkout,
    ExerciseSession,
    User,
)


EXERCISES_SEED: List[Dict[str, str]] = [
    {"name": "Приседания со штангой", "primary_muscle": "legs", "equipment": "barbell", "is_bodyweight": "0"},
    {"name": "Жим лёжа", "primary_muscle": "chest", "equipment": "barbell", "is_bodyweight": "0"},
    {"name": "Тяга штанги в наклоне", "primary_muscle": "back", "equipment": "barbell", "is_bodyweight": "0"},
    {"name": "Становая тяга", "primary_muscle": "posterior_chain", "equipment": "barbell", "is_bodyweight": "0"},
    {"name": "Жим гантелей сидя", "primary_muscle": "shoulders", "equipment": "dumbbell", "is_bodyweight": "0"},
    {"name": "Подтягивания", "primary_muscle": "back", "equipment": "bar", "is_bodyweight": "1"},
    {"name": "Отжимания", "primary_muscle": "chest", "equipment": "floor", "is_bodyweight": "1"},
    {"name": "Планка", "primary_muscle": "core", "equipment": "floor", "is_bodyweight": "1"},
]


@dataclass
class Target:
    sets: int
    reps_low: int
    reps_high: int
    rpe: int
    progression_pct: float  # % load increase if easy


HYPERTROPHY = Target(sets=3, reps_low=8, reps_high=12, rpe=7, progression_pct=0.025)
STRENGTH = Target(sets=5, reps_low=3, reps_high=5, rpe=8, progression_pct=0.02)
ENDURANCE = Target(sets=3, reps_low=15, reps_high=20, rpe=6, progression_pct=0.03)


def _rep_range_str(t: Target) -> str:
    return f"{t.reps_low}-{t.reps_high}"


async def seed_exercises() -> None:
    Session = get_sessionmaker()
    async with Session() as session:
        existing = {e.name for e in (await session.execute(select(Exercise))).scalars().all()}
        new = []
        for ex in EXERCISES_SEED:
            if ex["name"] in existing:
                continue
            new.append(
                Exercise(
                    name=ex["name"],
                    primary_muscle=ex["primary_muscle"],
                    equipment=ex["equipment"],
                    is_bodyweight=(ex["is_bodyweight"] == "1"),
                )
            )
        if new:
            session.add_all(new)
            await session.commit()


def _next_load(current: Optional[float], success: bool, target: Target) -> Optional[float]:
    if current is None:
        return None
    if success:
        return round(current * (1.0 + target.progression_pct), 2)
    else:
        # failed: reduce slightly
        return max(0.0, round(current * 0.97, 2))


def _should_deload(fail_streak: int) -> bool:
    return fail_streak >= 3


async def start_weekly_plan(user: User, start: date, focus: str) -> WeeklyWorkoutPlan:
    Session = get_sessionmaker()
    async with Session() as session:
        week_number = int(start.strftime("%G%V"))
        w = WeeklyWorkoutPlan(
            user_id=user.id,
            week_number=week_number,
            start_date=datetime.combine(start, datetime.min.time()),
            end_date=datetime.combine(start + timedelta(days=6), datetime.min.time()),
            focus_type=focus,
        )
        session.add(w)
        await session.flush()

        # Template split: Upper/Lower/Upper/Lower + accessories, rest days as needed
        days = [
            (1, "upper", "strength" if focus == "strength" else focus),
            (2, "lower", "strength" if focus == "strength" else focus),
            (3, "rest", "rest"),
            (4, "upper", focus),
            (5, "lower", focus),
            (6, "cardio", "endurance"),
            (7, "rest", "rest"),
        ]
        for dnum, mg, wtype in days:
            dw = DailyWorkout(
                weekly_plan_id=w.id,
                day_number=dnum,
                muscle_group=mg,
                workout_type=wtype,
                duration_minutes=50 if wtype != "rest" else 0,
                total_volume=0.0,
            )
            session.add(dw)
            await session.flush()

            if wtype == "rest":
                continue

            # choose targets
            tgt = HYPERTROPHY if focus == "hypertrophy" else STRENGTH if focus == "strength" else ENDURANCE
            rep_range = _rep_range_str(tgt)

            # pick exercises
            res = await session.execute(select(Exercise))
            exercises = res.scalars().all()
            chosen: List[Exercise] = []
            if mg == "upper":
                for e in exercises:
                    if e.primary_muscle in ("chest", "back", "shoulders"):
                        chosen.append(e)
                    if len(chosen) >= 4:
                        break
            elif mg == "lower":
                for e in exercises:
                    if e.primary_muscle in ("legs", "posterior_chain"):
                        chosen.append(e)
                    if len(chosen) >= 3:
                        break
            elif mg == "cardio":
                chosen = [e for e in exercises if e.name == "Планка"]

            for ex in chosen:
                sess = ExerciseSession(
                    daily_workout_id=dw.id,
                    exercise_id=ex.id,
                    target_sets=tgt.sets,
                    target_reps=rep_range,
                    target_weight=20.0 if not ex.is_bodyweight else None,
                    rest_time_seconds=90,
                    rpe=tgt.rpe,
                    is_completed=False,
                )
                session.add(sess)

        await session.commit()
        await session.refresh(w)
        return w


async def apply_session_result(session_id: int, actual_sets: int, actual_reps: List[int], actual_weight: Optional[float]) -> Tuple[bool, Optional[float]]:
    """Store results and compute next target load suggestion.
    Returns (success, next_load)
    """
    Session = get_sessionmaker()
    async with Session() as db:
        res = await db.execute(select(ExerciseSession).where(ExerciseSession.id == session_id))
        es = res.scalar_one()
        es.actual_sets = actual_sets
        es.actual_reps = actual_reps
        es.actual_weight = actual_weight
        es.is_completed = True
        # success criteria: completed all sets with reps >= lower bound
        try:
            low = int(es.target_reps.split("-")[0]) if es.target_reps else 0
        except Exception:
            low = 0
        success = (actual_sets >= (es.target_sets or 0)) and all(r >= low for r in actual_reps)
        # compute next load suggestion
        tgt = HYPERTROPHY if (es.target_reps and low >= 8) else STRENGTH if (es.target_reps and low <= 5) else ENDURANCE
        next_load = _next_load(es.actual_weight or es.target_weight, success, tgt)
        await db.commit()
        return success, next_load