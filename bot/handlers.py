"""
Обработчики команд и сообщений Telegram-бота.
"""

import logging
import os
import re
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from db.database import AsyncSessionLocal
from db import crud
from db.crud import normalize_difficulty, points_for_difficulty
from bot.keyboards import (
    get_main_menu, get_task_menu, get_topic_keyboard, get_difficulty_keyboard,
    get_start_problem_keyboard, get_admin_keyboard,
    get_topic_keyboard_fsm, get_difficulty_keyboard_fsm,
)
from services.problem_selector import (
    select_problem, select_daily,
    format_problem_question, format_problem_solution,
    MAX_ATTEMPTS,
)
from parsers.manager import run_all_parsers, run_parser_for_urls

logger = logging.getLogger(__name__)
router = Router()

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


# ── FSM: добавление задачи админом ───────────────────────────────────────────

class AddProblem(StatesGroup):
    waiting_text       = State()
    waiting_answer     = State()
    waiting_solution   = State()
    waiting_topic      = State()
    waiting_difficulty = State()


# ── Нормализация ответа ───────────────────────────────────────────────────────

def normalize_answer(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text


def answers_match(user_answer: str, correct_answer: str) -> bool:
    u = normalize_answer(user_answer)
    c = normalize_answer(correct_answer)
    if u == c:
        return True
    try:
        return float(re.sub(r"\s", "", u)) == float(re.sub(r"\s", "", c))
    except ValueError:
        return False


def _is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    tg = message.from_user
    async with AsyncSessionLocal() as session:
        await crud.get_or_create_user(
            session, tg.id,
            username=tg.username,
            first_name=tg.first_name,
        )
    text = (
        "👋 Привет! Я бот для подбора <b>олимпиадных задач по математике</b>.\n\n"
        "🔹 Выдаю задачи по теме и сложности\n"
        "🔹 Проверяю ответы — 3 попытки на задачу\n"
        "🔹 Начисляю очки и веду рейтинг\n\n"
        "Нажми <b>🧩 Новая задача</b> чтобы начать 👇"
    )
    await message.answer(text, parse_mode="HTML",
                         reply_markup=get_main_menu(is_admin=_is_admin(tg.id)))


# ── /help / ℹ️ Помощь ─────────────────────────────────────────────────────────

@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message) -> None:
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "🧩 <b>Новая задача</b> — получить задачу\n"
        "🎯 <b>Выбрать тему</b> — графы, логика, комбинаторика и др.\n"
        "⚙️ <b>Выбрать сложность</b> — лёгкая, средняя, сложная\n"
        "👤 <b>Профиль</b> — твоя статистика и очки\n"
        "🏆 <b>Рейтинг</b> — топ игроков по очкам\n"
        "📅 <b>Задачи на день</b> — подборка из 5 задач\n\n"
        "💡 Ответ и решение открываются только после 3 попыток "
        "или при правильном ответе.\n\n"
        "<b>Очки:</b> лёгкая = 5 🟢 | средняя = 10 🟡 | сложная = 20 🔴"
    )
    await message.answer(text, parse_mode="HTML")


# ── /topics / 🎯 Выбрать тему ─────────────────────────────────────────────────

@router.message(Command("topics"))
@router.message(F.text == "🎯 Выбрать тему")
async def cmd_topics(message: Message) -> None:
    await message.answer(
        "🎯 <b>Выберите тему задач:</b>",
        parse_mode="HTML",
        reply_markup=get_topic_keyboard(),
    )


# ── ⚙️ Выбрать сложность ──────────────────────────────────────────────────────

@router.message(F.text == "⚙️ Выбрать сложность")
async def cmd_difficulty(message: Message) -> None:
    await message.answer(
        "⚙️ <b>Выберите сложность задач:</b>",
        parse_mode="HTML",
        reply_markup=get_difficulty_keyboard(),
    )


# ── Callback: выбор темы ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("set_topic:"))
async def cb_set_topic(callback: CallbackQuery) -> None:
    value = callback.data.split(":", 1)[1]
    tg_id = callback.from_user.id
    topic = None if value == "any" else value
    async with AsyncSessionLocal() as session:
        await crud.set_user_topic(session, tg_id, topic)
    label = "Любая тема 🎲" if topic is None else topic.capitalize()
    await callback.message.edit_text(
        f"✅ Тема выбрана: <b>{label}</b>",
        parse_mode="HTML",
        reply_markup=get_start_problem_keyboard(),
    )
    await callback.answer()


