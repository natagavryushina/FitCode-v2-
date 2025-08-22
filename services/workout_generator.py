from __future__ import annotations

from typing import Dict, List

from database import User, WeeklyWorkoutPlan


class DailyWorkoutGenerator:
    def generate_daily_workout(self, user: User, day: int, weekly_plan: WeeklyWorkoutPlan) -> Dict:
        """Генерация тренировки на конкретный день.
        Возвращает словарь с полями day_number, muscle_group, workout_type, exercises, total_duration, total_volume.
        """
        focus = weekly_plan.focus_type or "hypertrophy"
        workout_template = self.get_workout_template(user, day, focus)
        intensity = getattr(weekly_plan, "intensity", 1.0) or 1.0

        workout_data: Dict = {
            "day_number": day,
            "muscle_group": self.get_muscle_group_for_day(day, (user.goal or "maintain")),
            "workout_type": self.get_workout_type(day),
            "exercises": [],
            "total_duration": 0,
            "total_volume": 0.0,
        }

        for exercise_template in workout_template["exercises"]:
            exercise = self.generate_exercise_details(
                exercise_template,
                (user.level or "beginner"),
                intensity,
            )
            workout_data["exercises"].append(exercise)
            workout_data["total_duration"] += exercise.get("estimated_duration", 0)
            workout_data["total_volume"] += exercise.get("volume", 0.0)

        workout_data["total_volume"] = round(float(workout_data["total_volume"]), 2)
        return workout_data

    def get_workout_template(self, user: User, day: int, focus_type: str) -> Dict:
        """Возвращает шаблон тренировки на день с упражнениями.
        focus_type: strength | hypertrophy | endurance | functional
        """
        mg = self.get_muscle_group_for_day(day, (user.goal or "maintain"))
        # Простые шаблоны под группы мышц
        templates: Dict[str, List[Dict]] = {
            "upper": [
                {"name": "Жим лёжа", "type": "compound", "max_percentage": 0.7, "technique": "Лопатки сведены", "video_url": "https://youtu.be/gRVjAtPip0Y"},
                {"name": "Тяга штанги в наклоне", "type": "compound", "max_percentage": 0.65, "technique": "Корпус стабилен", "video_url": "https://youtu.be/vT2GjY_Umpw"},
                {"name": "Жим гантелей сидя", "type": "accessory", "max_percentage": 0.5, "technique": "Контроль амплитуды", "video_url": "https://youtu.be/B-aVuyhvLHU"},
                {"name": "Планка", "type": "core", "max_percentage": 0.0, "technique": "Корпус прямой", "video_url": "https://youtu.be/pSHjTRCQxIw"},
            ],
            "lower": [
                {"name": "Приседания со штангой", "type": "compound", "max_percentage": 0.7, "technique": "Спина нейтральна", "video_url": "https://youtu.be/ultWZbUMPL8"},
                {"name": "Становая тяга", "type": "compound", "max_percentage": 0.75, "technique": "Гриф близко к голени", "video_url": "https://youtu.be/op9kVnSso6Q"},
                {"name": "Планка", "type": "core", "max_percentage": 0.0, "technique": "Корпус прямой", "video_url": "https://youtu.be/pSHjTRCQxIw"},
            ],
            "cardio": [
                {"name": "Берпи", "type": "cardio", "max_percentage": 0.0, "technique": "Ровный темп", "video_url": "https://youtu.be/dZgVxmf6jkA"},
            ],
            "rest": [],
        }
        key = "upper" if mg in ("chest", "back", "shoulders", "upper") else "lower" if mg in ("legs", "posterior_chain", "lower") else mg
        return {"exercises": templates.get(key, [])}

    def get_muscle_group_for_day(self, day: int, goal: str) -> str:
        """Схема Upper/Lower/Rest/Upper/Lower/Cardio/Rest."""
        mapping = {
            1: "upper",
            2: "lower",
            3: "rest",
            4: "upper",
            5: "lower",
            6: "cardio",
            7: "rest",
        }
        return mapping.get(day, "upper")

    def get_workout_type(self, day: int) -> str:
        tmap = {3: "rest", 6: "endurance"}
        return tmap.get(day, "hypertrophy")

    def generate_exercise_details(self, template: Dict, user_level: str, intensity: float) -> Dict:
        """Генерация конкретных параметров упражнения."""
        is_bodyweight = template.get("max_percentage", 0.0) <= 0.0 or template.get("type") in ("cardio", "core")
        sets = self.calculate_sets(user_level, intensity, template.get("type") or "accessory")
        reps = self.calculate_reps(template.get("type") or "accessory", user_level)
        est_weight = None if is_bodyweight else self.calculate_weight(user_level, template.get("max_percentage", 0.5), intensity, template.get("name") or "")
        rest_time = self.calculate_rest_time(template.get("type") or "accessory", intensity)
        rpe = self.calculate_rpe(intensity)
        volume = float((est_weight or 0.0) * (reps * sets))
        duration = self.estimate_duration(template.get("type") or "accessory", sets, reps, rest_time)
        return {
            "name": template["name"],
            "sets": sets,
            "reps": reps,
            "weight": None if est_weight is None else round(est_weight, 2),
            "rest_time": rest_time,
            "rpe": rpe,
            "technique_tips": template.get("technique", ""),
            "video_url": template.get("video_url", ""),
            "estimated_duration": duration,
            "volume": round(volume, 2),
        }

    def calculate_sets(self, user_level: str, intensity: float, ex_type: str) -> int:
        base = 3 if ex_type != "compound" else 4
        if user_level == "advanced":
            base += 1
        elif user_level == "intermediate":
            base += 0
        else:
            base = max(2, base - 1)
        if intensity > 1.05:
            base += 1
        return int(base)

    def calculate_reps(self, ex_type: str, user_level: str) -> int:
        if ex_type == "compound":
            return 5 if user_level == "advanced" else 6 if user_level == "intermediate" else 8
        if ex_type == "cardio":
            return 20
        if ex_type == "core":
            return 30
        return 10 if user_level != "beginner" else 12

    def calculate_weight(self, user_level: str, max_percentage: float, intensity: float, exercise_name: str) -> float:
        # Базовые оценки нагрузок, если 1ПМ неизвестен
        base_map = {
            "присед": 60.0,
            "станов": 70.0,
            "жим лёжа": 50.0,
            "тяга штанги": 40.0,
            "жим гантелей": 20.0,
        }
        ex_lower = exercise_name.lower()
        base = 30.0
        for k, v in base_map.items():
            if k in ex_lower:
                base = v
                break
        level_factor = 1.2 if user_level == "advanced" else 1.0 if user_level == "intermediate" else 0.8
        return base * max_percentage * level_factor * intensity

    def calculate_rest_time(self, ex_type: str, intensity: float) -> int:
        if ex_type == "compound":
            return 120 if intensity >= 1.0 else 90
        if ex_type in ("cardio", "core"):
            return 45
        return 60

    def calculate_rpe(self, intensity: float) -> int:
        if intensity >= 1.05:
            return 8
        if intensity <= 0.95:
            return 6
        return 7

    def estimate_duration(self, ex_type: str, sets: int, reps: int, rest_time: int) -> int:
        # Грубая оценка: 2 сек/повтор + отдых между подходами
        time_lifting = sets * reps * 2
        time_rest = max(0, sets - 1) * rest_time
        return int((time_lifting + time_rest) / 60)  # минуты