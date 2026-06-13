"""
CRUD-операции с базой данных.
"""

import logging
from typing import Optional
from datetime import datetime

from sqlalchemy import func, select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Problem, User, ActiveAttempt, UserProblemHistory

logger = logging.getLogger(__name__)

MAX_SOLVE_REPEATS = 2  # задача не показывается если решена >= этого числа раз

# ── Утилиты ───────────────────────────────────────────────────────────────────

DIFFICULTY_POINTS = {"лёгкая": 5, "средняя": 10, "сложная": 20}
DIFFICULTY_ALIASES = {
    "лёгкая": "лёгкая", "легкая": "лёгкая", "easy": "лёгкая", "1": "лёгкая",
    "средняя": "средняя", "medium": "средняя", "2": "средняя", "3": "средняя",
    "сложная": "сложная", "hard": "сложная", "4": "сложная", "5": "сложная",
}

def normalize_difficulty(raw) -> Optional[str]:
    """Привести любое значение difficulty к строке лёгкая/средняя/сложная."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in DIFFICULTY_ALIASES:
        return DIFFICULTY_ALIASES[s]
    # числовое: 1-2 → лёгкая, 3 → средняя, 4-5 → сложная
    try:
        v = float(s)
        if v <= 2:
            return "лёгкая"
        if v <= 3:
            return "средняя"
        return "сложная"
    except ValueError:
        return None

def points_for_difficulty(difficulty_str: Optional[str]) -> int:
    d = normalize_difficulty(difficulty_str)
    return DIFFICULTY_POINTS.get(d, 10)


# ── Problems ──────────────────────────────────────────────────────────────────

async def add_problem(session: AsyncSession, data: dict) -> Optional[Problem]:
    """Добавить задачу; вернуть None если дубликат."""
    if data.get("source_url"):
        if await session.scalar(select(Problem).where(Problem.source_url == data["source_url"])):
            return None
    text_prefix = data.get("text", "")[:200]
    if await session.scalar(select(Problem).where(Problem.text.like(f"{text_prefix}%"))):
        return None

    # Нормализуем difficulty и проставляем points
    raw_diff = data.get("difficulty")
    norm_diff = normalize_difficulty(raw_diff)
    data = dict(data)
    if norm_diff:
        data["difficulty"] = norm_diff
    if not data.get("points"):
        data["points"] = points_for_difficulty(norm_diff)

    problem = Problem(**{k: v for k, v in data.items() if hasattr(Problem, k)})
    session.add(problem)
    await session.commit()
    await session.refresh(problem)
    logger.info("Добавлена задача id=%s topic=%s diff=%s", problem.id, problem.topic, problem.difficulty)
    return problem


async def get_random_problem(
    session: AsyncSession,
    topic: Optional[str] = None,
    grade: Optional[int] = None,
    telegram_id: Optional[int] = None,
    difficulty: Optional[str] = None,
) -> Optional[Problem]:
    """Случайная задача с фильтрами. Исключает «выжженные» (решены >= MAX_SOLVE_REPEATS)."""
    query = select(Problem)

    if topic:
        query = query.where(Problem.topic == topic)

    if difficulty:
        norm = normalize_difficulty(difficulty)
        if norm:
            query = query.where(Problem.difficulty == norm)

    if grade:
        query = query.where(
            or_(Problem.grade_min.is_(None), Problem.grade_min <= grade)
        ).where(
            or_(Problem.grade_max.is_(None), Problem.grade_max >= grade)
        )

    if telegram_id:
        overused = (
            select(UserProblemHistory.problem_id)
            .where(UserProblemHistory.telegram_id == telegram_id)
            .where(UserProblemHistory.solve_count >= MAX_SOLVE_REPEATS)
            .scalar_subquery()
        )
        query = query.where(Problem.id.not_in(overused))

    query = query.order_by(func.random()).limit(1)
    return await session.scalar(query)


async def get_daily_problems(
    session: AsyncSession,
    grade: Optional[int] = None,
    count: int = 5,
    telegram_id: Optional[int] = None,
) -> list[Problem]:
    query = select(Problem)
    if grade:
        query = query.where(
            or_(Problem.grade_min.is_(None), Problem.grade_min <= grade)
        ).where(
            or_(Problem.grade_max.is_(None), Problem.grade_max >= grade)
        )
    if telegram_id:
        overused = (
            select(UserProblemHistory.problem_id)
            .where(UserProblemHistory.telegram_id == telegram_id)
            .where(UserProblemHistory.solve_count >= MAX_SOLVE_REPEATS)
            .scalar_subquery()
        )
        query = query.where(Problem.id.not_in(overused))
    query = query.order_by(func.random()).limit(count)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_stats(session: AsyncSession) -> dict:
    total = await session.scalar(select(func.count()).select_from(Problem))
    rows = await session.execute(
        select(Problem.topic, func.count().label("cnt"))
        .group_by(Problem.topic).order_by(func.count().desc())
    )
    by_topic = {row.topic: row.cnt for row in rows}
    return {"total": total or 0, "by_topic": by_topic}


async def get_problem_by_id(session: AsyncSession, problem_id: int) -> Optional[Problem]:
    return await session.scalar(select(Problem).where(Problem.id == problem_id))


# ── Users ─────────────────────────────────────────────────────────────────────

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("Новый пользователь telegram_id=%s", telegram_id)
    else:
        # обновляем имя если пришло новое
        changed = False
        if username and user.username != username:
            user.username = username; changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name; changed = True
        if changed:
            await session.commit()
            await session.refresh(user)
    return user


async def set_user_grade(session: AsyncSession, telegram_id: int, grade: int) -> User:
    user = await get_or_create_user(session, telegram_id)
    user.grade = grade
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_topic(session: AsyncSession, telegram_id: int, topic: Optional[str]) -> User:
    user = await get_or_create_user(session, telegram_id)
    user.selected_topic = topic
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_difficulty(session: AsyncSession, telegram_id: int, difficulty: Optional[str]) -> User:
    user = await get_or_create_user(session, telegram_id)
    user.selected_difficulty = difficulty
    await session.commit()
    await session.refresh(user)
    return user


async def award_points(session: AsyncSession, telegram_id: int, pts: int) -> User:
    """Начислить очки и увеличить solved_count."""
    user = await get_or_create_user(session, telegram_id)
    user.points += pts
    user.solved_count += 1
    await session.commit()
    await session.refresh(user)
    return user


async def increment_user_attempts(session: AsyncSession, telegram_id: int) -> User:
    """Увеличить счётчик попыток пользователя."""
    user = await get_or_create_user(session, telegram_id)
    user.attempts_count += 1
    await session.commit()
    await session.refresh(user)
    return user


async def get_top_users(session: AsyncSession, limit: int = 10) -> list[User]:
    result = await session.execute(
        select(User).where(User.points > 0).order_by(desc(User.points)).limit(limit)
    )
    return list(result.scalars().all())


async def get_total_users(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(User)) or 0


async def get_user_recent_solved(session: AsyncSession, telegram_id: int, limit: int = 5) -> list[UserProblemHistory]:
    result = await session.execute(
        select(UserProblemHistory)
        .where(UserProblemHistory.telegram_id == telegram_id)
        .order_by(desc(UserProblemHistory.last_solved_at))
        .limit(limit)
    )
    return list(result.scalars().all())


# ── ActiveAttempts ────────────────────────────────────────────────────────────

async def get_active_attempt(session: AsyncSession, telegram_id: int) -> Optional[ActiveAttempt]:
    return await session.scalar(
        select(ActiveAttempt).where(ActiveAttempt.telegram_id == telegram_id)
    )


async def create_or_replace_attempt(
    session: AsyncSession, telegram_id: int, problem_id: int
) -> ActiveAttempt:
    existing = await get_active_attempt(session, telegram_id)
    if existing:
        await session.delete(existing)
        await session.flush()
    attempt = ActiveAttempt(
        telegram_id=telegram_id,
        problem_id=problem_id,
        attempts_used=0,
        is_solved=False,
        points_awarded=0,
        created_at=datetime.utcnow(),
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return attempt


async def increment_attempts(session: AsyncSession, telegram_id: int) -> Optional[ActiveAttempt]:
    attempt = await get_active_attempt(session, telegram_id)
    if not attempt:
        return None
    attempt.attempts_used += 1
    await session.commit()
    await session.refresh(attempt)
    return attempt


async def clear_attempt(session: AsyncSession, telegram_id: int) -> None:
    attempt = await get_active_attempt(session, telegram_id)
    if attempt:
        await session.delete(attempt)
        await session.commit()


# ── UserProblemHistory ────────────────────────────────────────────────────────

async def record_solved(
    session: AsyncSession, telegram_id: int, problem_id: int, points: int
) -> UserProblemHistory:
    """Записать или обновить факт решения задачи."""
    rec = await session.scalar(
        select(UserProblemHistory)
        .where(UserProblemHistory.telegram_id == telegram_id)
        .where(UserProblemHistory.problem_id == problem_id)
    )
    if rec:
        rec.solve_count += 1
        rec.points_awarded += points
        rec.last_solved_at = datetime.utcnow()
    else:
        rec = UserProblemHistory(
            telegram_id=telegram_id,
            problem_id=problem_id,
            solve_count=1,
            points_awarded=points,
            last_solved_at=datetime.utcnow(),
        )
        session.add(rec)
    await session.commit()
    await session.refresh(rec)
    return rec


async def get_total_solved(session: AsyncSession) -> int:
    """Всего правильных решений по всем пользователям."""
    return await session.scalar(select(func.sum(UserProblemHistory.solve_count))) or 0


async def get_total_attempts_all(session: AsyncSession) -> int:
    return await session.scalar(select(func.sum(User.attempts_count))) or 0



async def get_sources_stats(session: AsyncSession) -> list[tuple[str, int]]:
    """Статистика задач по источникам."""
    rows = await session.execute(
        select(Problem.source_name, func.count(Problem.id))
        .group_by(Problem.source_name)
        .order_by(func.count(Problem.id).desc())
    )
    return [(name or "Неизвестный источник", count) for name, count in rows.all()]
