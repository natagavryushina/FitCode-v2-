from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy import select

from database import get_sessionmaker, User, WeeklyWorkoutPlan, DailyWorkout, ExerciseSession
from services.workout_manager import WeeklyWorkoutManager
from utils import format_daily_workout_message, format_weekly_schedule_message


class WorkoutReminderService:
    def __init__(self, bot):
        self.bot = bot
        self.mgr = WeeklyWorkoutManager()

    async def send_daily_reminders(self) -> None:
        """Отправка ежедневных напоминаний о тренировках"""
        Session = get_sessionmaker()
        async with Session() as session:
            users: List[User] = (await session.execute(select(User))).scalars().all()
            for user in users:
                # найти план текущей недели
                w = await self.mgr.get_current_weekly_plan(user.telegram_id)
                if not w:
                    continue
                dnum = date.today().weekday() + 1
                res_dw = await session.execute(
                    select(DailyWorkout).where(DailyWorkout.weekly_plan_id == w.id, DailyWorkout.day_number == dnum)
                )
                dw = res_dw.scalar_one_or_none()
                if not dw or (dw.workout_type == 'rest'):
                    continue
                # загрузить сессии
                await session.execute(select(ExerciseSession).where(ExerciseSession.daily_workout_id == dw.id))
                msg = format_daily_workout_message(dw)
                try:
                    await self.bot.send_message(chat_id=user.telegram_id, text=msg, parse_mode='Markdown')
                except Exception:
                    # Логировать можно через стандартный логгер, опускаем детали
                    pass

    async def send_weekly_preview(self) -> None:
        """Отправка анонса недельного плана в воскресенье"""
        # Воскресенье: 6
        if datetime.now().weekday() != 6:
            return
        Session = get_sessionmaker()
        async with Session() as session:
            users: List[User] = (await session.execute(select(User))).scalars().all()
            for user in users:
                weekly_plan = await self.mgr.generate_weekly_plan(user.telegram_id)
                msg = format_weekly_schedule_message(weekly_plan)
                try:
                    await self.bot.send_message(chat_id=user.telegram_id, text=msg, parse_mode='Markdown')
                except Exception:
                    pass