# ── Callback: выбор сложности ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("set_diff:"))
async def cb_set_difficulty(callback: CallbackQuery) -> None:
    value = callback.data.split(":", 1)[1]
    tg_id = callback.from_user.id
    difficulty = None if value == "any" else value
    async with AsyncSessionLocal() as session:
        await crud.set_user_difficulty(session, tg_id, difficulty)
    label = "Любая сложность 🎲" if difficulty is None else difficulty.capitalize()
    await callback.message.edit_text(
        f"✅ Сложность выбрана: <b>{label}</b>",
        parse_mode="HTML",
        reply_markup=get_start_problem_keyboard(),
    )
    await callback.answer()


# ── Callback: показать выбор темы ─────────────────────────────────────────────

@router.callback_query(F.data == "choose_topic")
async def cb_choose_topic(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "🎯 <b>Выберите тему задач:</b>",
        parse_mode="HTML",
        reply_markup=get_topic_keyboard(),
    )
    await callback.answer()


# ── Callback: показать выбор сложности ───────────────────────────────────────

@router.callback_query(F.data == "choose_difficulty")
async def cb_choose_difficulty(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "⚙️ <b>Выберите сложность задач:</b>",
        parse_mode="HTML",
        reply_markup=get_difficulty_keyboard(),
    )
    await callback.answer()


# ── Выдача задачи (общая логика) ──────────────────────────────────────────────

async def _send_problem(
    message: Message,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    user_id: Optional[int] = None,
) -> None:
    tg_id = user_id or (message.from_user.id if message.from_user else 0)

    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(session, tg_id)
        # Если тема/сложность не переданы явно — берём из профиля
        eff_topic = topic if topic is not None else user.selected_topic
        eff_diff  = difficulty if difficulty is not None else user.selected_difficulty

        problem = await crud.get_random_problem(
            session,
            topic=eff_topic,
            grade=user.grade,
            telegram_id=tg_id,
            difficulty=eff_diff,
        )

        if not problem and user.grade:
            # попробовать без фильтра класса
            problem = await crud.get_random_problem(
                session, topic=eff_topic, telegram_id=tg_id, difficulty=eff_diff
            )

        if not problem and (eff_topic or eff_diff):
            # попробовать без темы/сложности
            problem = await crud.get_random_problem(session, telegram_id=tg_id)

        if not problem:
            hint_parts = []
            if eff_topic:  hint_parts.append(f"теме <b>{eff_topic}</b>")
            if eff_diff:   hint_parts.append(f"сложности <b>{eff_diff}</b>")
            hint = " и ".join(hint_parts)
            await message.answer(
                f"😔 Подходящих задач по {hint} пока нет.\n"
                "Попробуйте выбрать другую тему или сложность.",
                parse_mode="HTML",
                reply_markup=get_topic_keyboard(),
            )
            return

        await crud.create_or_replace_attempt(session, tg_id, problem.id)

    await message.answer(format_problem_question(problem), parse_mode="HTML")


# ── /problem ──────────────────────────────────────────────────────────────────

@router.message(Command("problem"))
@router.message(F.text == "🧩 Новая задача")
async def cmd_problem(message: Message) -> None:
    topic = None
    if message.text and message.text.startswith("/problem"):
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            topic = parts[1].strip().lower()
    await _send_problem(message, topic=topic)


# ── Callback: следующая задача ────────────────────────────────────────────────

@router.callback_query(F.data == "next_problem")
async def cb_next_problem(callback: CallbackQuery) -> None:
    await callback.answer()
    await _send_problem(callback.message, user_id=callback.from_user.id)


# ── Callback: старый формат topic:<name> (совместимость) ─────────────────────

@router.callback_query(F.data.startswith("topic:"))
async def callback_topic_compat(callback: CallbackQuery) -> None:
    topic = callback.data.split(":", 1)[1]
    await callback.answer()
    await _send_problem(callback.message, topic=topic, user_id=callback.from_user.id)


# ── /daily / 📅 Задачи на день ────────────────────────────────────────────────

@router.message(Command("daily"))
@router.message(F.text == "📅 Задачи на день")
async def cmd_daily(message: Message) -> None:
    tg_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(session, tg_id)
        problems = await crud.get_daily_problems(
            session, grade=user.grade, count=5, telegram_id=tg_id
        )

    if not problems:
        await message.answer("😔 В базе пока нет задач. Загляните позже!")
        return

    await message.answer(
        "📅 <b>Подборка задач на сегодня</b> (5 штук):\n\n"
        "Отвечай на задачи по очереди — бот запомнит последнюю активную.",
        parse_mode="HTML",
    )
    for i, problem in enumerate(problems, start=1):
        async with AsyncSessionLocal() as session:
            await crud.create_or_replace_attempt(session, tg_id, problem.id)
        await message.answer(format_problem_question(problem, index=i), parse_mode="HTML")


