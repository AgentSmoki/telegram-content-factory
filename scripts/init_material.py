#!/usr/bin/env python3
"""Создаёт рабочую папку материала: один пост = один проверяемый пакет.

Использование:
    python3 init_material.py "интервью про запуск"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = {
    "source.md": (
        "# Источник\n\n- Тип (мысль/голосовое/статья/видео):\n- Ссылка или файл:\n"
        "- Права на использование:\n- Дата получения:\n\n## Сырьё\n\n"
    ),
    "transcript.md": "# Транскрипт\n\n_Расшифровка через TeleTranscribe MCP; спикеры и таймкоды._\n\n",
    "evidence-map.md": (
        "# Карта фактов\n\n| Утверждение | Источник | Уверенность |\n|---|---|---|\n| | | |\n"
    ),
    "brief.md": (
        "# Бриф\n\n- Аудитория:\n- Цель (прогрев/продажа/экспертка/мысль):\n"
        "- Тип поста (история/инсайты/шаги):\n- Действие читателя:\n- Обязательные ссылки:\n"
    ),
    "hooks.md": "# Батарея хуков\n\n_5–10 вариантов первой строки, отбор перед черновиком._\n\n",
    "post-plain.md": "",
    "post-rich.html": "",
    "validation-report.md": (
        "# Отчёт приёмки\n\n- [ ] validate_rich.py без ошибок\n- [ ] check_style.py без FAIL\n"
        "- [ ] три прохода редактуры выполнены\n- [ ] превью проверено на desktop и mobile\n"
        "- [ ] факты сверены с картой\n- [ ] публикация одобрена автором\n"
    ),
}


def slug(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", value.lower(), flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", cleaned).strip("-") or "material"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="человеческое имя материала")
    parser.add_argument("--root", type=Path, default=ROOT / "materials")
    args = parser.parse_args()

    folder = args.root / slug(args.name)
    if folder.exists():
        print(f"ОШИБКА: папка уже существует: {folder}", file=sys.stderr)
        return 1
    (folder / "media").mkdir(parents=True)
    for filename, content in FILES.items():
        (folder / filename).write_text(content, encoding="utf-8")
    print(f"СОЗДАНО: {folder}")
    for filename in [*FILES, "media/"]:
        print(f"  - {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
