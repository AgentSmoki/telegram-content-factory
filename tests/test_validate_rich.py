"""Офлайн-тесты валидатора Rich HTML: python3 -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from validate_rich import Media, validate  # noqa: E402


class TestTags(unittest.TestCase):
    def test_valid_document_passes(self):
        markup = (
            "<h1>Заголовок</h1><p>Текст с <b>жирным</b> и "
            '<a href="https://example.com">ссылкой</a>.</p>'
            "<details><summary>Ещё</summary><p>Внутри.</p></details>"
        )
        report = validate(markup)
        self.assertEqual(report.errors, [])
        self.assertTrue(report.ok)

    def test_unknown_tag_fails(self):
        report = validate("<div>браузерный HTML</div>")
        self.assertTrue(any("<div>" in e for e in report.errors))

    def test_draft_tag_needs_flag(self):
        markup = "<tg-thinking>черновик</tg-thinking>"
        self.assertFalse(validate(markup).ok)
        self.assertTrue(validate(markup, draft=True).ok)

    def test_unclosed_tag_fails(self):
        report = validate("<p>абзац без закрытия")
        self.assertTrue(any("незакрытые" in e for e in report.errors))

    def test_mismatched_close_fails(self):
        report = validate("<p><b>текст</p></b>")
        self.assertFalse(report.ok)


class TestAttributes(unittest.TestCase):
    def test_event_handler_fails(self):
        report = validate('<p><a href="https://x.io" onclick="hack()">x</a></p>')
        self.assertTrue(any("обработчик" in e for e in report.errors))

    def test_inline_style_fails(self):
        report = validate('<p style="color:red">x</p>')
        self.assertTrue(any("inline-стиль" in e for e in report.errors))

    def test_javascript_url_fails(self):
        report = validate('<p><a href="javascript:alert(1)">x</a></p>')
        self.assertTrue(any("схема URL" in e for e in report.errors))

    def test_internal_anchor_passes(self):
        report = validate('<p><a href="#note-1">[1]</a></p>')
        self.assertTrue(report.ok)


class TestLimits(unittest.TestCase):
    def test_table_columns_limit(self):
        cells = "".join(f"<td>{i}</td>" for i in range(21))
        report = validate(f"<table><tr>{cells}</tr></table>")
        self.assertTrue(any("колонок" in e for e in report.errors))

    def test_colspan_counts(self):
        report = validate('<table><tr><td colspan="21">x</td></tr></table>')
        self.assertTrue(any("колонок" in e for e in report.errors))

    def test_named_entities(self):
        self.assertTrue(validate("<p>&mdash; и &nbsp;</p>").ok)
        report = validate("<p>&copy;</p>")
        self.assertTrue(any("сущности" in e for e in report.errors))


class TestMediaInvariant(unittest.TestCase):
    def test_referenced_but_undeclared(self):
        report = validate('<img src="tg://photo?id=cover"/>')
        self.assertTrue(any("в медиа нет" in e for e in report.errors))

    def test_declared_but_unused(self):
        report = validate("<p>без медиа</p>", [Media("cover", "https://x.io/a.jpg")])
        self.assertTrue(any("не используется" in e for e in report.errors))

    def test_matched_pair_passes(self):
        report = validate(
            '<img src="tg://photo?id=cover"/>',
            [Media("cover", "https://x.io/a.jpg", kind="photo")],
        )
        self.assertTrue(report.ok)

    def test_kind_mismatch_fails(self):
        report = validate(
            '<img src="tg://photo?id=cover"/>',
            [Media("cover", "https://x.io/a.mp4", kind="video")],
        )
        self.assertTrue(any("объявлено как video" in e for e in report.errors))


if __name__ == "__main__":
    unittest.main()
