#!/usr/bin/env python3
"""Приблизительное офлайн-превью Rich HTML в браузере.

Собирает автономную HTML-страницу с базовыми стилями, чтобы быстро
итерировать структуру поста без отправки. Точный рендер даёт только
Telegram — превью служит для черновой проверки композиции.

Использование:
    python3 preview_rich.py post-rich.html --out preview.html
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RE_MEDIA = re.compile(
    r'src="tg://(?P<kind>photo|video|audio|document)\?id=(?P<mid>[A-Za-z0-9_-]{1,64})"'
)

PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Превью Rich-поста (приблизительное)</title>
<style>
  body {{ max-width: 480px; margin: 24px auto; padding: 0 16px;
         font: 16px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif;
         background: #f4f4f5; color: #111; }}
  .bubble {{ background: #fff; border-radius: 12px; padding: 14px 16px;
             box-shadow: 0 1px 2px rgba(0,0,0,.08); overflow-wrap: anywhere; }}
  .note {{ color: #777; font-size: 13px; margin-bottom: 12px; }}
  blockquote, aside {{ border-left: 3px solid #3b82f6; margin: 8px 0;
                       padding: 4px 12px; background: #f0f6ff; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 4px 8px; font-size: 14px; }}
  details {{ background: #fafafa; border-radius: 8px; padding: 6px 10px; margin: 8px 0; }}
  tg-spoiler {{ background: #111; color: #111; border-radius: 3px; }}
  tg-spoiler:hover {{ color: #fff; }}
  .media-stub {{ background: #e5e7eb; border: 1px dashed #9ca3af; border-radius: 8px;
                 padding: 22px; text-align: center; color: #555; margin: 8px 0; }}
  footer {{ color: #777; font-size: 13px; margin-top: 10px; }}
  mark {{ background: #fde68a; }}
</style></head><body>
<p class="note">Приблизительное превью. Рендер-эталон — Telegram Desktop и mobile.</p>
<div class="bubble">
{body}
</div></body></html>
"""


def render(markup: str) -> str:
    def stub(match: re.Match) -> str:
        kind, mid = match.group("kind"), match.group("mid")
        return f'src="" data-stub="{kind}:{mid}"'

    body = RE_MEDIA.sub(stub, markup)
    # Заглушки вместо медиа: превью работает без файлов.
    body = re.sub(
        r"<(img|video|audio|tg-document)([^>]*data-stub=\"(?P<label>[^\"]+)\"[^>]*)/?>",
        r'<div class="media-stub">медиа: \g<label></div>',
        body,
    )
    body = body.replace("</video>", "").replace("</audio>", "").replace("</tg-document>", "")
    return PAGE.format(body=body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("markup", type=Path, help="файл Rich HTML")
    parser.add_argument("--out", type=Path, required=True, help="куда записать превью")
    args = parser.parse_args()
    if not args.markup.is_file():
        print(f"ОШИБКА: файл не найден: {args.markup}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(args.markup.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"ПРЕВЬЮ: {args.out} — открой в браузере. Ничего не отправлено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
