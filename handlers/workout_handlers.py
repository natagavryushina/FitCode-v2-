from __future__ import annotations

from typing import Dict, Any, List

from telegram import Update
from telegram.ext import ContextTypes

from services.workout_manager import WeeklyWorkoutManager
from database import get_sessionmaker, User


mgr = WeeklyWorkoutManager()


async def show_weekly_schedule(update: Update, weekly_plan) -> None:
    from sqlalchemy import select
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(type(weekly_plan)).where(type(weekly_plan).id == weekly_plan.id))
        w = res.scalar_one()
        res_dw = await session.execute(select(__import__('database').DailyWorkout).where(__import__('database').DailyWorkout.weekly_plan_id == w.id).order_by(__import__('database').DailyWorkout.day_number.asc()))
        dws = res_dw.scalars().all()
        lines = [f"План недели ({w.focus_type}):"]
        for dw in dws:
            lines.append(f"День {dw.day_number}: {dw.muscle_group} — объём {dw.total_volume or 0}")
    await update.message.reply_text("\n".join(lines))


def format_daily_workout_message(daily: Dict[str, Any]) -> str:
    lines = [f"*День {daily['day_number']}* — {daily['muscle_group']} ({daily['workout_type']})"]
    for ex in daily.get('exercises', []):
        w = ex.get('weight')
        wtxt = f", {w} кг" if w else ""
        lines.append(f"• {ex['name']}: {ex['sets']}x{ex['reps']}{wtxt}, отдых {ex['rest']}с, RPE {ex['rpe']}")
    return "\n".join(lines)


def parse_workout_completion(args: List[str]) -> Dict[str, Any]:
    # Expected format: session_id:sets:reps_csv[:weight] ...
    sessions = []
    for token in args or []:
        parts = token.split(':')
        if len(parts) < 3:
            continue
        sid = int(parts[0])
        sets = int(parts[1])
        reps = parts[2]
        weight = float(parts[3]) if len(parts) > 3 else None
        sessions.append({"session_id": sid, "sets": sets, "reps": reps, "weight": weight})
    return {"sessions": sessions}


async def send_weekly_plan_notification(telegram_id: int, weekly_plan) -> None:
    # This function can be implemented using application.bot in context; placeholder here
    pass


async def handle_weekly_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать недельный план тренировок"""
    user_id = update.effective_user.id
    weekly_plan = await mgr.get_current_weekly_plan(user_id)
    if not weekly_plan:
        weekly_plan = await mgr.generate_weekly_plan(user_id)
    await show_weekly_schedule(update, weekly_plan)


async def handle_daily_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сегодняшнюю тренировку"""
    user_id = update.effective_user.id
    daily_workout = await mgr.get_today_workout(user_id)
    message = format_daily_workout_message(daily_workout)
    await update.message.reply_text(message, parse_mode='Markdown')


async def log_workout_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запись выполненной тренировки"""
    user_id = update.effective_user.id
    workout_data = parse_workout_completion(context.args)
    await mgr.log_completion(user_id, workout_data)
    await update.message.reply_text("✅ Тренировка записана! Отличная работа!")


async def auto_update_weekly_plans(context: ContextTypes.DEFAULT_TYPE):
    """Автоматическое обновление планов в воскресенье вечером"""
    # Placeholder user repository: fetch all users
    Session = get_sessionmaker()
    async with Session() as session:
        from sqlalchemy import select
        users = (await session.execute(select(User))).scalars().all()
        for user in users:
            new_plan = await mgr.generate_weekly_plan(user.telegram_id)
            # send notification can be wired with context.application.bot later
            # await send_weekly_plan_notification(user.telegram_id, new_plan)