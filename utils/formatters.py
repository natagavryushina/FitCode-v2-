from __future__ import annotations

from typing import List

from database import DailyWorkout, WeeklyWorkoutPlan, ExerciseSession


def _fmt_weight(kg: float | None) -> str:
    return f"{kg:g} кг" if kg is not None else "—"


def format_daily_workout_message(workout: DailyWorkout) -> str:
    message = f"🏋️‍♂️ *Тренировка на сегодня* ({workout.muscle_group})\n\n"
    sessions: List[ExerciseSession] = getattr(workout, "exercise_sessions", [])
    for exercise in sessions:
        name = getattr(getattr(exercise, "exercise", None), "name", "Упражнение")
        message += f"*{name}*\n"
        message += f"• Подходы: {exercise.target_sets or 0}\n"
        message += f"• Повторы: {exercise.target_reps or '-'}\n"
        message += f"• Вес: {_fmt_weight(exercise.target_weight)}\n"
        message += f"• Отдых: {exercise.rest_time_seconds or 0} сек\n"
        message += f"• RPE: {exercise.rpe or 0}/10\n\n"

    message += f"⏱ Общее время: {int(workout.duration_minutes or 0)} мин\n"
    message += f"📊 Общий объем: {workout.total_volume or 0:g} кг\n"
    return message


def format_weekly_schedule_message(plan: WeeklyWorkoutPlan) -> str:
    message = "📅 *План тренировок на неделю*\n\n"
    for day in getattr(plan, "daily_workouts", []) or []:
        message += f"*День {day.day_number}:* {day.muscle_group}\n"
        message += f"Тип: {day.workout_type}\n"
        message += f"Длительность: {int(day.duration_minutes or 0)} мин\n\n"
    return message