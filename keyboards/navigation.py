from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_back_button(target_menu: str = None) -> InlineKeyboardButton:
    """Универсальная кнопка назад"""
    return InlineKeyboardButton("↩️ Назад", callback_data=f"back_to:{target_menu}")


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("💪 Тренировки", callback_data='menu_workouts')],
        [InlineKeyboardButton("🍏 Питание", callback_data='menu_nutrition')],
        [InlineKeyboardButton("🎯 Мои цели", callback_data='menu_goals')],
        [InlineKeyboardButton("📊 Прогресс", callback_data='menu_progress')],
        [InlineKeyboardButton("🎥 Видео-тренировки", callback_data='menu_videos')],
        [InlineKeyboardButton("🔍 Анализ", callback_data='menu_analysis')]
    ]
    return InlineKeyboardMarkup(keyboard)


def workouts_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📅 Недельный план", callback_data='workouts_weekly')],
        [InlineKeyboardButton("🏋️ Сегодняшняя тренировка", callback_data='workouts_today')],
        [InlineKeyboardButton("✅ Отметить выполнение", callback_data='workouts_log')],
        [InlineKeyboardButton("📊 Прогресс нагрузок", callback_data='workouts_progress')],
        [InlineKeyboardButton("🔄 Обновить план", callback_data='workouts_refresh')],
        [get_back_button("main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def nutrition_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🍽 Дневной план", callback_data='nutrition_daily')],
        [InlineKeyboardButton("📋 Рецепты", callback_data='nutrition_recipes')],
        [InlineKeyboardButton("📊 КБЖУ", callback_data='nutrition_calories')],
        [InlineKeyboardButton("⚙️ Настройки диеты", callback_data='nutrition_settings')],
        [get_back_button("main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)