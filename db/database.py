"""
Подключение к базе данных и управление сессиями.
"""

import logging
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from dotenv import load_dotenv

from db.models import Base

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///problems.db")

# Создаём асинхронный движок
engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # Поставьте True для отладки SQL-запросов
    future=True,
)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Создать все таблицы, если они ещё не существуют."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("База данных инициализирована.")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор сессии для dependency injection."""
    async with AsyncSessionLocal() as session:
        yield session
