from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from decorators.clean_chat import clean_chat_decorator
from utils import chat_manager
from keyboards import main_menu_keyboard, workout_menu_keyboard as workouts_menu_keyboard, nutrition_menu_keyboard


@clean_chat_decorator
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик главного меню с очисткой"""
    text = "🏠 *Главное меню*\n\nВыберите раздел:"
    keyboard = main_menu_keyboard()
    await chat_manager.send_clean_message(update, context, text, keyboard)


@clean_chat_decorator
async def handle_workouts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик меню тренировок с очисткой"""
    text = "💪 *Меню тренировок*\n\nЧто вас интересует?"
    keyboard = workouts_menu_keyboard()
    await chat_manager.send_clean_message(update, context, text, keyboard)


@clean_chat_decorator
async def handle_nutrition_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик меню питания с очисткой"""
    text = "🍏 *Меню питания*\n\nВыберите опцию:"
    keyboard = nutrition_menu_keyboard()
    await chat_manager.send_clean_message(update, context, text, keyboard)