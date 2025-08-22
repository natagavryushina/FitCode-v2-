#!/usr/bin/env python3
"""
Скрипт для добавления тестовых готовых тренировочных программ в базу данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from db.database import SessionLocal
from db.models import TrainingProgram, ProgramWorkout

def add_sample_programs():
    """Добавить тестовые программы в базу данных"""
    
    session = SessionLocal()
    
    # Программа 1: Начальная силовая программа
    program1 = TrainingProgram(
        name="Начальная силовая программа",
        description="Идеальная программа для новичков, желающих освоить основы силовых тренировок. Включает базовые упражнения с постепенным увеличением нагрузки.",
        goal="strength",
        level="beginner",
        duration_weeks=8,
        days_per_week=3,
        equipment="dumbbells,bench",
        is_active=True
    )
    
    session.add(program1)
    session.flush()
    
    # Тренировки для программы 1
    strength_workouts = [
        # Неделя 1
        {
            'week': 1, 'day': 1, 'type': 'Верх тела', 'muscles': 'Грудь, плечи, трицепс',
            'duration': 45, 'exercises': [
                {'name': 'Жим гантелей лежа', 'sets': 3, 'reps': '8-10', 'rest': 90, 'notes': 'Контролируйте движение'},
                {'name': 'Жим гантелей стоя', 'sets': 3, 'reps': '8-10', 'rest': 90},
                {'name': 'Отжимания', 'sets': 2, 'reps': '8-12', 'rest': 60},
                {'name': 'Планка', 'sets': 2, 'reps': '30 сек', 'rest': 60}
            ]
        },
        {
            'week': 1, 'day': 2, 'type': 'Низ тела', 'muscles': 'Ноги, ягодицы',
            'duration': 45, 'exercises': [
                {'name': 'Приседания с гантелями', 'sets': 3, 'reps': '10-12', 'rest': 90},
                {'name': 'Выпады с гантелями', 'sets': 3, 'reps': '8-10 на ногу', 'rest': 90},
                {'name': 'Румынская тяга', 'sets': 3, 'reps': '10-12', 'rest': 90},
                {'name': 'Подъемы на носки', 'sets': 2, 'reps': '15-20', 'rest': 60}
            ]
        },
        {
            'week': 1, 'day': 3, 'type': 'Спина и руки', 'muscles': 'Спина, бицепс',
            'duration': 45, 'exercises': [
                {'name': 'Тяга гантели в наклоне', 'sets': 3, 'reps': '8-10', 'rest': 90},
                {'name': 'Подъемы на бицепс', 'sets': 3, 'reps': '10-12', 'rest': 60},
                {'name': 'Обратные отжимания', 'sets': 2, 'reps': '8-10', 'rest': 60},
                {'name': 'Супермен', 'sets': 2, 'reps': '12-15', 'rest': 60}
            ]
        }
    ]
    
    # Добавляем тренировки для всех 8 недель
    for week in range(1, 9):
        for workout_template in strength_workouts:
            workout = ProgramWorkout(
                program_id=program1.id,
                week_number=week,
                day_number=workout_template['day'],
                workout_type=workout_template['type'],
                muscle_groups=workout_template['muscles'],
                duration_minutes=workout_template['duration'],
                exercises=workout_template['exercises']
            )
            session.add(workout)
    
    # Программа 2: Кардио для похудения
    program2 = TrainingProgram(
        name="Кардио-интенсив для похудения",
        description="Эффективная программа для сжигания жира и улучшения выносливости. Сочетает различные виды кардио с силовыми элементами.",
        goal="fat_loss",
        level="intermediate",
        duration_weeks=6,
        days_per_week=4,
        equipment="bodyweight_only,cardio_machine",
        is_active=True
    )
    
    session.add(program2)
    session.flush()
    
    # Тренировки для программы 2
    cardio_workouts = [
        {
            'week': 1, 'day': 1, 'type': 'HIIT', 'muscles': 'Все тело',
            'duration': 30, 'exercises': [
                {'name': 'Берпи', 'sets': 4, 'reps': '30 сек', 'rest': 30},
                {'name': 'Прыжки на месте', 'sets': 4, 'reps': '30 сек', 'rest': 30},
                {'name': 'Горные альпинисты', 'sets': 4, 'reps': '30 сек', 'rest': 30},
                {'name': 'Планка', 'sets': 3, 'reps': '45 сек', 'rest': 60}
            ]
        },
        {
            'week': 1, 'day': 2, 'type': 'Кардио низкой интенсивности', 'muscles': 'Сердечно-сосудистая система',
            'duration': 40, 'exercises': [
                {'name': 'Быстрая ходьба', 'sets': 1, 'reps': '40 мин', 'notes': 'Поддерживайте комфортный темп'}
            ]
        },
        {
            'week': 1, 'day': 3, 'type': 'Силовое кардио', 'muscles': 'Все тело',
            'duration': 35, 'exercises': [
                {'name': 'Приседания с прыжком', 'sets': 3, 'reps': '12-15', 'rest': 45},
                {'name': 'Отжимания', 'sets': 3, 'reps': '8-12', 'rest': 45},
                {'name': 'Выпады в прыжке', 'sets': 3, 'reps': '10 на ногу', 'rest': 45},
                {'name': 'Скручивания', 'sets': 3, 'reps': '15-20', 'rest': 30}
            ]
        },
        {
            'week': 1, 'day': 4, 'type': 'Активное восстановление', 'muscles': 'Растяжка',
            'duration': 25, 'exercises': [
                {'name': 'Легкая йога', 'sets': 1, 'reps': '20 мин', 'notes': 'Фокус на растяжке'},
                {'name': 'Дыхательные упражнения', 'sets': 1, 'reps': '5 мин'}
            ]
        }
    ]
    
    # Добавляем тренировки для всех 6 недель
    for week in range(1, 7):
        for workout_template in cardio_workouts:
            workout = ProgramWorkout(
                program_id=program2.id,
                week_number=week,
                day_number=workout_template['day'],
                workout_type=workout_template['type'],
                muscle_groups=workout_template['muscles'],
                duration_minutes=workout_template['duration'],
                exercises=workout_template['exercises']
            )
            session.add(workout)
    
    # Программа 3: Набор мышечной массы
    program3 = TrainingProgram(
        name="Массонаборный сплит",
        description="Классическая программа для набора мышечной массы. Проработка всех групп мышц с акцентом на прогрессию весов.",
        goal="muscle_gain",
        level="intermediate",
        duration_weeks=12,
        days_per_week=4,
        equipment="dumbbells,barbell,bench",
        is_active=True
    )
    
    session.add(program3)
    session.flush()
    
    # Тренировки для программы 3
    mass_workouts = [
        {
            'week': 1, 'day': 1, 'type': 'Грудь и трицепс', 'muscles': 'Грудь, трицепс',
            'duration': 60, 'exercises': [
                {'name': 'Жим штанги лежа', 'sets': 4, 'reps': '6-8', 'rest': 120},
                {'name': 'Жим гантелей на наклонной', 'sets': 3, 'reps': '8-10', 'rest': 90},
                {'name': 'Разводка гантелей', 'sets': 3, 'reps': '10-12', 'rest': 90},
                {'name': 'Жим узким хватом', 'sets': 3, 'reps': '8-10', 'rest': 90},
                {'name': 'Французский жим', 'sets': 3, 'reps': '10-12', 'rest': 90}
            ]
        },
        {
            'week': 1, 'day': 2, 'type': 'Спина и бицепс', 'muscles': 'Спина, бицепс',
            'duration': 60, 'exercises': [
                {'name': 'Становая тяга', 'sets': 4, 'reps': '5-6', 'rest': 120},
                {'name': 'Тяга штанги в наклоне', 'sets': 3, 'reps': '8-10', 'rest': 90},
                {'name': 'Тяга гантели одной рукой', 'sets': 3, 'reps': '8-10', 'rest': 90},
                {'name': 'Подъемы на бицепс со штангой', 'sets': 3, 'reps': '8-10', 'rest': 90},
                {'name': 'Молотки с гантелями', 'sets': 3, 'reps': '10-12', 'rest': 90}
            ]
        },
        {
            'week': 1, 'day': 3, 'type': 'Ноги', 'muscles': 'Ноги, ягодицы',
            'duration': 60, 'exercises': [
                {'name': 'Приседания со штангой', 'sets': 4, 'reps': '6-8', 'rest': 120},
                {'name': 'Румынская тяга', 'sets': 3, 'reps': '8-10', 'rest': 90},
                {'name': 'Выпады с гантелями', 'sets': 3, 'reps': '10-12 на ногу', 'rest': 90},
                {'name': 'Подъемы на носки', 'sets': 4, 'reps': '12-15', 'rest': 60}
            ]
        },
        {
            'week': 1, 'day': 4, 'type': 'Плечи и пресс', 'muscles': 'Плечи, пресс',
            'duration': 50, 'exercises': [
                {'name': 'Жим гантелей стоя', 'sets': 4, 'reps': '8-10', 'rest': 90},
                {'name': 'Разводка в стороны', 'sets': 3, 'reps': '10-12', 'rest': 90},
                {'name': 'Обратная разводка', 'sets': 3, 'reps': '12-15', 'rest': 90},
                {'name': 'Скручивания', 'sets': 3, 'reps': '15-20', 'rest': 60},
                {'name': 'Велосипед', 'sets': 3, 'reps': '20 на сторону', 'rest': 60}
            ]
        }
    ]
    
    # Добавляем тренировки для всех 12 недель
    for week in range(1, 13):
        for workout_template in mass_workouts:
            workout = ProgramWorkout(
                program_id=program3.id,
                week_number=week,
                day_number=workout_template['day'],
                workout_type=workout_template['type'],
                muscle_groups=workout_template['muscles'],
                duration_minutes=workout_template['duration'],
                exercises=workout_template['exercises']
            )
            session.add(workout)
    
    # Программа 4: Функциональный тренинг
    program4 = TrainingProgram(
        name="Функциональный тренинг",
        description="Тренировки для развития функциональной силы, координации и мобильности. Подходит для повседневной активности.",
        goal="endurance",
        level="beginner",
        duration_weeks=6,
        days_per_week=3,
        equipment="bodyweight_only,kettlebell",
        is_active=True
    )
    
    session.add(program4)
    session.flush()
    
    # Тренировки для программы 4
    functional_workouts = [
        {
            'week': 1, 'day': 1, 'type': 'Функциональная сила', 'muscles': 'Все тело',
            'duration': 40, 'exercises': [
                {'name': 'Турецкий подъем', 'sets': 3, 'reps': '3 на сторону', 'rest': 90},
                {'name': 'Качели с гирей', 'sets': 4, 'reps': '15-20', 'rest': 90},
                {'name': 'Медвежья походка', 'sets': 3, 'reps': '20 шагов', 'rest': 60},
                {'name': 'Планка с подъемом ног', 'sets': 3, 'reps': '10 на ногу', 'rest': 60}
            ]
        },
        {
            'week': 1, 'day': 2, 'type': 'Мобильность и стабилизация', 'muscles': 'Кор, стабилизаторы',
            'duration': 35, 'exercises': [
                {'name': 'Приседания на одной ноге', 'sets': 3, 'reps': '5-8 на ногу', 'rest': 90},
                {'name': 'Отжимания на одной руке (с колен)', 'sets': 3, 'reps': '3-5 на руку', 'rest': 90},
                {'name': 'Боковая планка', 'sets': 2, 'reps': '30 сек на сторону', 'rest': 60},
                {'name': 'Глубокие выпады', 'sets': 3, 'reps': '8-10 на ногу', 'rest': 60}
            ]
        },
        {
            'week': 1, 'day': 3, 'type': 'Кондиционная тренировка', 'muscles': 'Сердечно-сосудистая система',
            'duration': 30, 'exercises': [
                {'name': 'Круговая тренировка', 'sets': 3, 'reps': '5 мин', 'rest': 120, 'notes': '1 мин работа, 20 сек отдых'},
                {'name': 'Заминка и растяжка', 'sets': 1, 'reps': '10 мин', 'notes': 'Фокус на восстановлении'}
            ]
        }
    ]
    
    # Добавляем тренировки для всех 6 недель
    for week in range(1, 7):
        for workout_template in functional_workouts:
            workout = ProgramWorkout(
                program_id=program4.id,
                week_number=week,
                day_number=workout_template['day'],
                workout_type=workout_template['type'],
                muscle_groups=workout_template['muscles'],
                duration_minutes=workout_template['duration'],
                exercises=workout_template['exercises']
            )
            session.add(workout)
    
    session.commit()
    session.close()
    
    print("✅ Тестовые программы успешно добавлены в базу данных!")
    print(f"Добавлено {4} программы:")
    print("1. Начальная силовая программа (8 недель)")
    print("2. Кардио-интенсив для похудения (6 недель)")
    print("3. Массонаборный сплит (12 недель)")
    print("4. Функциональный тренинг (6 недель)")

if __name__ == "__main__":
    add_sample_programs()