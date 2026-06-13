"""
webhook.py — запуск бота через webhook на FastAPI.
Используется для деплоя на Render (и любой другой платформе с HTTPS).

Локальная разработка: используйте run.py (polling).
Продакшн / Render: используйте этот файл.
"""

import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from dotenv import load_dotenv
from fastapi import FastAPI, Request

from bot.handlers import router
from db.database import init_db, AsyncSessionLocal
from db.crud import add_problem, get_stats
from db.seed_data import SEED_PROBLEMS

load_dotenv()

# ── Логирование ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Переменные окружения ──────────────────────────────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://math-olympiad-bot.onrender.com

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Добавьте его в Environment Variables на Render.")

if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL не задан. Добавьте его в Environment Variables на Render.")

# ── Бот и диспетчер ───────────────────────────────────────────────────────────

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)


# ── Загрузка seed-данных ──────────────────────────────────────────────────────

async def load_seed_data() -> None:
    """Загрузить тестовые задачи при первом старте (если база пуста)."""
    async with AsyncSessionLocal() as session:
        stats = await get_stats(session)
        if stats["total"] > 0:
            logger.info("База содержит %d задач, seed пропущен.", stats["total"])
            return

        logger.info("База пуста — загружаем тестовые задачи...")
        added = 0
        for problem_data in SEED_PROBLEMS:
            result = await add_problem(session, problem_data)
            if result:
                added += 1
        logger.info("Seed загружен: %d задач.", added)


# ── Lifespan: старт и остановка приложения ────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    При старте:  создать таблицы, загрузить seed, установить webhook.
    При остановке: удалить webhook, закрыть сессию бота.
    """
    logger.info("Старт приложения...")

    # Инициализация БД и seed
    await init_db()
    await load_seed_data()

    # Установить webhook
    webhook_path = f"{WEBHOOK_URL}/webhook"
    await bot.set_webhook(webhook_path)
    logger.info("Webhook установлен: %s", webhook_path)

    yield  # ← приложение работает здесь

    # Остановка
    logger.info("Остановка приложения...")
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Webhook удалён, сессия закрыта.")


# ── FastAPI приложение ────────────────────────────────────────────────────────

app = FastAPI(
    title="Math Olympiad Bot",
    description="Telegram-бот для олимпиадных задач по математике",
    lifespan=lifespan,
)


@app.get("/")
async def home():
    """
    Проверка работоспособности сервера.
    Render использует этот эндпоинт для health-check.
    """
    return {"status": "bot is running", "webhook": f"{WEBHOOK_URL}/webhook"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Принимает апдейты от Telegram и передаёт их в диспетчер aiogram.
    """
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error("Ошибка обработки апдейта: %s", e)
    return {"ok": True}
