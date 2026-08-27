# Настройка Telegram: бот, каналы, .env

## 1. Создание бота

1. В Telegram открой [@BotFather](https://t.me/BotFather) → `/newbot`.
2. Имя и username бота → в ответ придёт токен вида `1234567890:AA...`.
3. Токен — секрет. Он живёт только в локальном `.env`; в чаты, скриншоты и коммиты попадает только имя переменной.

## 2. Тестовый канал (обязателен)

1. Создай приватный канал «<канал> — тест».
2. Добавь бота администратором с единственным правом **Post Messages**.
3. Узнай chat_id канала: перешли любой пост канала боту [@getidsbot](https://t.me/getidsbot), либо временно добавь тестовый пост и посмотри `forward_from_chat.id`. Для каналов chat_id начинается с `-100`.

## 3. Продовый канал (после успешных тестов)

Тот же порядок: бот-админ, только Post Messages. Прод и тест — разные переменные, чтобы перепутать адресата было технически сложно.

## 4. Файл .env

```bash
cp .env.example .env
```

```
# Публикация через Bot API
TELEGRAM_BOT_TOKEN=1234567890:AA...
TELEGRAM_TEST_CHAT_ID=-1001111111111
TELEGRAM_PROD_CHAT_ID=-1002222222222

# Эмодзи-слой (опционально, my.telegram.org)
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
EMOJI_PREVIEW_CHAT=me
```

`.env` внесён в `.gitignore`. Проверь установку:

```bash
python3 scripts/doctor.py            # офлайн
python3 scripts/doctor.py --telegram # + один вызов getMe
```

## 5. Установка зависимостей

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # aiogram + dotenv (публикация)
pip install -r requirements-emoji.txt    # pyrogram (эмодзи-превью, опционально)
```

Валидатор, стилевой гейт и превью работают на чистом Python 3.11+ без зависимостей.

## 6. Первый тест

```bash
python3 scripts/publish_fallback.py assets/rich-post.example.html --mode plain
# сухой прогон прошёл → согласуй отправку →
python3 scripts/publish_rich.py assets/rich-post.example.html \
  --send --confirm-target=<TELEGRAM_TEST_CHAT_ID>
```

Правило на каждый день: тест-канал по умолчанию, прод — только с флагом `--environment production`, свежим одобрением и точным `--confirm-target`.