# ── /setclass ─────────────────────────────────────────────────────────────────

@router.message(Command("setclass"))
async def cmd_setclass(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer(
            "⚠️ Укажите класс: <code>/setclass 9</code>\nДопустимые значения: 5–11",
            parse_mode="HTML",
        )
        return
    grade = int(parts[1].strip())
    if grade < 5 or grade > 11:
        await message.answer("⚠️ Класс должен быть от 5 до 11.")
        return
    async with AsyncSessionLocal() as session:
        await crud.set_user_grade(session, message.from_user.id, grade)
    await message.answer(
        f"✅ Класс сохранён: <b>{grade}</b>",
        parse_mode="HTML",
    )


# ── /stats / 📊 Статистика ────────────────────────────────────────────────────

@router.message(Command("stats"))
@router.message(F.text == "📊 Статистика")
async def cmd_stats(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        stats = await crud.get_stats(session)
    lines = [
        "📊 <b>Статистика базы задач:</b>\n",
        f"Всего задач: <b>{stats['total']}</b>\n",
    ]
    if stats["by_topic"]:
        lines.append("<b>По темам:</b>")
        for topic, count in stats["by_topic"].items():
            lines.append(f"  • {topic}: {count}")
    else:
        lines.append("<i>База пуста.</i>")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /profile / 👤 Профиль ─────────────────────────────────────────────────────

@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message) -> None:
    tg_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, tg_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        recent = await crud.get_user_recent_solved(session, tg_id, limit=5)
        # Подгружаем задачи для последних решений
        recent_problems = []
        for h in recent:
            p = await crud.get_problem_by_id(session, h.problem_id)
            if p:
                recent_problems.append((p, h))

    if user.solved_count == 0:
        await message.answer(
            "👤 <b>Профиль</b>\n\nПока статистики нет. Реши первую задачу!",
            parse_mode="HTML",
            reply_markup=get_task_menu(),
        )
        return

    name = f"@{user.username}" if user.username else (user.first_name or f"ID {tg_id}")
    pct = int(user.solved_count / max(user.attempts_count, 1) * 100) if user.attempts_count else 0

    lines = [
        "👤 <b>Профиль</b>\n",
        f"Имя: <b>{name}</b>",
        f"ID: <code>{tg_id}</code>\n",
        f"✅ Решено задач: <b>{user.solved_count}</b>",
        f"🎯 Очки: <b>{user.points}</b>",
        f"✍️ Попыток всего: <b>{user.attempts_count}</b>",
        f"📊 Процент правильных: <b>{pct}%</b>",
    ]

    if recent_problems:
        lines.append("\n<b>Последние решённые:</b>")
        for i, (p, h) in enumerate(recent_problems, 1):
            diff_label = p.difficulty or "—"
            pts = h.points_awarded
            lines.append(f"{i}. {p.topic.capitalize()} — {diff_label} — {pts} оч.")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /rating / 🏆 Рейтинг ──────────────────────────────────────────────────────

@router.message(Command("rating"))
@router.message(F.text == "🏆 Рейтинг")
async def cmd_rating(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        top = await crud.get_top_users(session, limit=10)

    if not top:
        await message.answer("🏆 <b>Рейтинг пока пустой.</b>", parse_mode="HTML")
        return

    lines = ["🏆 <b>Рейтинг по очкам</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(top, 1):
        medal = medals[i - 1] if i <= 3 else f"{i}."
        name = f"@{u.username}" if u.username else (u.first_name or f"ID {u.telegram_id}")
        lines.append(f"{medal} {name} — <b>{u.points}</b> оч., {u.solved_count} задач")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /admin / 🛠 Админка ───────────────────────────────────────────────────────

@router.message(Command("admin"))
@router.message(F.text == "🛠 Админка")
async def cmd_admin(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к админке.")
        return
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


# ── Callback: кнопки админки ──────────────────────────────────────────────────

@router.callback_query(F.data == "admin_back")
async def cb_admin_back(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        "🛠 <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    async with AsyncSessionLocal() as session:
        total_users    = await crud.get_total_users(session)
        problem_stats  = await crud.get_stats(session)
        total_solved   = await crud.get_total_solved(session)
        total_attempts = await crud.get_total_attempts_all(session)
        top            = await crud.get_top_users(session, limit=1)

    leader = "—"
    if top:
        u = top[0]
        leader = (f"@{u.username}" if u.username else f"ID {u.telegram_id}") + f" — {u.points} оч."

    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"🧩 Задач в базе: <b>{problem_stats['total']}</b>\n"
        f"✅ Решений: <b>{total_solved}</b>\n"
        f"✍️ Попыток: <b>{total_attempts}</b>\n"
        f"🏆 Лидер: <b>{leader}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    await callback.answer()


# ── FSM: добавление задачи ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_add_problem")
async def cb_admin_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.set_state(AddProblem.waiting_text)
    await callback.message.answer(
        "📝 <b>Шаг 1/5.</b> Введи <b>условие задачи</b>:\n\n"
        "<i>(Отправь /cancel чтобы отменить)</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("❌ Действие отменено.")


@router.message(AddProblem.waiting_text)
async def fsm_got_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text.strip())
    await state.set_state(AddProblem.waiting_answer)
    await message.answer(
        "✅ Условие сохранено.\n\n"
        "📝 <b>Шаг 2/5.</b> Введи <b>ответ</b> на задачу:",
        parse_mode="HTML",
    )


@router.message(AddProblem.waiting_answer)
async def fsm_got_answer(message: Message, state: FSMContext) -> None:
    await state.update_data(answer=message.text.strip())
    await state.set_state(AddProblem.waiting_solution)
    await message.answer(
        "✅ Ответ сохранён.\n\n"
        "📝 <b>Шаг 3/5.</b> Введи <b>решение</b> (или напиши «нет» если нет):",
        parse_mode="HTML",
    )


@router.message(AddProblem.waiting_solution)
async def fsm_got_solution(message: Message, state: FSMContext) -> None:
    solution = message.text.strip()
    if solution.lower() in ("нет", "no", "-", "—"):
        solution = None
    await state.update_data(solution=solution)
    await state.set_state(AddProblem.waiting_topic)
    await message.answer(
        "✅ Решение сохранено.\n\n"
        "📝 <b>Шаг 4/5.</b> Выбери <b>тему</b>:",
        parse_mode="HTML",
        reply_markup=get_topic_keyboard_fsm(),
    )


@router.callback_query(F.data.startswith("fsm_topic:"), AddProblem.waiting_topic)
async def fsm_got_topic(callback: CallbackQuery, state: FSMContext) -> None:
    topic = callback.data.split(":", 1)[1]
    await state.update_data(topic=topic)
    await state.set_state(AddProblem.waiting_difficulty)
    await callback.message.edit_text(
        f"✅ Тема: <b>{topic}</b>\n\n"
        "📝 <b>Шаг 5/5.</b> Выбери <b>сложность</b>:",
        parse_mode="HTML",
        reply_markup=get_difficulty_keyboard_fsm(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fsm_diff:"), AddProblem.waiting_difficulty)
async def fsm_got_difficulty(callback: CallbackQuery, state: FSMContext) -> None:
    difficulty = callback.data.split(":", 1)[1]
    data = await state.get_data()
    await state.clear()

    pts = points_for_difficulty(difficulty)
    problem_data = {
        "text":       data["text"],
        "answer":     data.get("answer"),
        "solution":   data.get("solution"),
        "topic":      data["topic"],
        "difficulty": difficulty,
        "points":     pts,
        "source_name": f"Добавлено админом (ID {callback.from_user.id})",
    }

    async with AsyncSessionLocal() as session:
        result = await crud.add_problem(session, problem_data)

    if result:
        await callback.message.edit_text(
            f"✅ <b>Задача добавлена!</b>\n\n"
            f"Тема: {data['topic']} | Сложность: {difficulty} | Очки: {pts}\n"
            f"ID задачи: #{result.id}",
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            "⚠️ Задача не добавлена (возможно, дубликат).",
            parse_mode="HTML",
        )
    await callback.answer()


# ── /parse и /sources (для админа) ───────────────────────────────────────────

URL_RE = re.compile(r"https?://\S+")


@router.callback_query(F.data == "admin_find_problems")
async def cb_admin_find_problems(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await callback.message.answer(
        "🔎 <b>Поиск задач через парсер</b>\n\n"
        "Отправь команду с ссылками:\n"
        "<code>/parse https://example.com/problems</code>\n\n"
        "Можно указать несколько ссылок через пробел. Парсер работает только с публичными HTML-страницами.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(Command("parse"))
async def cmd_parse(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return

    urls = URL_RE.findall(message.text or "")
    if not urls:
        await message.answer(
            "⚠️ Отправь ссылки после команды.\n\n"
            "Пример:\n<code>/parse https://example.com/problems</code>",
            parse_mode="HTML",
        )
        return

    await message.answer("🔎 Начинаю поиск задач... Это может занять немного времени.")
    try:
        async with AsyncSessionLocal() as session:
            result = await run_parser_for_urls(session, urls)
        await message.answer(
            "✅ <b>Парсер завершён</b>\n\n"
            f"Найдено: <b>{result['found']}</b>\n"
            f"Добавлено: <b>{result['added']}</b>\n"
            f"Пропущено дублей: <b>{result['skipped']}</b>\n"
            f"Ошибок: <b>{result['errors']}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Ошибка парсинга URL: %s", e)
        await message.answer(f"❌ Ошибка парсера: {e}")


@router.message(Command("sources"))
async def cmd_sources(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return
    async with AsyncSessionLocal() as session:
        rows = await crud.get_sources_stats(session)

    if not rows:
        await message.answer("Источников пока нет.")
        return

    lines = ["📚 <b>Источники задач</b>\n"]
    for name, count in rows[:30]:
        lines.append(f"• {name}: <b>{count}</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── Проверка ответа пользователя ──────────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/"), StateFilter(None))
async def handle_answer(message: Message) -> None:
    tg_id = message.from_user.id
    user_text = message.text.strip()

    # Кнопки главного меню не проверяем как ответ
    menu_texts = {
        "🧩 Новая задача", "📅 Задачи на день", "🎯 Выбрать тему",
        "⚙️ Выбрать сложность", "👤 Профиль", "🏆 Рейтинг",
        "ℹ️ Помощь", "🛠 Админка", "📊 Статистика",
        "🎲 Случайная задача",  # совместимость
    }
    if user_text in menu_texts:
        return

    async with AsyncSessionLocal() as session:
        attempt = await crud.get_active_attempt(session, tg_id)

        if not attempt:
            await message.answer(
                "У тебя сейчас нет активной задачи.\n"
                "Нажми <b>🧩 Новая задача</b> чтобы начать.",
                parse_mode="HTML",
            )
            return

        problem = await crud.get_problem_by_id(session, attempt.problem_id)
        if not problem:
            await crud.clear_attempt(session, tg_id)
            await message.answer("Задача не найдена. Попробуй /problem.")
            return

        # Нет проверяемого ответа
        if not problem.answer:
            await crud.clear_attempt(session, tg_id)
            sol = format_problem_solution(problem)
            await message.answer(
                "У этой задачи нет проверяемого ответа.\n\n" + (sol or "Решение не указано."),
                parse_mode="HTML",
                reply_markup=get_task_menu(),
            )
            return

        # Считаем попытку пользователя
        await crud.increment_user_attempts(session, tg_id)

        if answers_match(user_text, problem.answer):
            # ── Правильный ответ ──────────────────────────────────────────
            attempts_used = attempt.attempts_used + 1
            pts = problem.points or points_for_difficulty(problem.difficulty)

            await crud.clear_attempt(session, tg_id)
            await crud.award_points(session, tg_id, pts)
            await crud.record_solved(session, tg_id, problem.id, pts)

            word = _attempts_word(attempts_used)
            await message.answer(
                f"✅ <b>Верно!</b> Решено за {attempts_used} {word}.\n"
                f"🎯 Начислено очков: <b>+{pts}</b>",
                parse_mode="HTML",
            )
            sol = format_problem_solution(problem)
            if sol:
                await message.answer(sol, parse_mode="HTML")
            await message.answer(
                "Хочешь ещё задачу?",
                reply_markup=get_task_menu(),
            )

        else:
            # ── Неправильный ответ ────────────────────────────────────────
            updated = await crud.increment_attempts(session, tg_id)
            used = updated.attempts_used
            remaining = MAX_ATTEMPTS - used

            if remaining > 0:
                await message.answer(
                    f"❌ <b>Неверно.</b> Осталось попыток: <b>{remaining}</b> {_attempts_word(remaining)}.\n"
                    "Попробуй ещё раз.",
                    parse_mode="HTML",
                )
            else:
                await crud.clear_attempt(session, tg_id)
                await message.answer(
                    f"❌ <b>Попытки закончились.</b>\n"
                    f"Правильный ответ: <b>{problem.answer}</b>",
                    parse_mode="HTML",
                )
                sol = format_problem_solution(problem)
                if sol:
                    await message.answer(sol, parse_mode="HTML")
                await message.answer(
                    "Попробуй следующую?",
                    reply_markup=get_task_menu(),
                )


def _attempts_word(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "попыток"
    r = n % 10
    if r == 1: return "попытку"
    if 2 <= r <= 4: return "попытки"
    return "попыток"
