from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Any, List

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from database import get_or_create_user, save_weekly_workout_plan, get_sessionmaker, DailyWorkout, WeeklyWorkoutPlan, ExerciseSession
from ai_agents import query_memory, generate_workout
from services.progression import start_weekly_plan, apply_session_result
from services.workout_manager import WeeklyWorkoutManager


TRAIN_CB_PREFIX = "menu:training"


async def train_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    mem = query_memory(user.telegram_id, "тренировки предпочтения", n=5)
    plan = generate_workout(user, today_weekday=date.today().weekday(), memory_context=mem)

    lines = [f"🏋️ Сегодня: {plan.get('name','')}"]
    for ex in plan.get("exercises", []):
        lines.append(f"- {ex['name']}: {ex['sets']}x{ex['reps']} отдых {ex['rest_s']}с")
        if ex.get("technique"):
            lines.append(f"  техника: {ex['technique']}")
    await update.message.reply_text("\n".join(lines))


async def plan_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    mem = query_memory(user.telegram_id, "история тренировки цели", n=8)
    week_start = date.today() - timedelta(days=date.today().weekday())
    days: List[str] = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    week_plan: Dict[str, Any] = {}
    for i in range(7):
        p = generate_workout(user, today_weekday=i, memory_context=mem)
        week_plan[days[i]] = p
    await save_weekly_workout_plan(user.telegram_id, week_start, week_plan)
    text_lines = ["План на неделю:"]
    for d in days:
        text_lines.append(f"\n{d}: {week_plan[d].get('name','')}")
    await update.message.reply_text("\n".join(text_lines))


async def start_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    focus = (context.args[0] if context.args else (user.goal or "hypertrophy")).lower()
    if focus not in ("strength", "hypertrophy", "endurance"):
        focus = "hypertrophy"
    week_start = date.today() - timedelta(days=date.today().weekday())
    w = await start_weekly_plan(user, week_start, focus)
    await update.message.reply_text(f"Стартовал недельный план ({focus}). Дней: {len(w.daily_workouts)}")


async def complete_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        session_id = int(context.args[0])
        actual_sets = int(context.args[1])
        actual_reps = [int(x) for x in context.args[2].split(',')]
        actual_weight = float(context.args[3]) if len(context.args) > 3 else None
    except Exception:
        await update.message.reply_text("Формат: /complete_set <session_id> <sets> <r1,r2,...> [weight]")
        return
    success, next_load = await apply_session_result(session_id, actual_sets, actual_reps, actual_weight)
    msg = "✅ Успех!" if success else "⚠️ Не все цели достигнуты."
    if next_load is not None:
        msg += f" Следующая рекомендуемая нагрузка: {next_load} кг"
    await update.message.reply_text(msg)


async def complete_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        day_id = int(context.args[0])
    except Exception:
        await update.message.reply_text("Формат: /complete_day <daily_workout_id>")
        return
    Session = get_sessionmaker()
    async with Session() as session:
        from sqlalchemy import select
        res = await session.execute(select(DailyWorkout).where(DailyWorkout.id == day_id))
        dw = res.scalar_one()
        dw.total_volume = float(dw.total_volume or 0.0)  # could compute from sessions
        await session.commit()
    await update.message.reply_text("День отмечен завершенным.")


async def complete_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        week_id = int(context.args[0])
    except Exception:
        await update.message.reply_text("Формат: /complete_week <weekly_plan_id>")
        return
    Session = get_sessionmaker()
    async with Session() as session:
        from sqlalchemy import select
        res = await session.execute(select(WeeklyWorkoutPlan).where(WeeklyWorkoutPlan.id == week_id))
        w = res.scalar_one()
        w.is_completed = True
        await session.commit()
    await update.message.reply_text("Неделя закрыта. Отличная работа!")


async def training_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Раздел тренировки: /start_week <focus>, /complete_set, /complete_day, /complete_week, /train_today, /plan_week.")


async def start_week_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mgr = WeeklyWorkoutManager()
    week = await mgr.generate_weekly_plan(update.effective_user.id)
    Session = get_sessionmaker()
    async with Session() as session:
        from sqlalchemy import select
        res = await session.execute(select(DailyWorkout).where(DailyWorkout.weekly_plan_id == week.id).order_by(DailyWorkout.day_number.asc()))
        dws = res.scalars().all()
        lines = [f"План недели ({week.focus_type}):"]
        for dw in dws:
            lines.append(f"День {dw.day_number}: {dw.muscle_group} — объём {dw.total_volume or 0}")
    await update.message.reply_text("\n".join(lines))


def register_training_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("train_today", train_today))
    app.add_handler(CommandHandler("plan_week", plan_week))
    app.add_handler(CommandHandler("start_week", start_week))
    app.add_handler(CommandHandler("complete_set", complete_set))
    app.add_handler(CommandHandler("complete_day", complete_day))
    app.add_handler(CommandHandler("complete_week", complete_week))
    app.add_handler(CommandHandler("start_week_auto", start_week_auto))
    app.add_handler(CallbackQueryHandler(training_menu_handler, pattern=f"^{TRAIN_CB_PREFIX}$"))