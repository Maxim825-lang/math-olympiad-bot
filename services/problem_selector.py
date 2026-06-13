"""
Сервис выбора задач.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from db import crud
from db.models import Problem

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


async def select_problem(
    session: AsyncSession,
    topic: Optional[str] = None,
    grade: Optional[int] = None,
    telegram_id: Optional[int] = None,
    difficulty: Optional[str] = None,
) -> Optional[Problem]:
    problem = await crud.get_random_problem(
        session, topic=topic, grade=grade,
        telegram_id=telegram_id, difficulty=difficulty,
    )
    if not problem and grade:
        problem = await crud.get_random_problem(
            session, topic=topic, telegram_id=telegram_id, difficulty=difficulty
        )
    return problem


async def select_daily(
    session: AsyncSession,
    grade: Optional[int] = None,
    count: int = 5,
    telegram_id: Optional[int] = None,
) -> list[Problem]:
    problems = await crud.get_daily_problems(
        session, grade=grade, count=count, telegram_id=telegram_id
    )
    if not problems:
        problems = await crud.get_daily_problems(session, grade=None, count=count)
    return problems


def _header(problem: Problem, index: Optional[int] = None) -> list[str]:
    lines: list[str] = []
    prefix = f"Задача {index}." if index else "Задача."
    if problem.title:
        lines.append(f"<b>{prefix} {problem.title}</b>")
    else:
        lines.append(f"<b>{prefix}</b>")

    lines.append(f"📚 <b>Тема:</b> {problem.topic}")

    if problem.difficulty:
        diff_str = str(problem.difficulty)
        lines.append(f"⭐ <b>Сложность:</b> {diff_str}")

    pts = problem.points
    if pts:
        lines.append(f"🎯 <b>За решение:</b> {pts} очков")

    if problem.grade_min and problem.grade_max:
        lines.append(f"🎓 <b>Классы:</b> {problem.grade_min}–{problem.grade_max}")
    elif problem.grade_min:
        lines.append(f"🎓 <b>Класс:</b> {problem.grade_min}+")

    return lines


def format_problem_question(problem: Problem, index: Optional[int] = None) -> str:
    lines = _header(problem, index)
    lines.append("")
    lines.append(problem.text)
    lines.append("")
    lines.append("✏️ <i>Напиши свой ответ в чат.</i>")
    if problem.source_name:
        lines.append("")
        lines.append(f"📎 <i>Источник: {problem.source_name}</i>")
    return "\n".join(lines)


def format_problem_solution(problem: Problem) -> str:
    lines: list[str] = []
    if problem.answer:
        lines.append(f"💡 <b>Правильный ответ:</b> {problem.answer}")
    if problem.solution:
        lines.append("")
        lines.append(f"📝 <b>Решение:</b>\n{problem.solution}")
    return "\n".join(lines) if lines else ""


def format_problem(problem: Problem, index: Optional[int] = None) -> str:
    return format_problem_question(problem, index)
