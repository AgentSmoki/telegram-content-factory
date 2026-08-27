#!/usr/bin/env python3
"""Извлечение document_id кастомных эмодзи из установленных паков.

Разовый шаг настройки: userbot читает свои emoji-паки и складывает
document_id каждого эмодзи в JSON. Дальше нужные записи переносятся
в emoji-catalog.json вручную — с именем, описанием и тегами.

Использование:
    TELEGRAM_API_ID=... TELEGRAM_API_HASH=... python3 emoji_extract.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSION = str(ROOT / "userbot_session")
DEFAULT_OUT = ROOT / "emoji-extracted.json"


async def extract(session: str, out: Path) -> None:
    from pyrogram import Client
    import pyrogram.raw.functions.messages as functions
    import pyrogram.raw.types as types

    packs: dict[str, list[dict]] = {}
    async with Client(
        session,
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    ) as app:
        result = await app.invoke(functions.GetEmojiStickers(hash=0))
        for set_info in getattr(result, "sets", []):
            full = await app.invoke(
                functions.GetStickerSet(
                    stickerset=types.InputStickerSetID(
                        id=set_info.id, access_hash=set_info.access_hash
                    ),
                    hash=0,
                )
            )
            title = full.set.title
            packs[title] = []
            alt_by_doc: dict[int, str] = {}
            for pack_item in getattr(full, "packs", []):
                for doc_id in pack_item.documents:
                    alt_by_doc[doc_id] = pack_item.emoticon
            for document in getattr(full, "documents", []):
                packs[title].append(
                    {
                        "document_id": str(document.id),
                        "alt": alt_by_doc.get(document.id, ""),
                    }
                )
            print(f"Пак «{title}»: {len(packs[title])} эмодзи")

    out.write_text(
        json.dumps({"packs": packs}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"ГОТОВО: {out}")
    print("Перенеси нужные document_id в emoji-catalog.json и дай им имена/теги.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", default=DEFAULT_SESSION)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    for var in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH"):
        if not os.getenv(var):
            print(f"ОШИБКА: переменная {var} пуста (my.telegram.org)", file=sys.stderr)
            return 2
    asyncio.run(extract(args.session, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
