#!/usr/bin/env python3
"""Fallback-публикация: обычный пост или классический альбом 2–10 медиа.

Для аудиторий со старыми клиентами Telegram, где Rich Message показывается
как «неподдерживаемое сообщение». Сухой прогон по умолчанию; отправка —
только с --send и точным --confirm-target (та же схема, что publish_rich).

Использование:
    python3 publish_fallback.py post-plain.md --mode plain
    python3 publish_fallback.py caption.txt --mode album \
        --photo p1=1.jpg --photo p2=2.jpg --send --confirm-target=-100123
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from publish_rich import ROOT, as_input_media, media_arg, resolve_env

PLAIN_LIMIT = 4096
CAPTION_LIMIT = 1024
ALBUM_MIN, ALBUM_MAX = 2, 10


def cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("text", type=Path, help="файл текста или подписи, UTF-8")
    parser.add_argument("--mode", choices=("plain", "album"), default="plain")
    parser.add_argument("--photo", action="append", default=[], type=media_arg("photo"))
    parser.add_argument("--video", action="append", default=[], type=media_arg("video"))
    parser.add_argument(
        "--parse-mode", choices=("HTML", "MarkdownV2", "none"), default="none"
    )
    parser.add_argument("--environment", choices=("test", "production"), default="test")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--confirm-target")
    return parser


def precheck(args: argparse.Namespace, text: str) -> list[str]:
    errors = []
    media = [*args.photo, *args.video]
    if args.mode == "plain":
        if media:
            errors.append("режим plain отправляется без медиа — используй album")
        if len(text) > PLAIN_LIMIT:
            errors.append(f"{len(text)} симв. — лимит обычного поста {PLAIN_LIMIT}")
    else:
        if not ALBUM_MIN <= len(media) <= ALBUM_MAX:
            errors.append(f"альбом требует {ALBUM_MIN}–{ALBUM_MAX} медиа")
        if len(text) > CAPTION_LIMIT:
            errors.append(f"{len(text)} симв. — лимит подписи альбома {CAPTION_LIMIT}")
    return errors


async def deliver(args: argparse.Namespace, text: str) -> None:
    from aiogram import Bot

    token, chat_id = resolve_env(args)
    parse_mode = None if args.parse_mode == "none" else args.parse_mode
    media = [*args.photo, *args.video]

    bot = Bot(token)
    try:
        if args.mode == "plain":
            message = await bot.send_message(chat_id, text, parse_mode=parse_mode)
            print(f"ОТПРАВЛЕНО: chat={message.chat.id} message_id={message.message_id}")
        else:
            group = [as_input_media(item) for item in media]
            group[0].caption = text
            group[0].parse_mode = parse_mode
            messages = await bot.send_media_group(chat_id, group)
            print(f"ОТПРАВЛЕНО: альбом из {len(messages)} сообщений в chat={chat_id}")
    finally:
        await bot.session.close()


def main() -> int:
    args = cli().parse_args()
    if not args.text.is_file():
        print(f"ОШИБКА: файл не найден: {args.text}", file=sys.stderr)
        return 2
    text = args.text.read_text(encoding="utf-8").strip()

    errors = precheck(args, text)
    if errors:
        for error in errors:
            print(f"ОШИБКА: {error}", file=sys.stderr)
        return 1
    print(f"ВАЛИДНО: режим {args.mode}, {len(text)} симв.")

    if not args.send:
        print("Сухой прогон. Для отправки добавь --send и точный --confirm-target.")
        return 0
    try:
        asyncio.run(deliver(args, text))
    except Exception as exc:  # noqa: BLE001 — граница CLI
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
