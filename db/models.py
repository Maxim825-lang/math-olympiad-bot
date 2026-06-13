"""
Модели базы данных (SQLAlchemy ORM).
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    BigInteger, Boolean, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ── Задача ────────────────────────────────────────────────────────────────────

class Problem(Base):
    """Олимпиадная задача."""
    __tablename__ = "problems"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    title        = Column(String(500), nullable=True)
    text         = Column(Text, nullable=False)
    answer       = Column(Text, nullable=True)
    solution     = Column(Text, nullable=True)
    topic        = Column(String(100), nullable=False, default="разное")
    grade_min    = Column(Integer, nullable=True)
    grade_max    = Column(Integer, nullable=True)
    # difficulty: числовое 1–5 (парсеры) ИЛИ строка "лёгкая/средняя/сложная" (новые задачи)
    # Храним как строку; числовые значения тоже принимаем и конвертируем при показе
    difficulty   = Column(String(20), nullable=True)
    points       = Column(Integer, nullable=True)     # очки за задачу
    source_name  = Column(String(200), nullable=True)
    source_url   = Column(String(1000), nullable=True, unique=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Problem id={self.id} topic={self.topic!r}>"


# ── Пользователь ──────────────────────────────────────────────────────────────

class User(Base):
    """Пользователь Telegram-бота."""
    __tablename__ = "users"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id        = Column(BigInteger, unique=True, nullable=False)
    username           = Column(String(200), nullable=True)
    first_name         = Column(String(200), nullable=True)
    grade              = Column(Integer, nullable=True)
    solved_count       = Column(Integer, default=0, nullable=False)
    attempts_count     = Column(Integer, default=0, nullable=False)
    points             = Column(Integer, default=0, nullable=False)
    selected_topic     = Column(String(100), nullable=True)      # выбранная тема
    selected_difficulty = Column(String(20), nullable=True)      # выбранная сложность
    created_at         = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User telegram_id={self.telegram_id} points={self.points}>"


# ── Активная попытка ──────────────────────────────────────────────────────────

class ActiveAttempt(Base):
    """Текущая задача пользователя (одна на пользователя)."""
    __tablename__ = "active_attempts"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id    = Column(BigInteger, unique=True, nullable=False, index=True)
    problem_id     = Column(Integer, ForeignKey("problems.id"), nullable=False)
    attempts_used  = Column(Integer, default=0, nullable=False)
    is_solved      = Column(Boolean, default=False, nullable=False)
    points_awarded = Column(Integer, default=0, nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<ActiveAttempt telegram_id={self.telegram_id} "
            f"problem_id={self.problem_id} attempts={self.attempts_used}>"
        )


# ── История решений ───────────────────────────────────────────────────────────

class UserProblemHistory(Base):
    """
    История правильно решённых задач.
    solve_count — сколько раз пользователь решил задачу (макс 2, потом не показывается).
    """
    __tablename__ = "user_problem_history"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id    = Column(BigInteger, nullable=False, index=True)
    problem_id     = Column(Integer, ForeignKey("problems.id"), nullable=False)
    solve_count    = Column(Integer, default=1, nullable=False)
    points_awarded = Column(Integer, default=0, nullable=False)
    last_solved_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<UserProblemHistory telegram_id={self.telegram_id} "
            f"problem_id={self.problem_id} solve_count={self.solve_count}>"
        )


# ── FSM-состояния хранятся в памяти aiogram, таблица не нужна ─────────────────
