#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных с новыми таблицами
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import engine
from db.models import Base

def init_database():
    """Создать все таблицы в базе данных"""
    print("Создание таблиц в базе данных...")
    Base.metadata.create_all(bind=engine)
    print("✅ Все таблицы успешно созданы!")

if __name__ == "__main__":
    init_database()