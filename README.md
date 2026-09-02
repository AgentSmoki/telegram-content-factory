# Telegram Content Factory

**Контент-завод для Telegram: скилл для Claude Code, который превращает идею, голосовое, статью или видео в пост в голосе автора — и безопасно публикует его, от обычного текста до Rich Message с таблицами, спойлерами и слайдшоу.**

Skill for Claude Code that turns raw ideas, voice notes, articles and videos into Telegram posts in the author's voice — with a three-pass editing pipeline, premium-emoji previews and dry-run-first publishing. Docs are in Russian.

[![tests](https://img.shields.io/github/actions/workflow/status/AgentSmoki/telegram-content-factory/tests.yml?branch=main&style=flat-square&label=tests)](https://github.com/AgentSmoki/telegram-content-factory/actions)
[![release](https://img.shields.io/github/v/release/AgentSmoki/telegram-content-factory?display_name=tag&style=flat-square)](https://github.com/AgentSmoki/telegram-content-factory/releases)
[![license](https://img.shields.io/github/license/AgentSmoki/telegram-content-factory?style=flat-square)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude_Code-skill-D97757?style=flat-square)](SKILL.md)
[![TeleTranscribe](https://img.shields.io/badge/транскрибация-TeleTranscribe-2CA5E0?style=flat-square)](https://github.com/AgentSmoki/TeleTransribe)

## Чем отличается от «генераторов постов»

Генератор начинает с пустой страницы и заканчивает «каким-то текстом». Здесь — редакция целиком:

- **Формат-роутер.** Три типа постов (личная история / инсайты / шаги) с разными правилами структуры и разметки — тип выбирается до черновика.
- **Батарея хуков.** 5–10 вариантов первой строки четырьмя приёмами (личная выгода, скользкая горка, факт-якорь, PAS) — и только потом текст.
- **Редактура в три прохода.** Смысл → чистка языка (штампы, канцелярит, оценочные) → анти-AI-проход. Плюс детерминированный гейт `check_style.py` со встроенными русскими словарями: известные штампы и AI-фразы ловятся правилом, а не вкусом.
- **Память правок.** Каждая правка автора превращается в правило в `MEMORY.md`; устойчивые правила повышаются в профиль голоса. Скилл пишет лучше с каждым постом.
- **Premium-эмодзи превью.** Userbot-слой отправляет пост с кастомными эмодзи в превью-чат — то, чего Bot API без купленного username не умеет.
- **Транскрибация через [TeleTranscribe](https://github.com/AgentSmoki/TeleTransribe).** Голосовые, созвоны, YouTube — с диаризацией спикеров и word-level таймкодами, через MCP прямо в контекст агента.
- **Публикация с двойным подтверждением.** Сухой прогон по умолчанию; отправка требует `--send` плюс `--confirm-target`, посимвольно совпадающий с настроенным chat_id. Тест и прод — разные переменные и разные одобрения.

## Установка

```bash
git clone https://github.com/AgentSmoki/telegram-content-factory.git \
  ~/.claude/skills/telegram-content-factory
```

Перезапусти Claude Code и попробуй:

```text
Используй telegram-content-factory. Вот голосовое — расшифруй, собери карту
фактов, предложи 5 хуков и сделай пост в моём голосе. Ничего не публикуй.
```

Python-скрипты требуют 3.11+. Валидатор, стилевой гейт и превью работают без зависимостей; для публикации и эмодзи-слоя:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # aiogram + dotenv — публикация
pip install -r requirements-emoji.txt    # pyrogram — premium-эмодзи превью
python3 scripts/doctor.py                # диагностика (офлайн)
```

## Конвейер

```
источник → транскрипт (TeleTranscribe MCP) → карта фактов → бриф
→ формат-роутер → батарея хуков → черновик → редактура ×3
→ check_style.py → plain + rich варианты → validate_rich.py
→ превью (браузер / premium-эмодзи) → тест-канал → прод
```

Каждый материал живёт в одной папке (`scripts/init_material.py`): источник, транскрипт, карта фактов, бриф, хуки, оба варианта поста, медиа, отчёт приёмки. Любой факт прослеживается до источника, любая публикация — до одобрения.

## Скрипты

| Скрипт | Что делает | Сеть |
|---|---|---|
| `validate_rich.py` | офлайн-валидатор Rich HTML: allowlist Bot API 10.3, лимиты, медиа-инвариант | нет |
| `check_style.py` | стилевой гейт: штампы, канцелярит, AI-фразы, структурные лимиты | нет |
| `preview_rich.py` | приблизительное браузерное превью | нет |
| `init_material.py` | пакет материала: один пост = одна проверяемая папка | нет |
| `doctor.py` | диагностика установки | только с `--telegram` |
| `publish_rich.py` | Rich Message; сухой прогон по умолчанию | только с `--send` |
| `approve_send.py` | превью в личку автора + кнопки «✅ Опубликовать / ✖ Отмена»; галочка публикует в канал | да, превью + после ✅ |
| `publish_fallback.py` | обычный пост (с inline-кнопкой `--button "Текст\|URL"`) или альбом 2–10 медиа | только с `--send` |
| `emoji_send.py` | превью с кастомными Premium-эмодзи через userbot | да, в превью-чат |
| `emoji_extract.py` | выгрузка document_id из установленных emoji-паков | да, read-only |

## Rich Messages, когда они оправданы

Rich Message (Bot API 10.1+) даёт заголовки, таблицы, чек-листы, сворачиваемые блоки, сноски, формулы, карты, коллажи и свайп-слайдшоу. Старые клиенты показывают заглушку — поэтому plain-fallback готовится всегда, а rich-разметка обязана улучшать понимание, а не украшать.

```html
<h1>Заголовок, который сканируется</h1>
<aside><b>Ключевой вывод.</b></aside>
<table bordered compact>
  <tr><th>Вариант</th><th>Когда</th></tr>
  <tr><td>Plain</td><td>совместимость важнее</td></tr>
  <tr><td>Rich</td><td>структура улучшает понимание</td></tr>
</table>
<details><summary>Подробности</summary><p>Для дочитавших.</p></details>
```

Полная грамматика: [references/formatting.md](references/formatting.md).

## Безопасность

- Секреты — только в локальном `.env` (в `.gitignore`); в коде и документации живут имена переменных.
- Скрипты по умолчанию ничего не отправляют. Отправка = `--send` + точный `--confirm-target`. Прод дополнительно требует `--environment production`.
- Боту выдаётся единственное право Post Messages; тестовый канал приватный.
- Запрещены: выдумывание фактов и цитат, обход пейволов и DRM, публикация полных транскриптов чужих материалов.

## Карта репозитория

- [`SKILL.md`](SKILL.md) — инструкции агента и границы безопасности
- [`references/`](references) — формат-роутер, хуки, редактура, голос и память, Rich-грамматика, транскрибация, эмодзи, настройка, ошибки
- [`scripts/`](scripts) — детерминированные локальные инструменты
- [`assets/`](assets) — шаблоны профиля голоса, памяти, стилевого гейта, каталога эмодзи, пример Rich-поста
- [`tests/`](tests) — офлайн-тесты валидатора и стилевого гейта (`python3 -m unittest discover tests`)

## Лицензия

MIT © Богдан Корниенко ([Neuroimpulse](https://neuroimpuls.ru)). См. [LICENSE](LICENSE).
