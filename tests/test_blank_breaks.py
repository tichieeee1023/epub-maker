import copy
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from builder import (
    BLANK_SCENE_BREAK_MARKER,
    generate_from_config,
    mark_blank_scene_breaks,
    preprocess_text,
    split_chapters,
    text_to_html,
)
from config import default_book_config


class BlankBreakTests(unittest.TestCase):
    def test_explicit_two_blank_lines_and_regular_single_blank_line(self):
        manuscript = "첫 문단\n\n둘째 문단\n\n\n장면 전환 뒤."
        marked = mark_blank_scene_breaks(manuscript, "2")
        self.assertEqual(marked.count(BLANK_SCENE_BREAK_MARKER), 1)
        self.assertIn("첫 문단\n\n둘째 문단", marked)
        self.assertIn(BLANK_SCENE_BREAK_MARKER, preprocess_text(marked))

    def test_one_blank_line_mode_is_opt_in(self):
        manuscript = "첫 문단\n\n둘째 문단"
        self.assertEqual(mark_blank_scene_breaks(manuscript, "off"), manuscript)
        self.assertEqual(mark_blank_scene_breaks(manuscript, "2"), manuscript)
        self.assertIn(BLANK_SCENE_BREAK_MARKER, mark_blank_scene_breaks(manuscript, "1"))

    def test_three_blank_line_threshold(self):
        manuscript = "가\n\n\n나\n\n\n\n다"
        marked = mark_blank_scene_breaks(manuscript, "3")
        self.assertEqual(marked.count(BLANK_SCENE_BREAK_MARKER), 1)

    def test_no_scene_marker_at_chapter_boundaries(self):
        manuscript = "#제1장\n\n\n첫 문단\n\n\n#제2장 제목\n\n\n둘째 문단"
        marked = mark_blank_scene_breaks(manuscript, "2")
        self.assertNotIn(BLANK_SCENE_BREAK_MARKER, marked)

    def test_no_double_marker_beside_visible_break(self):
        manuscript = "하나\n\n\n***\n\n\n둘"
        marked = mark_blank_scene_breaks(manuscript, "2")
        self.assertNotIn(BLANK_SCENE_BREAK_MARKER, marked)

    def test_blank_marker_has_visible_reflowable_spacing(self):
        html = text_to_html("앞\n" + BLANK_SCENE_BREAK_MARKER + "\n뒤",
                            blank_break_style="space")
        self.assertIn('scene-break--blank-space', html)
        self.assertIn('&#160;', html)
        self.assertNotIn(BLANK_SCENE_BREAK_MARKER, html)

    def test_blank_dingbat_and_triple_star_are_separate(self):
        html = text_to_html("앞\n*\n***\n" + BLANK_SCENE_BREAK_MARKER,
                            scene_break_style="dots",
                            triple_star_style="leaf",
                            blank_break_style="short-line")
        self.assertIn('scene-break--dots', html)
        self.assertIn('scene-break--leaf', html)
        self.assertIn('scene-break--short-line', html)

    def test_original_dot_symbols_remain_identical(self):
        html = text_to_html("앞\n· · ·\n뒤\n•••\n끝\n•")
        self.assertIn('scene-break--source-dots">· · ·</p>', html)
        self.assertIn('scene-break--source-dots">•••</p>', html)
        self.assertIn('scene-break--source-dots">•</p>', html)

    def test_end_to_end_epub_and_diagnostic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            txt_path = root / "book.txt"
            txt_path.write_text("#제1장 시작\n첫째\n\n\n둘째\n", encoding="utf-8")
            config = default_book_config()
            config.update({
                "title": "테스트",
                "original_title": "測試",
                "author_korean": "저자",
                "input_file": str(txt_path),
                "blank_break_detection": "2",
                "blank_break_style": "space",
                "include_translation_notice": False,
                "include_reader_notice": False,
            })
            with patch("builder.OUTPUT_DIR", root), patch("builder.OUTPUT_TXT", root / "output.txt"):
                result = generate_from_config(copy.deepcopy(config))
            self.assertEqual(result["blank_breaks"], 1)
            with zipfile.ZipFile(result["output_epub"]) as archive:
                chapter = archive.read("EPUB/Text/chapter_001.xhtml").decode("utf-8")
                self.assertIn("scene-break--blank-space", chapter)
                self.assertNotIn(BLANK_SCENE_BREAK_MARKER, chapter)
                self.assertIn('Styles/style.css', archive.namelist()[-1] if False else archive.read("EPUB/content.opf").decode("utf-8"))
            self.assertIn("[공백 장면전환]", (root / "output.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
