from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.config import settings

engine = create_engine(
	settings.database_url,
	future=True,
	echo=False,
	pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Iterator:
	session = SessionLocal()
	try:
		yield session
		session.commit()
	except Exception:
		session.rollback()
		raise
	finally:
		session.close()