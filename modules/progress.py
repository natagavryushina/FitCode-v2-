from __future__ import annotations

import io
import os
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from database import get_sessionmaker, ProgressEntry, get_or_create_user


PROGRESS_CB_PREFIX = "menu:progress"
PHOTOS_DIR = os.path.join(os.getcwd(), "data", "photos")


async def add_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = (update.message.text or "").split()
    weight = None
    if len(args) >= 2:
        try:
            weight = float(args[1])
        except Exception:
            pass
    user = await get_or_create_user(update.effective_user.id)
    Session = get_sessionmaker()
    async with Session() as session:
        entry = ProgressEntry(user_id=user.id, entry_date=date.today(), weight_kg=weight)
        session.add(entry)
        await session.commit()
    await update.message.reply_text("Записал прогресс. Используй /progress_plot для графика.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    path = os.path.join(PHOTOS_DIR, f"{update.effective_user.id}_{date.today().isoformat()}.jpg")
    await file.download_to_drive(path)
    user = await get_or_create_user(update.effective_user.id)
    Session = get_sessionmaker()
    async with Session() as session:
        entry = ProgressEntry(user_id=user.id, entry_date=date.today(), photo_path=path)
        session.add(entry)
        await session.commit()
    await update.message.reply_text("Фото сохранено к сегодняшней записи.")


async def progress_plot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    Session = get_sessionmaker()
    weights = []
    dates = []
    async with Session() as session:
        from sqlalchemy import select
        res = await session.execute(select(ProgressEntry).where(ProgressEntry.user_id == user.id).order_by(ProgressEntry.entry_date.asc()))
        entries = res.scalars().all()
        for e in entries:
            if e.weight_kg is not None:
                dates.append(e.entry_date)
                weights.append(float(e.weight_kg))
    if not weights:
        await update.message.reply_text("Пока нет данных для графика.")
        return
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(dates, weights, marker="o")
    ax.set_title("Динамика веса")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Вес, кг")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    await update.message.reply_photo(photo=InputFile(buf, filename="progress.png"))


async def progress_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Раздел прогресс: /add_progress <вес>, пришли фото, /progress_plot для графика.")


def register_progress_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("add_progress", add_progress))
    app.add_handler(CommandHandler("progress_plot", progress_plot))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(progress_menu_handler, pattern=f"^{PROGRESS_CB_PREFIX}$"))