"""
Менеджер парсеров.

Запускает все зарегистрированные парсеры и сохраняет задачи в базу данных.

Чтобы добавить новый парсер:
1. Создайте файл в parsers/, наследуйтесь от BaseParser
2. Импортируйте класс ниже
3. Добавьте экземпляр в список REGISTERED_PARSERS
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from parsers.base import BaseParser
from parsers.simple_web_parser import SimpleWebParser
# from parsers.example_parser import ExampleParser  # раскомментируйте для использования
from db.crud import add_problem

logger = logging.getLogger(__name__)

# ── Зарегистрированные парсеры ────────────────────────────────────────────────
# Добавляйте сюда экземпляры своих парсеров.
# Пример: ExampleParser()
REGISTERED_PARSERS: list[BaseParser] = [
    # ExampleParser(),
]


async def run_all_parsers(session: AsyncSession) -> dict:
    """
    Запустить все зарегистрированные парсеры и сохранить задачи в БД.

    Returns:
        Словарь {"added": N, "skipped": N, "errors": N}
    """
    if not REGISTERED_PARSERS:
        logger.warning(
            "Нет зарегистрированных парсеров. "
            "Добавьте парсеры в parsers/manager.py → REGISTERED_PARSERS."
        )
        return {"added": 0, "skipped": 0, "errors": 0}

    total_added = 0
    total_skipped = 0
    total_errors = 0

    for parser in REGISTERED_PARSERS:
        logger.info("Запуск парсера: %s", parser.source_name)

        try:
            problems = await parser.fetch()
        except Exception as e:
            logger.error("Ошибка в парсере %s: %s", parser.source_name, e)
            total_errors += 1
            continue

        for problem_data in problems:
            try:
                result = await add_problem(session, problem_data.to_dict())
                if result:
                    total_added += 1
                else:
                    total_skipped += 1
            except Exception as e:
                logger.error("Ошибка сохранения задачи: %s", e)
                total_errors += 1

        logger.info(
            "Парсер %s завершён. Добавлено: %d, пропущено: %d",
            parser.source_name, total_added, total_skipped,
        )

    return {
        "added": total_added,
        "skipped": total_skipped,
        "errors": total_errors,
    }



async def run_parser_for_urls(session: AsyncSession, urls: list[str]) -> dict:
    """Запустить простой веб-парсер по конкретным URL и сохранить задачи в БД."""
    parser = SimpleWebParser(urls)
    if not parser.urls:
        return {"found": 0, "added": 0, "skipped": 0, "errors": 0}

    try:
        problems = await parser.fetch()
    except Exception as e:
        logger.error("Ошибка запуска веб-парсера: %s", e)
        return {"found": 0, "added": 0, "skipped": 0, "errors": 1}

    found = len(problems)
    added = 0
    skipped = 0
    errors = 0

    for problem_data in problems:
        try:
            result = await add_problem(session, problem_data.to_dict())
            if result:
                added += 1
            else:
                skipped += 1
        except Exception as e:
            logger.error("Ошибка сохранения задачи из веб-парсера: %s", e)
            errors += 1

    return {"found": found, "added": added, "skipped": skipped, "errors": errors}
