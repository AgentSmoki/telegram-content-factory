#!/usr/bin/env python3
"""Детерминированный стилевой гейт для русских текстов.

Ловит то, что проверяется правилом, а не вкусом: штампы, канцелярит,
типовые AI-конструкции, оценочные усилители без факта, структурные
лимиты (длина предложений и абзацев, количество эмодзи).

Это НЕ «оценка голоса» и не замена редактуры — только объяснимые
правила с указанием, что именно сработало. Финальное слово за автором.

Использование:
    python3 check_style.py post-plain.md
    python3 check_style.py post-plain.md --profile style-check.json --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

RE_EMOJI = re.compile("[\U0001f1e6-\U0001f1ff\U0001f300-\U0001faff☀-➿]")
RE_SENTENCE = re.compile(r"[^.!?…]+[.!?…]?")
RE_WORD = re.compile(r"\b[\w'-]+\b", re.UNICODE)

# --- Встроенные словари (расширяются profile-файлом) -----------------------

CLICHES = [
    "в современном мире",
    "не секрет, что",
    "ни для кого не секрет",
    "как известно",
    "уникальная возможность",
    "широкий спектр",
    "индивидуальный подход",
    "команда профессионалов",
    "залог успеха",
    "по ту сторону",
    "лучшие практики",
    "качественно и в срок",
    "динамично развивающаяся",
]

BUREAUCRAT = [
    "осуществлять",
    "осуществление",
    "является",
    "данный",
    "вышеуказанный",
    "во избежание",
    "касательно",
    "в рамках",
    "с целью",
    "в связи с тем",
    "по причине того",
    "имеет место",
    "производить работы",
    "оказывать содействие",
]

AI_SLOP = [
    "важно отметить",
    "стоит отметить",
    "следует отметить",
    "важно понимать",
    "давайте разберемся",
    "давайте разберёмся",
    "давайте рассмотрим",
    "погрузимся в",
    "недавно понял",
    "в заключение",
    "подводя итог",
    "подведем итоги",
    "мир не будет прежним",
    "разберем по полочкам",
    "разберём по полочкам",
    "но и это еще не все",
    "но и это ещё не всё",
    "это меняет всё",
    "спойлер:",
]

EVALUATIVE = [
    "невероятно",
    "потрясающе",
    "впечатляюще",
    "революционный",
    "инновационный",
    "уникальный",
    "эффективный",
    "качественный",
    "передовой",
    "беспрецедентный",
]

DEFAULTS: dict[str, object] = {
    "max_sentence_words": 20,
    "max_paragraph_chars": 500,
    "max_emoji": 2,
    "forbid_exclamation": True,
    "forbid_hash": True,
    "banned_phrases": [],
    "required_phrases": [],
    "extra_cliches": [],
    "allow_words": [],
    "ignore_quoted": True,
}

RE_QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"")


@dataclass
class Finding:
    level: str  # FAIL | WARN
    rule: str
    detail: str

    def as_dict(self) -> dict:
        return {"level": self.level, "rule": self.rule, "detail": self.detail}


def _find_phrases(
    text_low: str, phrases: list[str], rule: str, level: str, allow: set[str]
) -> list[Finding]:
    found = []
    for phrase in phrases:
        p = phrase.casefold()
        if p in allow:
            continue
        if p in text_low:
            found.append(Finding(level, rule, repr(phrase)))
    return found


def check(text: str, config: dict[str, object]) -> list[Finding]:
    cfg = {**DEFAULTS, **config}
    allow = {str(w).casefold() for w in cfg.get("allow_words", [])}
    low = text.casefold()
    # Цитата штампа в «кавычках» — пример, а не штамп: словари её пропускают.
    scan = RE_QUOTED.sub(" ", low) if cfg.get("ignore_quoted") else low
    findings: list[Finding] = []

    # Словари: штампы и канцелярит — FAIL, AI-slop — FAIL, оценочные — WARN.
    cliches = CLICHES + [str(p) for p in cfg.get("extra_cliches", [])]
    findings += _find_phrases(scan, cliches, "cliche", "FAIL", allow)
    findings += _find_phrases(scan, BUREAUCRAT, "bureaucrat", "FAIL", allow)
    findings += _find_phrases(scan, AI_SLOP, "ai_slop", "FAIL", allow)
    findings += _find_phrases(scan, EVALUATIVE, "evaluative", "WARN", allow)

    for phrase in cfg.get("banned_phrases", []):
        if str(phrase).casefold() in scan:
            findings.append(Finding("FAIL", "banned_phrase", repr(str(phrase))))
    for phrase in cfg.get("required_phrases", []):
        if str(phrase).casefold() not in low:
            findings.append(Finding("FAIL", "required_phrase", f"нет {phrase!r}"))

    if cfg.get("forbid_exclamation") and "!" in text:
        count = text.count("!")
        findings.append(Finding("FAIL", "exclamation", f"{count} шт. «!» — замени на «)»"))
    if cfg.get("forbid_hash") and re.search(r"(^|\s)#\w", text):
        findings.append(Finding("FAIL", "hash", "решётка в тексте поста"))

    max_words = int(cfg.get("max_sentence_words") or 0)
    if max_words:
        for i, sentence in enumerate(RE_SENTENCE.findall(text), start=1):
            words = RE_WORD.findall(sentence)
            if len(words) > max_words:
                findings.append(
                    Finding(
                        "WARN",
                        "sentence_length",
                        f"предложение {i}: {len(words)} слов > {max_words}",
                    )
                )

    max_par = int(cfg.get("max_paragraph_chars") or 0)
    if max_par:
        for i, par in enumerate(re.split(r"\n\s*\n", text), start=1):
            if len(par.strip()) > max_par:
                findings.append(
                    Finding(
                        "WARN",
                        "paragraph_length",
                        f"абзац {i}: {len(par.strip())} симв. > {max_par}",
                    )
                )

    max_emoji = int(cfg.get("max_emoji") or 0)
    if max_emoji:
        n = len(RE_EMOJI.findall(text))
        if n > max_emoji:
            findings.append(Finding("WARN", "emoji_count", f"{n} эмодзи > {max_emoji}"))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("text", type=Path, help="файл с текстом поста")
    parser.add_argument("--profile", type=Path, help="JSON с правилами проекта")
    parser.add_argument("--json", action="store_true", help="отчёт в JSON")
    args = parser.parse_args()

    if not args.text.is_file():
        print(f"ОШИБКА: файл не найден: {args.text}", file=sys.stderr)
        return 2
    config: dict[str, object] = {}
    if args.profile:
        try:
            config = json.loads(args.profile.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ОШИБКА: профиль не читается: {exc}", file=sys.stderr)
            return 2

    findings = check(args.text.read_text(encoding="utf-8"), config)
    if args.json:
        print(json.dumps([f.as_dict() for f in findings], ensure_ascii=False, indent=2))
    elif findings:
        for f in findings:
            print(f"{f.level}: {f.rule}: {f.detail}")
    else:
        print("ПРОЙДЕНО: ни одно правило не сработало")
    print("Справка: это проверка правил, а не «оценка качества текста».")
    return 1 if any(f.level == "FAIL" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
