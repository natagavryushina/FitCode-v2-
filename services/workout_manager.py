from __future__ import annotations

from typing import List, Optional, Dict, Any
from datetime import date, timedelta

from sqlalchemy import select

from database import (
    get_sessionmaker,
    User,
    WeeklyWorkoutPlan,
    DailyWorkout,
    ExerciseSession,
)
from services.progression import start_weekly_plan


class WeeklyWorkoutManager:
    async def generate_weekly_plan(self, user_id: int) -> WeeklyWorkoutPlan:
        """Генерация нового недельного плана на основе прогресса.
        user_id — telegram_id пользователя
        """
        user = await self.get_user_data(user_id)
        progress = await self.get_user_progress(user.id)

        new_volume = self.calculate_new_volume(user, progress)
        new_intensity = self.calculate_new_intensity(user, progress)

        return await self.create_weekly_plan(user, new_volume, new_intensity)

    async def get_user_data(self, telegram_id: int) -> User:
        Session = get_sessionmaker()
        async with Session() as session:
            res = await session.execute(select(User).where(User.telegram_id == telegram_id))
            return res.scalar_one()

    async def get_user_progress(self, user_pk: int) -> List[Dict[str, Any]]:
        """Возвращает список прогресс-слепков. Сейчас — только за последнюю неделю.
        Формат: { total_volume: float, avg_rpe: float, completion_rate: float }
        """
        Session = get_sessionmaker()
        async with Session() as session:
            res = await session.execute(
                select(WeeklyWorkoutPlan)
                .where(WeeklyWorkoutPlan.user_id == user_pk)
                .order_by(WeeklyWorkoutPlan.start_date.desc())
                .limit(1)
            )
            week = res.scalar_one_or_none()
            if not week:
                return []
            # gather sessions
            res_dw = await session.execute(select(DailyWorkout).where(DailyWorkout.weekly_plan_id == week.id))
            dws = res_dw.scalars().all()
            total_volume = 0.0
            rpes: List[int] = []
            completed = 0
            total_sessions = 0
            for dw in dws:
                res_s = await session.execute(select(ExerciseSession).where(ExerciseSession.daily_workout_id == dw.id))
                sessions = res_s.scalars().all()
                for s in sessions:
                    total_sessions += 1
                    if s.rpe is not None:
                        rpes.append(s.rpe)
                    # volume estimate: use actual if present, else target
                    if s.actual_weight and s.actual_reps:
                        vol = float(s.actual_weight) * float(sum(s.actual_reps))
                    else:
                        try:
                            low = int((s.target_reps or "0").split("-")[0])
                        except Exception:
                            low = 0
                        vol = float(s.target_weight or 0.0) * float(low * (s.target_sets or 0))
                    total_volume += vol
                    if s.is_completed:
                        completed += 1
            avg_rpe = (sum(rpes) / len(rpes)) if rpes else 7.5
            completion_rate = (completed / total_sessions) if total_sessions else 0.0
            return [{
                "total_volume": round(total_volume, 2),
                "avg_rpe": round(avg_rpe, 2),
                "completion_rate": round(completion_rate, 3),
            }]

    def calculate_new_volume(self, user: User, progress: List[Dict[str, Any]]) -> float:
        """Расчет нового тренировочного объема с прогрессией 5-10%. По умолчанию — +7%."""
        last_volume = progress[-1]['total_volume'] if progress else 0.0
        progression_rate = 0.07  # 7% прогрессия
        base = last_volume if last_volume > 0 else 5000.0  # разумная стартовая оценка объема
        return round(base * (1 + progression_rate), 2)

    def calculate_new_intensity(self, user: User, progress: List[Dict[str, Any]]) -> float:
        """Расчет интенсивности (множитель к рабочим весам) по RPE и выполнению.
        Диапазон 0.90..1.10
        """
        if not progress:
            return 1.0
        p = progress[-1]
        avg_rpe = p.get('avg_rpe', 7.5)
        completion = p.get('completion_rate', 0.0)
        factor = 1.0
        if completion >= 0.9 and avg_rpe <= 7.5:
            factor += 0.03
        elif completion >= 0.8 and avg_rpe <= 8.0:
            factor += 0.02
        elif completion < 0.6 or avg_rpe >= 9.0:
            factor -= 0.05
        # clamp
        factor = max(0.90, min(1.10, factor))
        return round(factor, 3)

    async def create_weekly_plan(self, user: User, new_volume: float, new_intensity: float) -> WeeklyWorkoutPlan:
        """Создать план, скорректировать target_weight и распределить объем."""
        focus_map = {
            "fat_loss": "endurance",
            "muscle_gain": "hypertrophy",
            "maintain": "hypertrophy",
            "event_prep": "strength",
        }
        focus = focus_map.get((user.goal or "maintain"), "hypertrophy")
        start = date.today() - timedelta(days=date.today().weekday())
        week = await start_weekly_plan(user, start, focus)

        # adjust weights by intensity and compute volumes
        Session = get_sessionmaker()
        async with Session() as session:
            res_dw = await session.execute(select(DailyWorkout).where(DailyWorkout.weekly_plan_id == week.id))
            dws = res_dw.scalars().all()
            # first pass: apply intensity
            for dw in dws:
                res_s = await session.execute(select(ExerciseSession).where(ExerciseSession.daily_workout_id == dw.id))
                sessions = res_s.scalars().all()
                for s in sessions:
                    if s.target_weight is not None:
                        s.target_weight = round(float(s.target_weight) * new_intensity, 2)
                await session.flush()
            # compute current estimated total
            def est_volume_for_day(dw_id: int) -> float:
                return 0.0
            total_est = 0.0
            for dw in dws:
                res_s = await session.execute(select(ExerciseSession).where(ExerciseSession.daily_workout_id == dw.id))
                sessions = res_s.scalars().all()
                day_vol = 0.0
                for s in sessions:
                    try:
                        reps_low = int((s.target_reps or "0").split("-")[0])
                    except Exception:
                        reps_low = 0
                    day_vol += float(s.target_weight or 0.0) * float(reps_low * (s.target_sets or 0))
                dw.total_volume = round(day_vol, 2)
                total_est += day_vol
            # scale to match new_volume if possible
            if total_est > 0 and new_volume > 0:
                scale = new_volume / total_est
                for dw in dws:
                    res_s = await session.execute(select(ExerciseSession).where(ExerciseSession.daily_workout_id == dw.id))
                    sessions = res_s.scalars().all()
                    for s in sessions:
                        if s.target_weight is not None:
                            s.target_weight = round(float(s.target_weight) * scale, 2)
                    # recompute day volume
                    day_vol = 0.0
                    for s in sessions:
                        try:
                            reps_low = int((s.target_reps or "0").split("-")[0])
                        except Exception:
                            reps_low = 0
                        day_vol += float(s.target_weight or 0.0) * float(reps_low * (s.target_sets or 0))
                    dw.total_volume = round(day_vol, 2)
            await session.commit()

        return week