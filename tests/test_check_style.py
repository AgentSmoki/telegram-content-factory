"""Офлайн-тесты стилевого гейта: python3 -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_style import check  # noqa: E402


def rules(findings, level=None):
    return [f.rule for f in findings if level is None or f.level == level]


class TestDictionaries(unittest.TestCase):
    def test_cliche_fails(self):
        findings = check("В современном мире все пишут посты.", {})
        self.assertIn("cliche", rules(findings, "FAIL"))

    def test_ai_slop_fails(self):
        findings = check("Важно отметить, что бот работает.", {})
        self.assertIn("ai_slop", rules(findings, "FAIL"))

    def test_bureaucrat_fails(self):
        findings = check("Данный сервис является лидером.", {})
        self.assertIn("bureaucrat", rules(findings, "FAIL"))

    def test_evaluative_warns(self):
        findings = check("Невероятно быстрый запуск.", {})
        self.assertIn("evaluative", rules(findings, "WARN"))

    def test_clean_text_passes(self):
        findings = check("Запустил бота за вечер. Отвечает за 2 секунды)", {})
        self.assertEqual(rules(findings, "FAIL"), [])

    def test_quoted_example_is_ignored(self):
        text = "Фразу «важно отметить» гейт ловит сразу."
        self.assertNotIn("ai_slop", rules(check(text, {})))
        self.assertIn("ai_slop", rules(check(text, {"ignore_quoted": False}), "FAIL"))

    def test_allow_words_disables_rule(self):
        cfg = {"allow_words": ["данный"]}
        findings = check("Данный кейс разберу отдельно.", cfg)
        self.assertNotIn("bureaucrat", rules(findings, "FAIL"))


class TestStructure(unittest.TestCase):
    def test_exclamation_fails_by_default(self):
        findings = check("Это сработало!", {})
        self.assertIn("exclamation", rules(findings, "FAIL"))

    def test_exclamation_can_be_allowed(self):
        findings = check("Это сработало!", {"forbid_exclamation": False})
        self.assertNotIn("exclamation", rules(findings))

    def test_hash_fails(self):
        findings = check("Пост про запуск #маркетинг", {})
        self.assertIn("hash", rules(findings, "FAIL"))

    def test_long_sentence_warns(self):
        text = "слово " * 25 + "."
        findings = check(text, {"max_sentence_words": 20})
        self.assertIn("sentence_length", rules(findings, "WARN"))

    def test_emoji_limit_warns(self):
        findings = check("🔥🔥🔥 запуск", {"max_emoji": 2})
        self.assertIn("emoji_count", rules(findings, "WARN"))

    def test_banned_and_required_phrases(self):
        cfg = {"banned_phrases": ["синергия"], "required_phrases": ["подписывайся"]}
        findings = check("Полная синергия отделов.", cfg)
        found = rules(findings, "FAIL")
        self.assertIn("banned_phrase", found)
        self.assertIn("required_phrase", found)


if __name__ == "__main__":
    unittest.main()
