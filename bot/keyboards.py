"""
Клавиатуры для Telegram-бота.
"""

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)

# ── Темы ──────────────────────────────────────────────────────────────────────
TOPIC_BUTTONS = [
    ("🔵 Графы",         "графы"),
    ("🟣 Логика",        "логика"),
    ("🟠 Комбинаторика", "комбинаторика"),
    ("🔷 Геометрия",     "геометрия"),
    ("🟤 Алгебра",       "алгебра"),
    ("🔴 Теория чисел",  "теория чисел"),
    ("🎲 Любая тема",    "any"),
]

DIFFICULTY_BUTTONS = [
    ("🟢 Лёгкая",          "лёгкая"),
    ("🟡 Средняя",          "средняя"),
    ("🔴 Сложная",          "сложная"),
    ("🎲 Любая сложность",  "any"),
]


# ── Главное меню ──────────────────────────────────────────────────────────────

def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🧩 Новая задача"), KeyboardButton(text="📅 Задачи на день")],
        [KeyboardButton(text="🎯 Выбрать тему"), KeyboardButton(text="⚙️ Выбрать сложность")],
        [KeyboardButton(text="👤 Профиль"),       KeyboardButton(text="🏆 Рейтинг")],
        [KeyboardButton(text="ℹ️ Помощь")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="🛠 Админка")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True,
                               input_field_placeholder="Выберите действие...")


# ── Меню после задачи ─────────────────────────────────────────────────────────

def get_task_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Следующая задача", callback_data="next_problem")],
        [InlineKeyboardButton(text="🎯 Сменить тему",     callback_data="choose_topic"),
         InlineKeyboardButton(text="⚙️ Сменить сложность", callback_data="choose_difficulty")],
    ])


# ── Выбор темы ────────────────────────────────────────────────────────────────

def get_topic_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"set_topic:{value}")]
        for label, value in TOPIC_BUTTONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Выбор сложности ───────────────────────────────────────────────────────────

def get_difficulty_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"set_diff:{value}")]
        for label, value in DIFFICULTY_BUTTONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Кнопка "Получить задачу" ──────────────────────────────────────────────────

def get_start_problem_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧩 Получить задачу", callback_data="next_problem")]
    ])


# ── Админ-меню ────────────────────────────────────────────────────────────────

def get_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить задачу",  callback_data="admin_add_problem")],
        [InlineKeyboardButton(text="📊 Статистика бота",  callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔎 Найти задачи",    callback_data="admin_find_problems")],
        [InlineKeyboardButton(text="⬅️ Назад",            callback_data="admin_back")],
    ])


# ── Тема для добавления задачи (FSM) ─────────────────────────────────────────

def get_topic_keyboard_fsm() -> InlineKeyboardMarkup:
    """Клавиатура выбора темы внутри FSM (без «любая тема»)."""
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"fsm_topic:{value}")]
        for label, value in TOPIC_BUTTONS
        if value != "any"
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_difficulty_keyboard_fsm() -> InlineKeyboardMarkup:
    """Клавиатура выбора сложности внутри FSM (без «любая»)."""
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"fsm_diff:{value}")]
        for label, value in DIFFICULTY_BUTTONS
        if value != "any"
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Совместимость со старым кодом ─────────────────────────────────────────────

def topics_keyboard() -> InlineKeyboardMarkup:
    return get_topic_keyboard()

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return get_main_menu(is_admin=False)
