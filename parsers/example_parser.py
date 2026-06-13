"""
Пример парсера-шаблона.

Скопируйте этот файл, переименуйте (например, mathplanet_parser.py)
и настройте под конкретный сайт.

ВАЖНО: Используйте парсер только для сайтов, которые явно разрешают
автоматический сбор данных (есть robots.txt без запретов, API,
или явное разрешение в Terms of Service).
"""

import asyncio
import logging
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from parsers.base import BaseParser, ProblemData
from services.classifier import classify_problem, estimate_difficulty

logger = logging.getLogger(__name__)


class ExampleParser(BaseParser):
    """
    Шаблон парсера. Замените URL и CSS-селекторы на реальные.

    Как использовать:
    1. Замените BASE_URL на адрес нужного сайта
    2. Найдите CSS-селекторы в браузере (F12 → Elements)
    3. Замените значения SELECTOR_* ниже
    4. Зарегистрируйте класс в parsers/manager.py
    """

    source_name = "Example Math Site"
    base_url = "https://example-math-site.com"  # ← ЗАМЕНИТЕ

    # ── CSS-селекторы ── замените на реальные ──────────────────────────────
    # Ссылки на страницы с задачами на главной/списке
    SELECTOR_PROBLEM_LINKS = "a.problem-link"       # ← ЗАМЕНИТЕ

    # На странице задачи:
    SELECTOR_TITLE = "h1.problem-title"             # ← ЗАМЕНИТЕ
    SELECTOR_TEXT = "div.problem-text"              # ← ЗАМЕНИТЕ
    SELECTOR_ANSWER = "div.problem-answer"          # ← ЗАМЕНИТЕ (может отсутствовать)
    SELECTOR_SOLUTION = "div.problem-solution"      # ← ЗАМЕНИТЕ (может отсутствовать)

    # Страницы со списком задач (пагинация)
    LIST_URLS: list[str] = [
        # "https://example-math-site.com/problems/page/1",  # ← ЗАМЕНИТЕ
        # "https://example-math-site.com/problems/page/2",
    ]

    # Диапазон классов по умолчанию (если на сайте не указано)
    DEFAULT_GRADE_MIN: Optional[int] = None
    DEFAULT_GRADE_MAX: Optional[int] = None

    request_delay = 1.5  # секунды между запросами

    # ──────────────────────────────────────────────────────────────────────

    async def fetch(self) -> list[ProblemData]:
        """Собрать задачи со всех страниц LIST_URLS."""
        if not self.LIST_URLS:
            self.log(
                "LIST_URLS пуст. Добавьте URL страниц с задачами.", "warning"
            )
            return []

        problems: list[ProblemData] = []

        async with aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0 (educational bot)"}
        ) as session:
            for list_url in self.LIST_URLS:
                links = await self._get_problem_links(session, list_url)
                self.log(f"Найдено {len(links)} ссылок на странице {list_url}")

                for link in links:
                    problem = await self._parse_problem_page(session, link)
                    if problem:
                        problems.append(problem)
                    await asyncio.sleep(self.request_delay)

        self.log(f"Итого собрано задач: {len(problems)}")
        return problems

    async def _get_problem_links(
        self, session: aiohttp.ClientSession, url: str
    ) -> list[str]:
        """Получить список ссылок на задачи со страницы-списка."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    self.log(f"HTTP {resp.status} для {url}", "warning")
                    return []
                html = await resp.text()
        except Exception as e:
            self.log(f"Ошибка запроса {url}: {e}", "error")
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = []

        for tag in soup.select(self.SELECTOR_PROBLEM_LINKS):
            href = tag.get("href", "")
            if href:
                # Если ссылка относительная, добавляем базовый URL
                if href.startswith("/"):
                    href = self.base_url + href
                links.append(href)

        return links

    async def _parse_problem_page(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[ProblemData]:
        """Распарсить страницу с одной задачей."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    self.log(f"HTTP {resp.status} для {url}", "warning")
                    return None
                html = await resp.text()
        except Exception as e:
            self.log(f"Ошибка запроса {url}: {e}", "error")
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Извлечь заголовок
        title_tag = soup.select_one(self.SELECTOR_TITLE)
        title = title_tag.get_text(strip=True) if title_tag else None

        # Извлечь текст задачи
        text_tag = soup.select_one(self.SELECTOR_TEXT)
        if not text_tag:
            self.log(f"Текст задачи не найден на {url}", "warning")
            return None
        text = text_tag.get_text(separator="\n", strip=True)

        # Извлечь ответ (опционально)
        answer_tag = soup.select_one(self.SELECTOR_ANSWER)
        answer = answer_tag.get_text(strip=True) if answer_tag else None

        # Извлечь решение (опционально)
        solution_tag = soup.select_one(self.SELECTOR_SOLUTION)
        solution = solution_tag.get_text(separator="\n", strip=True) if solution_tag else None

        # Автоматически классифицировать тему и сложность
        full_text = f"{title or ''} {text}"
        topic = classify_problem(full_text)
        difficulty = estimate_difficulty(full_text)

        return ProblemData(
            title=title,
            text=text,
            answer=answer,
            solution=solution,
            topic=topic,
            grade_min=self.DEFAULT_GRADE_MIN,
            grade_max=self.DEFAULT_GRADE_MAX,
            difficulty=difficulty,
            source_name=self.source_name,
            source_url=url,
        )
