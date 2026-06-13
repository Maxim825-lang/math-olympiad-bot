# 🧮 Math Olympiad Bot

Telegram-бот для подбора олимпиадных задач по математике.

---

## 📦 Установка зависимостей

```bash
# Клонируйте или скачайте проект
cd math_olympiad_bot

# Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate        # Linux/Mac
# или
venv\Scripts\activate           # Windows

# Установите зависимости
pip install -r requirements.txt
```

---

## 🤖 Создание бота через BotFather

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Введите имя бота (например: `Math Olympiad Bot`)
4. Введите username (например: `my_math_olympiad_bot`)
5. Скопируйте полученный **токен** (вида `123456789:AABBccDDeeff...`)

---

## ⚙️ Настройка .env

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

Откройте `.env` и вставьте свои данные:

```env
BOT_TOKEN=123456789:AABBccDDeeff...   # Токен от BotFather
ADMIN_ID=987654321                    # Ваш Telegram ID (узнать: @userinfobot)
DATABASE_URL=sqlite+aiosqlite:///problems.db
```

---

## 🚀 Запуск

```bash
python run.py
```

При первом запуске:
- Автоматически создаётся база данных `problems.db`
- Загружаются 13 тестовых задач по всем темам
- Бот готов к работе без парсинга

---

## 📋 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и главное меню |
| `/help` | Список команд |
| `/topics` | Выбор темы через кнопки |
| `/problem` | Случайная задача |
| `/problem геометрия` | Задача по теме |
| `/setclass 9` | Сохранить свой класс (5–11) |
| `/daily` | Подборка из 5 задач на сегодня |
| `/stats` | Статистика базы задач |
| `/parse` | Запуск парсеров *(только для Admin)* |

**Доступные темы:**
`теория чисел`, `комбинаторика`, `геометрия`, `алгебра`,
`логика`, `графы`, `инварианты`, `игры`, `разное`

---

## 🔌 Как добавить новый парсер

### 1. Создайте файл парсера

Скопируйте шаблон:

```bash
cp parsers/example_parser.py parsers/my_site_parser.py
```

### 2. Настройте класс

Откройте `parsers/my_site_parser.py` и замените:

```python
class MySiteParser(BaseParser):
    source_name = "Название сайта"
    base_url = "https://my-math-site.com"

    # CSS-селекторы — найдите их в браузере (F12 → Elements → Ctrl+F)
    SELECTOR_PROBLEM_LINKS = "a.task-link"    # ссылки на задачи
    SELECTOR_TITLE = "h1.task-title"          # заголовок задачи
    SELECTOR_TEXT = "div.task-body"           # текст задачи
    SELECTOR_ANSWER = "span.answer"           # ответ (если есть)

    LIST_URLS = [
        "https://my-math-site.com/tasks/page/1",
        "https://my-math-site.com/tasks/page/2",
    ]
```

### 3. Зарегистрируйте парсер

В файле `parsers/manager.py`:

```python
from parsers.my_site_parser import MySiteParser

REGISTERED_PARSERS = [
    MySiteParser(),
]
```

### 4. Запустите парсинг

В Telegram: `/parse` (от имени администратора)

---

## ⚠️ Важно про парсинг

Используйте только те сайты, которые:
- Явно разрешают автоматический сбор данных
- Не запрещают боты в `robots.txt`
- Не требуют авторизации для просмотра задач

---

## 📁 Структура проекта

```
math_olympiad_bot/
├── bot/
│   ├── handlers.py      # Обработчики команд
│   ├── keyboards.py     # Клавиатуры
│   └── main.py          # Инициализация бота
├── db/
│   ├── models.py        # Модели SQLAlchemy
│   ├── database.py      # Подключение к БД
│   ├── crud.py          # CRUD-операции
│   └── seed_data.py     # Тестовые задачи
├── parsers/
│   ├── base.py          # Базовый класс парсера
│   ├── example_parser.py # Шаблон парсера
│   └── manager.py       # Менеджер парсеров
├── services/
│   ├── classifier.py    # Классификация задач
│   └── problem_selector.py # Выбор и форматирование
├── .env.example         # Пример конфигурации
├── requirements.txt
├── run.py               # Точка входа
└── README.md
```
