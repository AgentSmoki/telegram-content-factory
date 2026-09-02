#!/usr/bin/env python3
"""Одобрение поста кнопкой прямо в Telegram.

Схема: превью падает автору в личку с бота вместе с кнопками
«✅ Опубликовать» / «✖ Отмена». Автор жмёт галочку — бот публикует
пост в канал. Никакого терминала в момент решения: кнопка и есть отмашка.

Защита:
- на кнопку реагирует только TELEGRAM_APPROVER_ID (чужие нажатия отбиваются);
- у кнопок одноразовый код (nonce) — старые кнопки от прошлых прогонов мертвы;
- адресат публикации подтверждается флагом --confirm-target, как везде;
- по таймауту пост НЕ публикуется.

Использование:
    # rich-статья с фото
    python3 approve_send.py --rich post-rich.html --photo cover=cover.png \
        --publish-to production --confirm-target=@channel

    # обычный пост с URL-кнопкой
    python3 approve_send.py --plain post.html --parse-mode HTML \
        --url-button "Скачать|https://…" --publish-to production --confirm-target=@channel
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
import time
from pathlib import Path

from validate_rich import validate
from publish_rich import ROOT, TARGET_VARS, as_input_media, media_arg


def cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--rich", type=Path, help="файл Rich HTML")
    src.add_argument("--plain", type=Path, help="файл обычного поста")
    parser.add_argument("--photo", action="append", default=[], type=media_arg("photo"))
    parser.add_argument("--video", action="append", default=[], type=media_arg("video"))
    parser.add_argument("--parse-mode", choices=("HTML", "MarkdownV2", "none"), default="none")
    parser.add_argument(
        "--url-button", action="append", default=[], metavar="ТЕКСТ|URL",
        help="URL-кнопка под plain-постом; повторяемый флаг",
    )
    parser.add_argument(
        "--publish-to", choices=tuple(TARGET_VARS), default="production",
        help="куда уйдёт пост после ✅; по умолчанию production",
    )
    parser.add_argument("--confirm-target", required=True,
                        help="обязан посимвольно совпасть с настроенным адресатом")
    parser.add_argument("--timeout", type=int, default=3600,
                        help="секунд ждать нажатия; после — отбой (по умолчанию час)")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    return parser


def env_value(name: str, env_file: Path) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ValueError(f"{name} пуст в {env_file}")
    return value


async def run(args: argparse.Namespace) -> int:
    from aiogram import Bot
    from aiogram.types import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        InputRichMessage,
        InputRichMessageMedia,
    )
    from dotenv import load_dotenv

    if not args.env_file.is_file():
        raise ValueError(f".env не найден: {args.env_file}")
    load_dotenv(args.env_file, override=True)

    token = env_value("TELEGRAM_BOT_TOKEN", args.env_file)
    approver = env_value("TELEGRAM_APPROVER_ID", args.env_file)
    preview_chat = env_value("TELEGRAM_TEST_CHAT_ID", args.env_file)
    target = env_value(TARGET_VARS[args.publish_to], args.env_file)
    if args.confirm_target != target:
        raise ValueError(
            f"--confirm-target обязан посимвольно совпасть с {TARGET_VARS[args.publish_to]}"
        )

    media = [*args.photo, *args.video]
    source = args.rich or args.plain
    text = source.read_text(encoding="utf-8").strip()

    url_kb = None
    if args.url_button:
        rows = []
        for item in args.url_button:
            label, sep, url = item.partition("|")
            if not sep or not url.startswith(("http://", "https://", "tg://")):
                raise ValueError(f"кнопка задаётся как ТЕКСТ|URL: {item!r}")
            rows.append([InlineKeyboardButton(text=label.strip(), url=url.strip())])
        url_kb = InlineKeyboardMarkup(inline_keyboard=rows)

    if args.rich:
        report = validate(text, media)
        if not report.ok:
            for error in report.errors:
                print(f"ОШИБКА: {error}", file=sys.stderr)
            return 1
        print(f"ВАЛИДНО: {report.chars} симв., {report.blocks} блоков, медиа {report.media}.")

    def build_rich() -> "InputRichMessage":
        return InputRichMessage(
            html=text,
            media=[
                InputRichMessageMedia(id=item.mid, media=as_input_media(item))
                for item in media
            ],
        )

    parse_mode = None if args.parse_mode == "none" else args.parse_mode
    nonce = secrets.token_hex(4)
    bot = Bot(token)
    try:
        # Пропускаем накопленные апдейты: старые нажатия не считаются.
        pending = await bot.get_updates(offset=-1, timeout=0)
        offset = pending[-1].update_id + 1 if pending else None

        if args.rich:
            await bot.send_rich_message(preview_chat, build_rich())
        else:
            await bot.send_message(preview_chat, text, parse_mode=parse_mode, reply_markup=url_kb)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"pub:{nonce}"),
                InlineKeyboardButton(text="✖ Отмена", callback_data=f"no:{nonce}"),
            ]]
        )
        ctrl = await bot.send_message(
            preview_chat,
            f"Выше — превью. Опубликовать в {target}?",
            reply_markup=kb,
        )
        print(f"ЖДУ РЕШЕНИЯ: превью и кнопки у {preview_chat}, таймаут {args.timeout}с.")

        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            updates = await bot.get_updates(
                offset=offset, timeout=25,
                allowed_updates=["callback_query", "message"],
            )
            for update in updates:
                offset = update.update_id + 1
                cq = update.callback_query
                if not cq or not cq.data or not cq.data.endswith(f":{nonce}"):
                    continue
                if str(cq.from_user.id) != approver:
                    await bot.answer_callback_query(cq.id, "Эта кнопка не для тебя)")
                    continue
                if cq.data.startswith("pub:"):
                    if args.rich:
                        message = await bot.send_rich_message(target, build_rich())
                    else:
                        message = await bot.send_message(
                            target, text, parse_mode=parse_mode, reply_markup=url_kb
                        )
                    await bot.answer_callback_query(cq.id, "Улетело в канал")
                    await bot.edit_message_text(
                        f"✅ Опубликовано: {target} (message_id={message.message_id})",
                        chat_id=ctrl.chat.id, message_id=ctrl.message_id,
                    )
                    print(
                        f"ОПУБЛИКОВАНО КНОПКОЙ: chat={message.chat.id} "
                        f"message_id={message.message_id}"
                    )
                    return 0
                await bot.answer_callback_query(cq.id, "Отменено")
                await bot.edit_message_text(
                    "✖ Отменено. Пост никуда не ушёл.",
                    chat_id=ctrl.chat.id, message_id=ctrl.message_id,
                )
                print("ОТМЕНЕНО КНОПКОЙ. Ничего не опубликовано.")
                return 3

        await bot.edit_message_text(
            "⏰ Время вышло. Пост не опубликован.",
            chat_id=ctrl.chat.id, message_id=ctrl.message_id,
        )
        print("ТАЙМАУТ: решение не принято, ничего не опубликовано.")
        return 2
    finally:
        await bot.session.close()


def main() -> int:
    args = cli().parse_args()
    source = args.rich or args.plain
    if not source.is_file():
        print(f"ОШИБКА: файл не найден: {source}", file=sys.stderr)
        return 2
    try:
        return asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001 — граница CLI
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
