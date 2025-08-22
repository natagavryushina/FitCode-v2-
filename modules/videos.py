from __future__ import annotations

import os
from typing import List

from googleapiclient.discovery import build
from cachetools import TTLCache, cached

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from keyboards import build_video_categories


VIDEOS_CB_PREFIX = "menu:videos"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

_cache = TTLCache(maxsize=256, ttl=60 * 60)


@cached(_cache)
def _search_youtube(query: str) -> List[str]:
    if not YOUTUBE_API_KEY:
        return []
    yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    res = yt.search().list(q=query, part="snippet", type="video", maxResults=5, relevanceLanguage="ru").execute()
    items = res.get("items", [])
    links = [f"https://www.youtube.com/watch?v={it['id']['videoId']}" for it in items if 'id' in it and 'videoId' in it['id']]
    return links


async def videos_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Выбери категорию видео-тренировок:", reply_markup=build_video_categories())


async def videos_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.split(":", 1)[1]
    mapping = {
        "cardio": "кардио тренировка дома",
        "strength": "силовая тренировка",
        "yoga": "йога для начинающих",
        "back": "упражнения для спины",
        "legs": "тренировка ног дома",
    }
    q = mapping.get(cat, "фитнес тренировка")
    links = _search_youtube(q)
    if not links:
        await query.edit_message_text("Не удалось получить видео. Проверь API ключ.")
    else:
        await query.edit_message_text("\n".join(links))


def register_video_handlers(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(videos_menu_handler, pattern=f"^{VIDEOS_CB_PREFIX}$"))
    app.add_handler(CallbackQueryHandler(videos_category_handler, pattern=r"^videos:(.+)$"))