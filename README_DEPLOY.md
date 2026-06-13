# 🚀 Деплой на Render — пошаговая инструкция

---

## Шаг 1 — Залейте проект на GitHub

1. Зайдите на [github.com](https://github.com) и создайте новый репозиторий (кнопка **New**)
2. Назовите его, например: `math-olympiad-bot`
3. Откройте терминал в папке проекта и выполните:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/ВАШ_ЛОГИН/math-olympiad-bot.git
git push -u origin main
```

> Если git не установлен — скачайте с [git-scm.com](https://git-scm.com)

---

## Шаг 2 — Зарегистрируйтесь на Render

Откройте [render.com](https://render.com) и войдите через GitHub (кнопка **Sign in with GitHub**).

---

## Шаг 3 — Создайте Web Service

1. Нажмите **New** → **Web Service**
2. В списке репозиториев найдите `math-olympiad-bot` и нажмите **Connect**

---

## Шаг 4 — Настройте сервис

Заполните поля:

| Поле | Значение |
|------|----------|
| **Name** | `math-olympiad-bot` (или любое) |
| **Region** | `Frankfurt (EU Central)` |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn webhook:app --host 0.0.0.0 --port $PORT` |
| **Plan** | `Free` |

---

## Шаг 5 — Добавьте переменные окружения

Прокрутите вниз до раздела **Environment Variables** и добавьте:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | Токен от BotFather (например: `123456:ABCdef...`) |
| `WEBHOOK_URL` | URL вашего сервиса на Render (см. ниже) |
| `ADMIN_ID` | Ваш Telegram ID (узнать у @userinfobot) |
| `DATABASE_URL` | `sqlite+aiosqlite:///problems.db` |

### Как узнать WEBHOOK_URL до деплоя?

URL Render формируется из названия сервиса:
```
https://ИМЯ-СЕРВИСА.onrender.com
```

Например, если назвали сервис `math-olympiad-bot`, то URL будет:
```
https://math-olympiad-bot.onrender.com
```

Вставьте этот URL в `WEBHOOK_URL` **без слэша в конце**.

---

## Шаг 6 — Запустите деплой

Нажмите кнопку **Create Web Service**.

Render начнёт сборку. В логах (вкладка **Logs**) вы увидите:

```
==> Installing dependencies...
==> Starting service...
INFO | db.database | База данных инициализирована.
INFO | webhook     | Webhook установлен: https://math-olympiad-bot.onrender.com/webhook
INFO | uvicorn     | Application startup complete.
```

Деплой занимает 2–5 минут.

---

## Шаг 7 — Проверьте что всё работает

1. Откройте ваш URL в браузере:
```
https://math-olympiad-bot.onrender.com
```
Должно показать:
```json
{"status": "bot is running", "webhook": "https://math-olympiad-bot.onrender.com/webhook"}
```

2. Откройте Telegram, найдите вашего бота и напишите `/start`

---

## ⚠️ Важно: спящий режим на бесплатном тарифе

На бесплатном тарифе Render **усыпляет сервис** через 15 минут неактивности.
При первом сообщении после сна бот может не ответить 30–60 секунд — это нормально.

Чтобы избежать засыпания — используйте платный тариф (`Starter`, от $7/мес)
или настройте внешний пинг сервиса (например, через [cron-job.org](https://cron-job.org)).

---

## 🔧 Если бот не работает

### Проверьте Render Logs

Вкладка **Logs** покажет все ошибки. Ищите строки с `ERROR` или `CRITICAL`.

### Частые проблемы:

**Бот не отвечает на сообщения**
- Проверьте, что `BOT_TOKEN` введён правильно (без пробелов)
- Проверьте, что `WEBHOOK_URL` указан без слэша в конце
- Убедитесь, что URL в `WEBHOOK_URL` совпадает с реальным URL сервиса на Render

**Ошибка `RuntimeError: BOT_TOKEN не задан`**
- Зайдите в Render → ваш сервис → **Environment** → убедитесь что `BOT_TOKEN` добавлен

**Ошибка `RuntimeError: WEBHOOK_URL не задан`**
- Добавьте `WEBHOOK_URL` в Environment Variables

**Страница показывает ошибку 502 или 503**
- Сервис засыпает на бесплатном тарифе — подождите 30 секунд и обновите
- Или проверьте Logs на ошибки при старте

**Start Command не работает**
- Убедитесь что команда точно: `uvicorn webhook:app --host 0.0.0.0 --port $PORT`
- Символы `--` это два дефиса, не тире

**`ModuleNotFoundError`**
- Убедитесь что все зависимости есть в `requirements.txt`
- Нажмите **Manual Deploy** → **Deploy latest commit** для пересборки

**В handlers.py нет router**
- Откройте `bot/handlers.py` и убедитесь что есть строка `router = Router()`

---

## 🔄 Обновление бота

После изменений в коде:

```bash
git add .
git commit -m "Описание изменений"
git push
```

Render автоматически подхватит новый коммит и пересоберёт сервис.

---

## 💻 Локальный запуск (для разработки)

Для разработки на своём компьютере используйте polling (не webhook):

```bash
# Скопируйте .env.example в .env и заполните BOT_TOKEN
cp .env.example .env

# Запустите через polling (WEBHOOK_URL не нужен)
python run.py
```

---

## 📋 Краткая сводка

| Что | Значение |
|-----|----------|
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn webhook:app --host 0.0.0.0 --port $PORT` |
| **BOT_TOKEN** | Токен от @BotFather |
| **WEBHOOK_URL** | `https://ИМЯ.onrender.com` (без слэша) |
| **ADMIN_ID** | Ваш Telegram ID |
| **DATABASE_URL** | `sqlite+aiosqlite:///problems.db` |
