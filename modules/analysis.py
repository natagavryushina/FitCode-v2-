from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from database import get_or_create_user, get_sessionmaker, ProgressEntry
from ai_agents import query_memory, generate_analysis


ANALYSIS_CB_PREFIX = "menu:analysis"


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    mem = query_memory(user.telegram_id, "цели предпочтения прогресс", n=8)
    # collect recent weights
    Session = get_sessionmaker()
    weights = []
    async with Session() as session:
        from sqlalchemy import select
        res = await session.execute(
            select(ProgressEntry).where(ProgressEntry.user_id == user.id).order_by(ProgressEntry.entry_date.asc())
        )
        entries = res.scalars().all()
        for e in entries[-10:]:
            if e.weight_kg is not None:
                weights.append(float(e.weight_kg))
    text = generate_analysis(user, mem, recent_weights=weights)
    await update.message.reply_text(text)


async def analysis_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Запусти анализ с помощью /analyze")


def register_analysis_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CallbackQueryHandler(analysis_menu_handler, pattern=f"^{ANALYSIS_CB_PREFIX}$"))