#!/usr/bin/env python3
"""Офлайн-валидатор Telegram Rich HTML.

Проверяет разметку и объявленные медиа по правилам Bot API 10.3
до любого сетевого действия. Сеть не используется вообще.

Использование:
    python3 validate_rich.py post-rich.html
    python3 validate_rich.py post-rich.html --media cover=cover.jpg --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

# Лимиты Bot API 10.3 (core.telegram.org/bots/api)
LIMIT_TEXT_CHARS = 32_768
LIMIT_BLOCKS = 500
LIMIT_NESTING = 16
LIMIT_MEDIA = 50
LIMIT_TABLE_COLS = 20

RE_MEDIA_REF = re.compile(
    r"tg://(?P<kind>photo|video|audio|document)\?id=(?P<mid>[A-Za-z0-9_-]{1,64})"
)
RE_MEDIA_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
RE_NAMED_ENTITY = re.compile(r"&([A-Za-z][A-Za-z0-9]{1,31});")

# Именованные HTML-сущности, которые Telegram документирует как поддерживаемые.
NAMED_ENTITIES = frozenset(
    "lt gt amp quot apos nbsp hellip mdash ndash lsquo rsquo ldquo rdquo".split()
)

# Разрешённые схемы URL в href/src/url.
URL_SCHEMES = frozenset({"http", "https", "mailto", "tg"})

# Allowlist тегов Rich HTML (Bot API 10.3). Явный список надёжнее «принять всё»:
# незнакомый тег сервер отклонит либо молча отбросит.
TAGS = frozenset(
    """a aside audio b blockquote br caption cite code del details em
    figcaption figure footer h1 h2 h3 h4 h5 h6 hr i img input ins li mark
    ol p pre s strike strong sub summary sup table td tg-button
    tg-button-row tg-collage tg-document tg-emoji tg-map tg-math
    tg-math-block tg-reference tg-slideshow tg-spoiler tg-thinking tg-time
    th tr u ul video""".split()
)

# Теги, допустимые только в черновике (Telegram их не принимает).
DRAFT_TAGS = frozenset({"tg-thinking"})

# Разрешённые атрибуты по тегам. Всё остальное — ошибка.
ATTRS: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "name"}),
    "audio": frozenset({"src", "tg-spoiler"}),
    "blockquote": frozenset({"expandable"}),
    "code": frozenset({"class"}),
    "details": frozenset({"open"}),
    "img": frozenset({"src", "alt", "tg-spoiler"}),
    "input": frozenset({"type", "checked"}),
    "li": frozenset({"value"}),
    "ol": frozenset({"start", "type", "reversed"}),
    "table": frozenset({"bordered", "striped", "compact"}),
    "td": frozenset({"colspan", "rowspan", "align", "valign"}),
    "th": frozenset({"colspan", "rowspan", "align", "valign"}),
    "tg-button": frozenset(
        {
            "type", "style", "url", "data", "forward-text", "query", "text",
            "request-write-access", "allow-user-chats", "allow-bot-chats",
            "allow-group-chats", "allow-channel-chats",
        }
    ),
    "tg-button-row": frozenset({"align"}),
    "tg-document": frozenset({"src", "tg-spoiler"}),
    "tg-emoji": frozenset({"emoji-id"}),
    "tg-map": frozenset({"lat", "long", "zoom", "width", "height"}),
    "tg-reference": frozenset({"name"}),
    "tg-time": frozenset({"unix", "format"}),
    "video": frozenset({"src", "tg-spoiler"}),
}

# Теги, которые считаются блоками при подсчёте лимита в 500 блоков.
BLOCK_LEVEL = frozenset(
    """h1 h2 h3 h4 h5 h6 p pre footer hr ul ol li blockquote aside table
    caption tr details tg-math-block tg-map tg-collage tg-slideshow
    tg-document img video audio""".split()
)

# Пустые (void) теги — без закрывающей пары.
VOID = frozenset({"br", "hr", "img", "input", "tg-map"})


@dataclass(frozen=True)
class Media:
    """Одно объявленное медиа: ID + локальный путь или https-URL."""

    mid: str
    source: str
    kind: str | None = None


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    chars: int = 0
    blocks: int = 0
    nesting: int = 0
    media: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "chars": self.chars,
            "blocks": self.blocks,
            "nesting": self.nesting,
            "media": self.media,
        }


class _Scanner(HTMLParser):
    """Один проход по разметке: теги, атрибуты, вложенность, таблицы."""

    def __init__(self, *, draft: bool = False) -> None:
        super().__init__(convert_charrefs=False)
        self.draft = draft
        self.errors: list[str] = []
        self.open_tags: list[str] = []
        self.blocks = 0
        self.deepest = 0
        self.row_cols: int | None = None
        self.widest_row = 0

    # --- проверки одного тега -------------------------------------------

    def _check_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        allowed = ATTRS.get(tag, frozenset())
        met: set[str] = set()
        for raw, value in attrs:
            name = raw.lower()
            if name in met:
                self.errors.append(f"атрибут {name!r} повторяется в <{tag}>")
            met.add(name)
            if name.startswith("on"):
                self.errors.append(f"обработчик событий {name!r} в <{tag}> запрещён")
                continue
            if name == "style" and tag != "tg-button":
                self.errors.append(f"inline-стиль в <{tag}> запрещён")
                continue
            if name not in allowed:
                self.errors.append(f"атрибут {name!r} не поддерживается в <{tag}>")
            if name in {"href", "src", "url"} and value:
                if name == "href" and value.startswith("#"):
                    continue  # внутренний якорь
                scheme = urlparse(value).scheme.lower()
                if scheme not in URL_SCHEMES:
                    self.errors.append(
                        f"схема URL {scheme or '(пусто)'!r} в {name!r} <{tag}> запрещена"
                    )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in TAGS:
            self.errors.append(f"тег <{tag}> не входит в Rich HTML Bot API 10.3")
        elif tag in DRAFT_TAGS and not self.draft:
            self.errors.append(f"черновой тег <{tag}> доступен только с --draft")
        self._check_attrs(tag, attrs)

        if tag in BLOCK_LEVEL:
            self.blocks += 1
        if tag == "tr":
            self.row_cols = 0
        elif tag in {"td", "th"} and self.row_cols is not None:
            raw_span = dict(attrs).get("colspan") or "1"
            try:
                span = max(1, int(raw_span))
            except ValueError:
                self.errors.append(f"colspan={raw_span!r} — ожидается целое число")
                span = 1
            self.row_cols += span
            self.widest_row = max(self.widest_row, self.row_cols)

        if tag not in VOID:
            self.open_tags.append(tag)
            self.deepest = max(self.deepest, len(self.open_tags))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        low = tag.lower()
        if low not in VOID and self.open_tags and self.open_tags[-1] == low:
            self.open_tags.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "tr":
            self.row_cols = None
        if not self.open_tags:
            self.errors.append(f"закрывающий </{tag}> без открывающего")
            return
        if self.open_tags[-1] == tag:
            self.open_tags.pop()
            return
        self.errors.append(
            f"</{tag}> закрывает не тот тег: открыт <{self.open_tags[-1]}>"
        )
        if tag in self.open_tags:
            while self.open_tags and self.open_tags[-1] != tag:
                self.open_tags.pop()
            if self.open_tags:
                self.open_tags.pop()

    def finish(self) -> None:
        self.close()
        if self.open_tags:
            self.errors.append("незакрытые теги: " + ", ".join(self.open_tags))


def parse_media_arg(value: str, *, kind: str | None = None) -> Media:
    """Разбирает аргумент вида ID=путь_или_URL."""
    mid, sep, source = value.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError("медиа задаётся как ID=ПУТЬ_ИЛИ_URL")
    if not RE_MEDIA_ID.match(mid):
        raise argparse.ArgumentTypeError("ID медиа: [A-Za-z0-9_-], 1–64 символа")
    if not source:
        raise argparse.ArgumentTypeError(f"источник медиа {mid!r} пуст")
    parsed = urlparse(source)
    is_url = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    if not is_url and not Path(source).expanduser().is_file():
        raise argparse.ArgumentTypeError(f"файл медиа не найден: {source}")
    return Media(mid=mid, source=source, kind=kind)


def validate(markup: str, media: list[Media] | None = None, *, draft: bool = False) -> Report:
    """Полная офлайн-проверка разметки и медиа-инварианта."""
    media = media or []
    report = Report(chars=len(markup), media=len(media))

    if len(markup) > LIMIT_TEXT_CHARS:
        report.errors.append(
            f"{len(markup)} символов — лимит {LIMIT_TEXT_CHARS}"
        )
    if len(media) > LIMIT_MEDIA:
        report.errors.append(f"{len(media)} медиа — лимит {LIMIT_MEDIA}")

    scanner = _Scanner(draft=draft)
    try:
        scanner.feed(markup)
        scanner.finish()
    except (AssertionError, ValueError) as exc:
        report.errors.append(f"ошибка HTML-парсера: {exc}")
    report.blocks = scanner.blocks
    report.nesting = scanner.deepest
    report.errors.extend(scanner.errors)

    if scanner.blocks > LIMIT_BLOCKS:
        report.errors.append(f"{scanner.blocks} блоков — лимит {LIMIT_BLOCKS}")
    if scanner.deepest > LIMIT_NESTING:
        report.errors.append(f"вложенность {scanner.deepest} — лимит {LIMIT_NESTING}")
    if scanner.widest_row > LIMIT_TABLE_COLS:
        report.errors.append(
            f"в строке таблицы {scanner.widest_row} колонок — лимит {LIMIT_TABLE_COLS}"
        )

    bad_entities = sorted(set(RE_NAMED_ENTITY.findall(markup)) - NAMED_ENTITIES)
    if bad_entities:
        report.errors.append(
            "неподдерживаемые именованные сущности: " + ", ".join(bad_entities)
        )

    # Медиа-инвариант: каждый tg://…?id=X ↔ ровно одно объявленное медиа X.
    refs = [(m.group("kind"), m.group("mid")) for m in RE_MEDIA_REF.finditer(markup)]
    ref_ids = {mid for _, mid in refs}
    declared = [item.mid for item in media]
    declared_set = set(declared)

    doubled = sorted({mid for mid in declared if declared.count(mid) > 1})
    if doubled:
        report.errors.append("ID медиа объявлены дважды: " + ", ".join(doubled))
    lost = sorted(ref_ids - declared_set)
    if lost:
        report.errors.append("в разметке есть, в медиа нет: " + ", ".join(lost))
    orphan = sorted(declared_set - ref_ids)
    if orphan:
        report.errors.append("объявлено, но не используется: " + ", ".join(orphan))

    want_kind = {mid: kind for kind, mid in refs}
    for item in media:
        expected = want_kind.get(item.mid)
        if item.kind and expected and item.kind != expected:
            report.errors.append(
                f"медиа {item.mid!r} объявлено как {item.kind}, "
                f"а разметка ссылается как {expected}"
            )

    if media and not refs:
        report.warnings.append("медиа объявлены, но tg://-ссылок в разметке нет")
    return report


def cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("markup", type=Path, help="файл Rich HTML в UTF-8")
    parser.add_argument(
        "--media", action="append", default=[], metavar="ID=ПУТЬ_ИЛИ_URL",
        help="объявить медиа для tg://-ссылок; повторяемый флаг",
    )
    parser.add_argument("--draft", action="store_true", help="допустить черновые теги")
    parser.add_argument("--json", action="store_true", help="отчёт в JSON")
    return parser


def main() -> int:
    args = cli().parse_args()
    if not args.markup.is_file():
        print(f"ОШИБКА: файл не найден: {args.markup}", file=sys.stderr)
        return 2
    try:
        media = [parse_media_arg(v) for v in args.media]
    except argparse.ArgumentTypeError as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 2

    report = validate(
        args.markup.read_text(encoding="utf-8").strip(), media, draft=args.draft
    )
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return 0 if report.ok else 1
    for warning in report.warnings:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {warning}")
    if not report.ok:
        for error in report.errors:
            print(f"ОШИБКА: {error}", file=sys.stderr)
        return 1
    print(
        f"ВАЛИДНО: {report.chars} симв., {report.blocks} блоков, "
        f"вложенность {report.nesting}, медиа {report.media}. Ничего не отправлено."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
