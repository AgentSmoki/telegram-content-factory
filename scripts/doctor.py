#!/usr/bin/env python3
"""Диагностика установки. По умолчанию работает полностью офлайн.

Проверяет интерпретатор, зависимости, .env и каталог эмодзи.
Флаг --telegram добавляет единственный сетевой вызов getMe (read-only).

Использование:
    python3 doctor.py
    python3 doctor.py --telegram
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_VARS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_TEST_CHAT_ID")
OPTIONAL_VARS = ("TELEGRAM_PROD_CHAT_ID", "TELEGRAM_API_ID", "TELEGRAM_API_HASH")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def local_checks(env_file: Path) -> list[tuple[str, str, str]]:
    checks: list[tuple[str, str, str]] = []

    ok = sys.version_info >= (3, 11)
    checks.append(
        ("python", "OK" if ok else "FAIL",
         f"{sys.version_info.major}.{sys.version_info.minor} (нужен 3.11+)")
    )
    checks.append(
        ("aiogram", "OK" if has_module("aiogram") else "WARN",
         "публикация Rich Message" if has_module("aiogram")
         else "pip install -r requirements.txt для публикации")
    )
    checks.append(
        ("dotenv", "OK" if has_module("dotenv") else "WARN",
         "чтение .env" if has_module("dotenv")
         else "pip install -r requirements.txt")
    )
    checks.append(
        ("pyrogram", "OK" if has_module("pyrogram") else "WARN",
         "превью с premium-эмодзи" if has_module("pyrogram")
         else "pip install -r requirements-emoji.txt для эмодзи-слоя")
    )

    env = read_env(env_file)
    if not env_file.is_file():
        checks.append((".env", "WARN", f"нет {env_file} — скопируй .env.example"))
    else:
        for var in REQUIRED_VARS:
            state = "OK" if env.get(var) else "WARN"
            checks.append((var, state, "задан" if env.get(var) else "пуст"))
        for var in OPTIONAL_VARS:
            checks.append((var, "OK" if env.get(var) else "INFO",
                           "задан" if env.get(var) else "опционален"))

    catalog = ROOT / "emoji-catalog.json"
    if catalog.is_file():
        try:
            data = json.loads(catalog.read_text(encoding="utf-8"))
            emoji = data.get("emoji", {})
            empty = [k for k, v in emoji.items() if not str(v.get("id", "")).isdigit()]
            state = "OK" if emoji and not empty else "WARN"
            detail = f"{len(emoji)} эмодзи" + (
                f", без id: {len(empty)} (emoji_extract.py)" if empty else ""
            )
            checks.append(("emoji-catalog", state, detail))
        except json.JSONDecodeError:
            checks.append(("emoji-catalog", "FAIL", "битый JSON"))
    else:
        checks.append(("emoji-catalog", "INFO", "нет каталога — эмодзи-слой выключен"))
    return checks


def telegram_check(env_file: Path) -> tuple[str, str, str]:
    import asyncio

    env = read_env(env_file)
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return ("getMe", "FAIL", "TELEGRAM_BOT_TOKEN пуст")

    async def _get_me() -> str:
        from aiogram import Bot

        bot = Bot(token)
        try:
            me = await bot.get_me()
            return f"@{me.username} (id={me.id})"
        finally:
            await bot.session.close()

    try:
        return ("getMe", "OK", asyncio.run(_get_me()))
    except Exception as exc:  # noqa: BLE001 — диагностика, наружу чистый текст
        return ("getMe", "FAIL", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--telegram", action="store_true",
        help="единственная сетевая проверка: getMe по токену бота",
    )
    args = parser.parse_args()

    checks = local_checks(args.env_file)
    if args.telegram:
        checks.append(telegram_check(args.env_file))

    failed = False
    for name, state, detail in checks:
        print(f"[{state:4}] {name}: {detail}")
        failed = failed or state == "FAIL"
    print("Итог: есть FAIL — почини и повтори" if failed else "Итог: готово к работе")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
