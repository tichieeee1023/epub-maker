import tempfile
import unittest
from pathlib import Path

import builder
import config


class ChapterDetectionRegressionTests(unittest.TestCase):
    def test_exact_user_reported_headings(self):
        manuscript = "# 제1장\n첫째 장 본문\n#제1화\n첫째 화 본문\n"
        chapters = builder.split_chapters(builder.preprocess_text(manuscript))
        self.assertEqual([c["title"] for c in chapters], ["제1장", "제1화"])
        self.assertIn("첫째 장 본문", chapters[0]["content"])
        self.assertIn("첫째 화 본문", chapters[1]["content"])

    def test_hidden_characters_indentation_multiple_hashes_and_fullwidth(self):
        raw = (
            "\ufeff# 제1장\n하나\n"
            "  #제2화\n둘\n"
            "\u200b#  제3장: 소제목\n셋\n"
            "## 제4화 (상)\n넷\n"
            "＃　제5화：다섯\n다섯\n"
            "# 제 6 화 - 마지막\n여섯\n"
        )
        chapters = builder.split_chapters(raw)
        self.assertEqual(
            [c["title"] for c in chapters],
            ["제1장", "제2화", "제3장: 소제목", "제4화 (상)",
             "제5화：다섯", "제6화 - 마지막"],
        )
        self.assertEqual([c["content"] for c in chapters],
                         ["하나", "둘", "셋", "넷", "다섯", "여섯"])
        self.assertFalse(builder.find_unrecognized_chapter_headings(raw))

    def test_100_chapters_without_dropping_a_single_heading_or_body(self):
        text = "".join(
            (f"  # 제{n}화\n" if n % 2 else f"\ufeff#제{n}화: 제목 {n}\n")
            + f"본문 {n}\n" for n in range(1, 151)
        )
        chapters = builder.split_chapters(builder.preprocess_text(text))
        self.assertEqual(len(chapters), 150)
        self.assertEqual(chapters[0]["title"], "제1화")
        self.assertEqual(chapters[-1]["title"], "제150화: 제목 150")
        for n, c in enumerate(chapters, start=1):
            self.assertIn(f"본문 {n}", c["content"])

    def test_chapter_display_titles_remain_compatible(self):
        self.assertEqual(builder.split_chapter_display_title("제101화: 노르망디 상륙작전 (상)"),
                         ("제101화", "노르망디 상륙작전 (상)"))
        self.assertEqual(builder.split_chapter_display_title("제5장 제목"),
                         ("제5장", "제목"))
        self.assertEqual(builder.split_chapter_display_title("第12章：副标题"),
                         ("第12章", "副标题"))

    def test_chinese_heading_and_suffixes_are_supported(self):
        text = "## 第1章: 你好\n본문\n# 제2화(하)\n본문2\n"
        chapters = builder.split_chapters(text)
        self.assertEqual([c["title"] for c in chapters],
                         ["第1章: 你好", "제2화(하)"])

    def test_non_chapter_hashtags_remain_body_text(self):
        text = "#해시태그\n#($**\n#제도적 문제\n#제1장\n정상본문\n"
        chapters = builder.split_chapters(text)
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0]["title"], "제1장")
        self.assertIn("#해시태그", chapters[0]["content"])
        self.assertIn("#제도적 문제", chapters[0]["content"])

    def test_unsupported_probable_heading_is_flagged(self):
        text = "# 제1장\n본문\n# 제2권 : 기타\n추가 내용\n"
        self.assertEqual(builder.find_unrecognized_chapter_headings(text),
                         [(3, "# 제2권 : 기타")])

    def test_preflight_prevents_overwriting_existing_epub(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            original = root / "novel.txt"
            original.write_text("#제1화\n본문\n#제2권\n내용", encoding="utf-8")
            existing_epub = root / "novel.epub"
            existing_epub.write_bytes(b"keep old EPUB")
            options = config.default_book_config()
            options.update({
                "title": "테스트", "original_title": "测试",
                "author_korean": "저자", "input_file": str(original),
            })
            with self.assertRaisesRegex(ValueError, "3행"):
                builder.generate_from_config(options)
            self.assertEqual(existing_epub.read_bytes(), b"keep old EPUB")

    def test_blank_line_scene_detection_does_not_insert_at_new_headings(self):
        raw = "#제1화\n\n\n첫 문단\n\n\n  #제2화\n\n\n둘째 문단"
        marked = builder.mark_blank_scene_breaks(raw, "2")
        self.assertNotIn(builder.BLANK_SCENE_BREAK_MARKER, marked)

    def test_missing_number_hints_are_not_mistaken_for_broken_parser(self):
        chapters = builder.split_chapters("#제101화\n본문\n#제103화\n본문\n")
        self.assertEqual(builder.find_number_gaps(chapters), ["101화 → 103화"])


if __name__ == "__main__":
    unittest.main()
