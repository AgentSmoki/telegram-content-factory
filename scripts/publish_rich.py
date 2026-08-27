#!/usr/bin/env python3
"""Публикация Telegram Rich Message с сухим прогоном по умолчанию.

Без флагов скрипт только валидирует разметку и медиа — сеть не трогается.
Реальная отправка требует двух независимых подтверждений:
`--send` И `--confirm-target`, посимвольно совпадающий с chat_id из .env.

Использование:
    python3 publish_rich.py post-rich.html --photo cover=cover.jpg
    python3 publish_rich.py post-rich.html --photo cover=cover.jpg \
        --send --confirm-target=-1001234567890
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from validate_rich import Media, parse_media_arg, validate

ROOT = Path(__file__).resolve().parent.parent
TARGET_VARS = {
    "test": "TELEGRAM_TEST_CHAT_ID",
    "production": "TELEGRAM_PROD_CHAT_ID",
}


def media_arg(kind: str):
    return lambda value: parse_media_arg(value, kind=kind)


def cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("markup", type=Path, help="файл Rich HTML в UTF-8")
    parser.add_argument("--photo", action="append", default=[], type=media_arg("photo"))
    parser.add_argument("--video", action="append", default=[], type=media_arg("video"))
    parser.add_argument("--audio", action="append", default=[], type=media_arg("audio"))
    parser.add_argument(
        "--document", action="append", default=[], type=media_arg("document")
    )
    parser.add_argument(
        "--environment", choices=tuple(TARGET_VARS), default="test",
        help="какой chat_id взять из .env; по умолчанию test",
    )
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--send", action="store_true", help="выполнить отправку")
    parser.add_argument(
        "--confirm-target",
        help="обязан посимвольно совпасть с настроенным chat_id при --send",
    )
    return parser


def resolve_env(args: argparse.Namespace) -> tuple[str, str]:
    """Возвращает (token, chat_id) после всех проверок безопасности."""
    from dotenv import load_dotenv

    if not args.env_file.is_file():
        raise ValueError(f".env не найден: {args.env_file}")
    load_dotenv(args.env_file, override=True)

    var = TARGET_VARS[args.environment]
    chat_id = (os.getenv(var) or "").strip()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not chat_id:
        raise ValueError(f"{var} пуст в {args.env_file}")
    if not token:
        raise ValueError(f"TELEGRAM_BOT_TOKEN пуст в {args.env_file}")
    if args.confirm_target != chat_id:
        raise ValueError(
            f"--confirm-target обязан посимвольно совпасть с {var}; "
            "проверь адресата и повтори"
        )
    return token, chat_id


def as_input_media(item: Media):
    from aiogram.types import (
        FSInputFile,
        InputMediaAudio,
        InputMediaDocument,
        InputMediaPhoto,
        InputMediaVideo,
    )

    kinds = {
        "photo": InputMediaPhoto,
        "video": InputMediaVideo,
        "audio": InputMediaAudio,
        "document": InputMediaDocument,
    }
    source = item.source
    if not source.startswith(("http://", "https://")):
        source = FSInputFile(Path(source).expanduser())
    return kinds[item.kind](media=source)


async def deliver(args: argparse.Namespace, markup: str, media: list[Media]) -> None:
    from aiogram import Bot
    from aiogram.types import InputRichMessage, InputRichMessageMedia

    token, chat_id = resolve_env(args)
    rich = InputRichMessage(
        html=markup,
        media=[
            InputRichMessageMedia(id=item.mid, media=as_input_media(item))
            for item in media
        ],
    )
    bot = Bot(token)
    try:
        message = await bot.send_rich_message(chat_id, rich)
        print(
            f"ОТПРАВЛЕНО: environment={args.environment} "
            f"chat={message.chat.id} message_id={message.message_id}"
        )
    finally:
        await bot.session.close()


def main() -> int:
    args = cli().parse_args()
    if not args.markup.is_file():
        print(f"ОШИБКА: файл не найден: {args.markup}", file=sys.stderr)
        return 2
    markup = args.markup.read_text(encoding="utf-8").strip()
    media = [*args.photo, *args.video, *args.audio, *args.document]

    report = validate(markup, media)
    for warning in report.warnings:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {warning}")
    if not report.ok:
        for error in report.errors:
            print(f"ОШИБКА: {error}", file=sys.stderr)
        return 1
    print(f"ВАЛИДНО: {report.chars} симв., {report.blocks} блоков, медиа {report.media}.")

    if not args.send:
        print("Сухой прогон. Для отправки добавь --send и точный --confirm-target.")
        return 0
    try:
        asyncio.run(deliver(args, markup, media))
    except Exception as exc:  # noqa: BLE001 — граница CLI, наружу уходит чистая ошибка
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
