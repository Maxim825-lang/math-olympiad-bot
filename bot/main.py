"""
Инициализация и запуск Telegram-бота.
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from db.database import init_db, AsyncSessionLocal
from db.crud import add_problem, get_stats
from db.seed_data import SEED_PROBLEMS
from bot.handlers import router

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def load_seed_data() -> None:
    """Загрузить тестовые задачи при первом запуске."""
    async with AsyncSessionLocal() as session:
        stats = await get_stats(session)
        if stats["total"] > 0:
            logger.info("База уже содержит %d задач, seed пропущен.", stats["total"])
            return

        logger.info("База пуста. Загружаем тестовые задачи...")
        added = 0
        for problem_data in SEED_PROBLEMS:
            result = await add_problem(session, problem_data)
            if result:
                added += 1

        logger.info("Загружено %d тестовых задач.", added)


async def main() -> None:
    """Главная функция запуска бота."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.critical("BOT_TOKEN не задан в .env файле!")
        raise SystemExit(1)

    # Инициализировать базу данных
    await init_db()

    # Загрузить тестовые данные
    await load_seed_data()

    # Создать бот и диспетчер
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Бот запускается...")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await bot.session.close()
        logger.info("Бот остановлен.")
