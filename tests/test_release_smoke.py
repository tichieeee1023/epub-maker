import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from builder import create_epub, split_chapter_display_title, split_chapters
from config import default_book_config


class EpubRegressionTests(unittest.TestCase):
    def test_colon_headings_and_content_are_preserved(self):
        text = (
            "#제101화: 노르망디 상륙작전 (상)\n첫 문단.\n"
            "# 제102화： 노르망디 상륙작전 (하)\n두 번째 문단.\n"
            "#제103화 결말\n세 번째 문단.\n"
            "#해시태그\n마지막 문단.\n"
        )
        chapters = split_chapters(text)
        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[0]["title"], "제101화: 노르망디 상륙작전 (상)")
        self.assertEqual(chapters[1]["title"], "제102화： 노르망디 상륙작전 (하)")
        self.assertIn("#해시태그", chapters[2]["content"])
        self.assertIn("마지막 문단.", chapters[2]["content"])
        self.assertEqual(split_chapter_display_title(chapters[0]["title"]),
                         ("제101화", "노르망디 상륙작전 (상)"))
        self.assertEqual(split_chapter_display_title(chapters[1]["title"]),
                         ("제102화", "노르망디 상륙작전 (하)"))

    def test_prologue_kept(self):
        chapters = split_chapters("권 앞머리\n#제1장\n본문")
        self.assertEqual([chapter["title"] for chapter in chapters], ["제1장"])
        self.assertTrue(chapters[0]["content"].startswith("권 앞머리"))
        self.assertIn("본문", chapters[0]["content"])

    def test_notices_in_epub_and_optional(self):
        chapters = split_chapters("#제1장 시작\n본문 내용.")
        for notices_enabled in (True, False):
            with self.subTest(notices_enabled=notices_enabled):
                config = default_book_config()
                config.update({
                    "title": "오벨리스크",
                    "input_file": "unused.txt",
                    "original_title": "方尖碑",
                    "author_korean": "일십사주",
                    "include_translation_notice": notices_enabled,
                    "include_reader_notice": notices_enabled,
                })
                with tempfile.TemporaryDirectory() as folder:
                    target = Path(folder) / "sample.epub"
                    create_epub(chapters, config, target)
                    self.assertTrue(target.is_file())
                    with zipfile.ZipFile(target) as archive:
                        names = archive.namelist()
                        self.assertTrue(any(name.endswith("Text/title.xhtml") for name in names))
                        self.assertTrue(any(name.endswith("Text/chapter_001.xhtml") for name in names))
                        for path in ("Text/translation_notice.xhtml", "Text/reader_notice.xhtml"):
                            matches = [name for name in names if name.endswith(path)]
                            self.assertEqual(bool(matches), notices_enabled, path)
                            if matches:
                                ET.fromstring(archive.read(matches[0]))
                        self.assertEqual(
                            any(name.endswith("Styles/notice.css") for name in names),
                            notices_enabled,
                        )


if __name__ == "__main__":
    unittest.main()
