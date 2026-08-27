#!/usr/bin/env python3
"""Превью поста с кастомными Premium-эмодзи через Pyrogram userbot.

Бот через Bot API отправляет кастомные эмодзи только при купленном
username на Fragment, поэтому превью с фирменными эмодзи проще делать
userbot'ом с Telegram Premium: скрипт заменяет маркеры [EMOJI:name]
на entity MessageEntityCustomEmoji и шлёт результат в превью-чат
(по умолчанию — «Избранное»).

Поддерживаемые маркеры в тексте:
    [EMOJI:name]  — кастомный эмодзи из каталога
    **текст**     — жирный
    <u>текст</u>  — подчёркивание

Использование:
    python3 emoji_send.py draft.txt
    python3 emoji_send.py draft.txt --catalog assets/emoji-catalog.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = ROOT / "emoji-catalog.json"
DEFAULT_SESSION = str(ROOT / "userbot_session")

RE_MARKER = re.compile(
    r"\[EMOJI:(\w+)\]"      # [EMOJI:name]
    r"|\*\*(.+?)\*\*"       # **жирный**
    r"|<u>(.+?)</u>",       # <u>подчёркивание</u>
    re.DOTALL,
)


def utf16_units(s: str) -> int:
    """Длина в UTF-16 code units — так Telegram считает offset/length."""
    return len(s.encode("utf-16-le")) // 2


def load_catalog(path: Path) -> dict:
    if not path.is_file():
        print(f"ОШИБКА: каталог эмодзи не найден: {path}", file=sys.stderr)
        print("Создай его из assets/emoji-catalog.template.json и заполни", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(path.read_text(encoding="utf-8")).get("emoji", {})


def build_entities(raw: str, catalog: dict) -> tuple[str, list]:
    """Возвращает (чистый текст, raw-entities) для отправки."""
    import pyrogram.raw.types as types

    clean = ""
    entities: list = []
    unknown: list[str] = []
    last = 0

    for m in RE_MARKER.finditer(raw):
        clean += raw[last:m.start()]
        if m.group(1) is not None:
            name = m.group(1)
            info = catalog.get(name)
            if info is None:
                unknown.append(name)
                last = m.end()
                continue
            fallback = info.get("fallback", "⭐")
            doc_id = str(info.get("id", ""))
            if doc_id.isdigit():
                entities.append(
                    types.MessageEntityCustomEmoji(
                        offset=utf16_units(clean),
                        length=utf16_units(fallback),
                        document_id=int(doc_id),
                    )
                )
            else:
                print(f"ПРЕДУПРЕЖДЕНИЕ: у {name!r} нет document_id — оставлен {fallback}")
            clean += fallback
        elif m.group(2) is not None:
            content = m.group(2)
            entities.append(
                types.MessageEntityBold(
                    offset=utf16_units(clean), length=utf16_units(content)
                )
            )
            clean += content
        else:
            content = m.group(3)
            entities.append(
                types.MessageEntityUnderline(
                    offset=utf16_units(clean), length=utf16_units(content)
                )
            )
            clean += content
        last = m.end()

    clean += raw[last:]
    if unknown:
        print(f"ПРЕДУПРЕЖДЕНИЕ: маркеры без записи в каталоге: {', '.join(unknown)}")
    return clean, entities


async def send_preview(text: str, args: argparse.Namespace) -> None:
    from pyrogram import Client
    import pyrogram.raw.functions.messages as functions

    catalog = load_catalog(args.catalog)
    clean, entities = build_entities(text, catalog)

    print("─── Текст превью " + "─" * 33)
    print(clean)
    print("─" * 50)
    print(f"Entities: {len(entities)} шт. → {args.chat}")

    async with Client(
        args.session,
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    ) as app:
        peer = await app.resolve_peer(args.chat)
        await app.invoke(
            functions.SendMessage(
                peer=peer,
                message=clean,
                entities=entities or None,
                random_id=app.rnd_id(),
                no_webpage=True,
            )
        )
    print(f"ГОТОВО: превью в {args.chat}. Проверь рендер и пересылай в канал вручную.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("draft", type=Path, help="файл поста с маркерами [EMOJI:name]")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--session", default=DEFAULT_SESSION, help="путь Pyrogram-сессии")
    parser.add_argument(
        "--chat", default=os.getenv("EMOJI_PREVIEW_CHAT", "me"),
        help="превью-чат; по умолчанию «Избранное» (me)",
    )
    args = parser.parse_args()

    for var in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH"):
        if not os.getenv(var):
            print(f"ОШИБКА: переменная {var} пуста (my.telegram.org)", file=sys.stderr)
            return 2
    if not args.draft.is_file():
        print(f"ОШИБКА: файл не найден: {args.draft}", file=sys.stderr)
        return 2

    text = args.draft.read_text(encoding="utf-8").strip()
    if not text:
        print("ОШИБКА: пустой черновик", file=sys.stderr)
        return 2
    asyncio.run(send_preview(text, args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
