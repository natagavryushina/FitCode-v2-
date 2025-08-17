from __future__ import annotations

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from db.database import session_scope
from db import repo

logger = logging.getLogger(__name__)


def _collect_user_ids() -> list[int]:
	ids: list[int] = []
	with session_scope() as s:
		# naive: everyone in users table
		from db.models import User
		for row in s.query(User).all():
			ids.append(int(row.tg_user_id))
	return ids


async def send_daily_reminders(bot, hour: int) -> None:
	user_ids = _collect_user_ids()
	for uid in user_ids:
		try:
			await bot.send_message(chat_id=uid, text="Напоминание: загляни в тренировки и меню на сегодня ✨")
		except Exception as e:
			logger.warning("reminder failed for %s: %s", uid, e)


def setup_scheduler(scheduler: AsyncIOScheduler, bot, hour: int) -> None:
	trigger = CronTrigger(hour=hour, minute=0)
	scheduler.add_job(send_daily_reminders, trigger=trigger, args=[bot, hour], id="daily_reminders", replace_existing=True)