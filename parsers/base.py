"""
Базовый класс для всех парсеров задач.

Каждый парсер должен наследоваться от BaseParser и реализовать метод fetch().
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ProblemData:
    """
    Данные одной задачи, возвращаемые парсером.
    Все парсеры должны возвращать список объектов этого класса.
    """
    text: str
    title: Optional[str] = None
    answer: Optional[str] = None
    solution: Optional[str] = None
    topic: str = "разное"
    grade_min: Optional[int] = None
    grade_max: Optional[int] = None
    difficulty: Optional[float] = None
    source_name: str = "Неизвестный источник"
    source_url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "text": self.text,
            "answer": self.answer,
            "solution": self.solution,
            "topic": self.topic,
            "grade_min": self.grade_min,
            "grade_max": self.grade_max,
            "difficulty": self.difficulty,
            "source_name": self.source_name,
            "source_url": self.source_url,
        }


class BaseParser(ABC):
    """
    Абстрактный базовый класс парсера.

    Чтобы добавить новый сайт:
    1. Создайте файл в папке parsers/, например my_site_parser.py
    2. Унаследуйтесь от BaseParser
    3. Реализуйте метод fetch()
    4. Зарегистрируйте парсер в parsers/manager.py
    """

    # Имя источника (отображается пользователям)
    source_name: str = "Unnamed Source"

    # Базовый URL сайта
    base_url: str = ""

    # Задержка между запросами (секунды) — уважайте сервер!
    request_delay: float = 1.0

    @abstractmethod
    async def fetch(self) -> list[ProblemData]:
        """
        Собрать задачи с сайта.

        Returns:
            Список объектов ProblemData.
        """
        ...

    def log(self, message: str, level: str = "info") -> None:
        """Удобный метод логирования с именем парсера."""
        getattr(logger, level)("[%s] %s", self.source_name, message)
