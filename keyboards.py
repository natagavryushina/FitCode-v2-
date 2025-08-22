from telegram import InlineKeyboardButton, InlineKeyboardMarkup


MAIN_MENU_BUTTONS = [
    [
        InlineKeyboardButton("💪 Тренировки", callback_data="menu:training"),
        InlineKeyboardButton("🍏 Питание", callback_data="menu:nutrition"),
    ],
    [
        InlineKeyboardButton("🎯 Мои цели", callback_data="menu:goals"),
        InlineKeyboardButton("📊 Прогресс", callback_data="menu:progress"),
    ],
    [
        InlineKeyboardButton("🎥 Видео-тренировки", callback_data="menu:videos"),
        InlineKeyboardButton("🔍 Анализ", callback_data="menu:analysis"),
    ],
]


def build_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(MAIN_MENU_BUTTONS)


def build_video_categories() -> InlineKeyboardMarkup:
    categories = [
        ("Кардио", "videos:cardio"),
        ("Силовые", "videos:strength"),
        ("Йога", "videos:yoga"),
        ("Спина", "videos:back"),
        ("Ноги", "videos:legs"),
    ]
    rows = [[InlineKeyboardButton(text, callback_data=data)] for text, data in categories]
    return InlineKeyboardMarkup(rows)


def workout_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📅 Недельный план", callback_data='weekly_plan')],
        [InlineKeyboardButton("🏋️ Сегодняшняя тренировка", callback_data='today_workout')],
        [InlineKeyboardButton("✅ Отметить выполнение", callback_data='log_workout')],
        [InlineKeyboardButton("📊 Прогресс нагрузок", callback_data='workout_progress')],
        [InlineKeyboardButton("🔄 Обновить план", callback_data='refresh_plan')],
        [InlineKeyboardButton("↩️ Назад", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)