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