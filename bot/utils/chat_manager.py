from __future__ import annotations

from typing import Dict, List
from telegram import Update
from telegram.ext import ContextTypes


def _get_ephemeral_store(context: ContextTypes.DEFAULT_TYPE) -> Dict[int, List[int]]:
	store = context.chat_data.get("ephemeral_ids")
	if store is None:
		store = {}
		context.chat_data["ephemeral_ids"] = store
	return store


async def cleanup_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	chat_id = update.effective_chat.id if update.effective_chat else None
	if chat_id is None:
		return
	store = _get_ephemeral_store(context)
	msg_ids = store.get(chat_id) or []
	if not msg_ids:
		return
	for mid in msg_ids:
		try:
			await context.bot.delete_message(chat_id=chat_id, message_id=mid)
		except Exception:
			pass
	store[chat_id] = []


async def track_message(context: ContextTypes.DEFAULT_TYPE, message_id: int) -> None:
	# Requires that cleanup_previous_messages was called before sending
	chat = getattr(context, "_chat", None)
	chat_id = getattr(chat, "id", None)
	# Fallback: context.user_data may carry last chat_id for the update
	if chat_id is None:
		chat_id = context.chat_data.get("last_chat_id")
	if chat_id is None:
		return
	store = _get_ephemeral_store(context)
	store.setdefault(chat_id, []).append(message_id)