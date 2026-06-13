"""
Простой веб-парсер олимпиадных задач с публичных HTML-страниц.

Не обходит авторизацию, капчи и защиты. Подходит для страниц, где задачи
уже есть в HTML-тексте.
"""

import asyncio
import logging
import re
from typing import Iterable
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from parsers.base import BaseParser, ProblemData
from services.classifier import classify_problem, estimate_difficulty

logger = logging.getLogger(__name__)

MIN_PROBLEM_LEN = 45
MAX_PROBLEM_LEN = 5000


class SimpleWebParser(BaseParser):
    """Парсер задач по списку публичных URL."""

    source_name = "Web Parser"
    request_delay = 1.5

    def __init__(self, urls: Iterable[str]):
        self.urls = [u.strip() for u in urls if u and u.strip().startswith(("http://", "https://"))]

    async def fetch(self) -> list[ProblemData]:
        problems: list[ProblemData] = []
        timeout = aiohttp.ClientTimeout(total=25)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; MathOlympiadBotParser/1.0; "
                "+https://github.com/Maxim825-lang/math-olympiad-bot)"
            )
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for url in self.urls:
                try:
                    html = await self._download(session, url)
                    page_problems = self._extract_from_html(html, url)
                    problems.extend(page_problems)
                    self.log(f"{url}: найдено {len(page_problems)} возможных задач")
                except Exception as exc:
                    logger.exception("Не удалось распарсить %s: %s", url, exc)
                await asyncio.sleep(self.request_delay)

        return problems

    async def _download(self, session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.text(errors="ignore")

    def _extract_from_html(self, html: str, url: str) -> list[ProblemData]:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
            tag.decompose()

        candidates: list[str] = []

        # 1) Пробуем найти смысловые блоки.
        selectors = [
            "article", ".problem", ".task", ".exercise", ".content", ".entry-content",
            "li", "p", "div",
        ]
        seen = set()
        for selector in selectors:
            for node in soup.select(selector):
                text = self._clean_text(node.get_text(" ", strip=True))
                if self._looks_like_problem(text) and text not in seen:
                    candidates.append(text)
                    seen.add(text)

        # 2) Если блоки не помогли — режем весь текст страницы.
        if len(candidates) < 2:
            page_text = self._clean_text(soup.get_text("\n", strip=True))
            for part in self._split_page_text(page_text):
                if self._looks_like_problem(part) and part not in seen:
                    candidates.append(part)
                    seen.add(part)

        # Ограничиваем, чтобы случайно не забить базу мусором с одной страницы.
        candidates = candidates[:50]

        result: list[ProblemData] = []
        for i, text in enumerate(candidates, start=1):
            answer, solution, clean_problem = self._extract_answer_solution(text)
            clean_problem = self._clean_text(clean_problem)
            if not self._looks_like_problem(clean_problem):
                continue

            numeric_diff = estimate_difficulty(clean_problem)
            difficulty = self._difficulty_label(numeric_diff)
            topic = classify_problem(clean_problem)
            title = self._make_title(clean_problem, i)

            result.append(
                ProblemData(
                    title=title,
                    text=clean_problem,
                    answer=answer,
                    solution=solution,
                    topic=topic,
                    difficulty=difficulty,
                    source_name=self._source_name_for_url(url),
                    source_url=f"{url}#problem-{i}",
                )
            )

        return result

    def _split_page_text(self, text: str) -> list[str]:
        markers = re.compile(r"(?=(?:^|\n|\s)(?:Задача\s*\d*|№\s*\d+|Problem\s*\d*|Task\s*\d*)[\.:\)\s])", re.IGNORECASE)
        parts = [p.strip() for p in markers.split(text) if p and p.strip()]
        if len(parts) <= 1:
            # Запасной вариант: делим по длинным пустым строкам.
            parts = re.split(r"\n{2,}", text)
        return [self._clean_text(p) for p in parts if p and len(p.strip()) >= MIN_PROBLEM_LEN]

    def _extract_answer_solution(self, text: str) -> tuple[str | None, str | None, str]:
        answer = None
        solution = None
        clean = text

        ans_match = re.search(r"(?:Ответ|Answer)\s*[:\-–—]\s*(.+?)(?=(?:Решение|Solution)\s*[:\-–—]|$)", text, re.IGNORECASE | re.DOTALL)
        if ans_match:
            answer = self._clean_text(ans_match.group(1))[:1000] or None
            clean = text[:ans_match.start()].strip()

        sol_match = re.search(r"(?:Решение|Solution)\s*[:\-–—]\s*(.+)$", text, re.IGNORECASE | re.DOTALL)
        if sol_match:
            solution = self._clean_text(sol_match.group(1))[:3000] or None
            if not ans_match:
                clean = text[:sol_match.start()].strip()

        return answer, solution, clean

    def _looks_like_problem(self, text: str) -> bool:
        if not text:
            return False
        if len(text) < MIN_PROBLEM_LEN or len(text) > MAX_PROBLEM_LEN:
            return False
        lower = text.lower()
        keywords = [
            "найдите", "докажите", "доказать", "сколько", "задача", "решите",
            "вычислите", "чему равно", "существует ли", "можно ли", "problem", "find", "prove",
        ]
        return any(k in lower for k in keywords)

    def _difficulty_label(self, value: float) -> str:
        if value <= 2:
            return "лёгкая"
        if value <= 3.5:
            return "средняя"
        return "сложная"

    def _make_title(self, text: str, index: int) -> str:
        first = text.split(".", 1)[0].strip()
        if 8 <= len(first) <= 90:
            return first
        return f"Задача из веб-парсера #{index}"

    def _source_name_for_url(self, url: str) -> str:
        host = urlparse(url).netloc or "Web Parser"
        return f"Web Parser: {host}"

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\r", "\n", text)
        text = re.sub(r"[ \t\xa0]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()
