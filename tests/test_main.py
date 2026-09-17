import base64
import copy
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

import main
import gui
import builder


SAMPLE_TEXT = '''#해시태그
#($**

#제1장 프롤로그 · 황혼 무렵

그가 말했다. "안녕?" 그가 웃었다.
"알았다." 그가 돌아섰다.

***

그는 고개를 들었다.

---

# 제2장 이름 없는 세계 01

그녀가 창밖을 바라봤다. "오늘은 춥네."
그는 아무 말도 하지 않았다.

#제3화

남자가 물었다. "정말……"
그녀는 고개를 끄덕였다.
'''


class EpubMakerTests(unittest.TestCase):
    def setUp(self):
        # Tests must not depend on the user's most recently autosaved GUI input.
        self.config = main.default_book_config()
        self.config.update(
            {
                "input_file": "manuscript.txt",
                "title": "오벨리스크",
                "original_title": "方尖碑",
                "korean_title": "오벨리스크",
                "english_title": "Obelisk",
                "author_korean": "일십사주",
            }
        )
        self.config["volume"].update(
            {
                "number": 1,
                "original_title": "忠诚者的誓言",
                "korean_title": "충성스러운 자의 맹세",
            }
        )
        self.config["serialization"].update(
            {
                "site": "진강문학성",
                "url": "https://example.com/obelisk",
            }
        )
        self.config["chapter_header_style"] = "simple"
        self.config["scene_break_style"] = "dots"
        self.config["section_divider_style"] = "short-line"
        self.config["volume_decoration_style"] = "floral"
        self.processed = main.preprocess_text(SAMPLE_TEXT)
        self.chapters = main.split_chapters(self.processed)

    def test_preprocess_and_strict_chapter_detection(self):
        self.assertIn('말했다.\n"안녕?"', self.processed)
        self.assertEqual(
            [chapter["title"] for chapter in self.chapters],
            ["제1장 프롤로그 · 황혼 무렵", "제2장 이름 없는 세계 01", "제3화"],
        )

    def test_legacy_spaced_and_zero_padded_heading_is_compatible(self):
        chapters = main.split_chapters("# 제001장\n본문")
        self.assertEqual([chapter["title"] for chapter in chapters], ["제001장"])

    def test_standalone_scene_markers(self):
        html = main.text_to_html(self.chapters[0]["content"])
        self.assertIn(
            '<p class="scene-break scene-break--dots">·  ·  ·</p>',
            html,
        )
        self.assertIn(
            '<hr class="section-divider section-divider--short-line" />',
            html,
        )

    def test_all_scene_break_and_divider_styles(self):
        expected_markers = {
            "dots": "·  ·  ·",
            "bullet": "•",
            "short-line": "\u00a0",
            "none": "\u00a0",
        }
        for style, marker in expected_markers.items():
            html = main.text_to_html("*", scene_break_style=style)
            self.assertIn(f"scene-break--{style}", html)
            if style == "short-line":
                self.assertIn('<span aria-hidden="true"></span>', html)
            else:
                self.assertIn(marker, html)

        for style in main.SECTION_DIVIDER_STYLES:
            html = main.text_to_html("---", section_divider_style=style)
            self.assertIn(f"section-divider--{style}", html)

        stylesheet = builder.STYLE_FILE.read_text(encoding="utf-8")
        short_line_rule = stylesheet.split(".scene-break--short-line", 1)[1].split("}", 1)[0]
        self.assertIn("padding: 1.6em 0", short_line_rule)
        short_line_span_rule = stylesheet.split(".scene-break--short-line span", 1)[1].split("}", 1)[0]
        self.assertIn("width: 2.8em", short_line_span_rule)

    def test_chapter_header_number_and_subtitle_are_separated(self):
        html = main.render_chapter_header(
            "제2장 이름 없는 세계 01",
            "subtitle",
        )
        self.assertIn("chapter-header--subtitle", html)
        self.assertIn('<h1 class="chapter-number">제2장</h1>', html)
        self.assertIn(
            '<p class="chapter-subtitle">이름 없는 세계 01</p>',
            html,
        )

    def test_inline_chapter_header_uses_spans_and_optional_subtitle(self):
        html = main.render_chapter_header(
            "제2장 이름 없는 세계 01",
            "inline",
        )
        self.assertIn("chapter-header--inline", html)
        self.assertIn('<span class="chapter-number">제2장</span>', html)
        self.assertIn(
            '<span class="chapter-subtitle">이름 없는 세계 01</span>',
            html,
        )

        no_subtitle = main.render_chapter_header("제3화", "inline")
        self.assertIn('<span class="chapter-number">제3화</span>', no_subtitle)
        self.assertNotIn('class="chapter-subtitle"', no_subtitle)

    def test_inline_and_unapproved_markers_remain_normal_text(self):
        html = main.text_to_html("문장 중간의 *** 표시는 유지\n**\n문장---중간")
        self.assertNotIn('class="scene-break"', html)
        self.assertNotIn('class="section-divider"', html)
        self.assertIn("문장 중간의 *** 표시는 유지", html)
        self.assertIn("<p>**</p>", html)
        self.assertIn("문장---중간", html)

    def test_postprocess_target_counts(self):
        self.assertEqual(main.count_postprocess_targets(self.chapters), (1, 1))

    def test_book_config_validation(self):
        missing_title = copy.deepcopy(self.config)
        del missing_title["title"]
        with self.assertRaisesRegex(ValueError, "작품명"):
            main.validate_book_config(missing_title)

        invalid_volume = copy.deepcopy(self.config)
        invalid_volume["volume"]["number"] = 0
        with self.assertRaisesRegex(ValueError, "1 이상"):
            main.validate_book_config(invalid_volume)

        invalid_style = copy.deepcopy(self.config)
        invalid_style["chapter_header_style"] = "decorative"
        with self.assertRaisesRegex(ValueError, "챕터 헤더"):
            main.validate_book_config(invalid_style)

        legacy_minimal = copy.deepcopy(self.config)
        legacy_minimal["chapter_header_style"] = "minimal"
        self.assertEqual(
            main.normalize_book_config(legacy_minimal)["chapter_header_style"],
            "simple",
        )

        legacy_diamonds = copy.deepcopy(self.config)
        legacy_diamonds["scene_break_style"] = "diamond"
        legacy_diamonds["volume_decoration_style"] = "sparkle"
        migrated = main.normalize_book_config(legacy_diamonds)
        self.assertEqual(migrated["scene_break_style"], "dots")
        self.assertEqual(migrated["volume_decoration_style"], "leaf")

        legacy_stars = copy.deepcopy(self.config)
        legacy_stars["scene_break_style"] = "asterisks"
        legacy_stars["volume_decoration_style"] = "asterisk"
        migrated = main.normalize_book_config(legacy_stars)
        self.assertEqual(migrated["scene_break_style"], "short-line")
        self.assertEqual(migrated["volume_decoration_style"], "dot")

        optional_fields_empty = copy.deepcopy(self.config)
        optional_fields_empty.update({"korean_title": "", "english_title": ""})
        optional_fields_empty["volume"].update(
            {"original_title": "", "korean_title": ""}
        )
        optional_fields_empty["serialization"] = {"site": "", "url": ""}
        self.assertEqual(
            main.validate_book_config(optional_fields_empty)["title"],
            "오벨리스크",
        )

    def test_identifier_is_generated_automatically_and_stably(self):
        self.assertNotIn("identifier", self.config)
        first = main.create_book_identifier(self.config)
        second = main.create_book_identifier(copy.deepcopy(self.config))
        next_volume = copy.deepcopy(self.config)
        next_volume["volume"]["number"] = 2

        self.assertTrue(first.startswith("urn:uuid:"))
        self.assertEqual(first, second)
        self.assertNotEqual(first, main.create_book_identifier(next_volume))

    def test_book_config_save_and_gui_form_restore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "book.json"
            main.save_book_config(copy.deepcopy(self.config), config_path)
            restored = main.load_book_config(config_path)

        form_values = gui.config_to_form_values(restored)
        form_values["volume.number"] = "2"
        form_values["volume.korean_title"] = "두 번째 권"
        form_values["chapter_header_style"] = "C. 부제 포함형"
        form_values["scene_break_style"] = "짧은 회색 실선"
        form_values["section_divider_style"] = "이중선"
        form_values["volume_decoration_style"] = "∞ 무한류 · 무한 기호"
        updated = gui.form_values_to_config(form_values, restored)

        self.assertEqual(updated["volume"]["number"], 2)
        self.assertEqual(updated["volume"]["korean_title"], "두 번째 권")
        self.assertEqual(updated["input_file"], restored["input_file"])
        self.assertEqual(updated["chapter_header_style"], "subtitle")
        self.assertEqual(updated["scene_break_style"], "short-line")
        self.assertEqual(updated["section_divider_style"], "double-line")
        self.assertEqual(updated["volume_decoration_style"], "infinite")
        chapter_options = gui.STYLE_SPECS[0][2]
        self.assertEqual(
            tuple(chapter_options),
            (
                "A. 담백형",
                "B. 자간 강조형",
                "C. 부제 포함형",
                "D. 나란히형",
            ),
        )
        self.assertNotIn("minimal", chapter_options.values())

    def test_missing_book_config_is_created_with_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "book.json"
            loaded = main.load_book_config(config_path)

            self.assertTrue(config_path.exists())
            self.assertEqual(loaded["chapter_header_style"], "simple")
            self.assertEqual(loaded["scene_break_style"], "dots")
            self.assertEqual(loaded["section_divider_style"], "short-line")
            self.assertEqual(loaded["volume_decoration_style"], "leaf")
            self.assertEqual(loaded["serialization"]["site"], "晋江文学城")

    def test_reset_clears_prefilled_serialization_site(self):
        self.assertEqual(
            main.default_book_config()["serialization"]["site"],
            "晋江文学城",
        )
        self.assertEqual(main.reset_book_config()["serialization"]["site"], "")

    def test_gui_displays_only_selected_file_name(self):
        self.assertEqual(
            gui.display_file_name("C:/books/소설 1권.txt", "선택 없음"),
            "소설 1권.txt",
        )
        self.assertEqual(gui.display_file_name("", "선택 없음"), "선택 없음")

    def test_gui_preview_loads_actual_first_chapter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "preview.txt"
            input_path.write_text(SAMPLE_TEXT, encoding="utf-8")
            chapter = gui.load_first_chapter_preview(str(input_path))

        self.assertEqual(chapter["title"], "제1장 프롤로그 · 황혼 무렵")
        self.assertIn("그가 말했다.", chapter["content"])

    def test_cover_is_registered_and_placed_first(self):
        one_pixel_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cover_path = temp_path / "selected-cover.png"
            cover_path.write_bytes(one_pixel_png)
            output_epub = temp_path / "with-cover.epub"
            config = copy.deepcopy(self.config)
            config["cover_file"] = str(cover_path)

            main.create_epub(self.chapters, config, output_epub)

            with zipfile.ZipFile(output_epub) as archive:
                names = archive.namelist()
                package = archive.read("EPUB/content.opf").decode("utf-8")
                cover_page = archive.read("EPUB/Text/cover.xhtml").decode("utf-8")
                self.assertIn("EPUB/Images/cover.png", names)
                self.assertIn("EPUB/Text/cover.xhtml", names)
                self.assertIn("EPUB/Styles/cover.css", names)
                self.assertIn('name="cover"', package)
                self.assertIn('../Images/cover.png', cover_page)
                self.assertIn('../Styles/cover.css', cover_page)
                self.assertNotIn("{{", cover_page)

                package_xml = ElementTree.fromstring(package)
                namespace = {"opf": "http://www.idpf.org/2007/opf"}
                manifest_items = package_xml.findall(
                    ".//opf:manifest/opf:item",
                    namespace,
                )
                manifest = {
                    item.attrib["id"]: item.attrib["href"]
                    for item in manifest_items
                }
                cover_image_item = next(
                    item for item in manifest_items if item.attrib["id"] == "cover-img"
                )
                self.assertEqual(cover_image_item.attrib["href"], "Images/cover.png")
                self.assertEqual(cover_image_item.attrib["media-type"], "image/png")
                self.assertEqual(cover_image_item.attrib["properties"], "cover-image")

                cover_meta = package_xml.find(
                    ".//opf:metadata/opf:meta[@name='cover']",
                    namespace,
                )
                self.assertEqual(cover_meta.attrib["content"], "cover-img")

                guide_cover = package_xml.find(
                    ".//opf:guide/opf:reference[@type='cover']",
                    namespace,
                )
                self.assertEqual(guide_cover.attrib["href"], "Text/cover.xhtml")

                spine_hrefs = [
                    manifest[item.attrib["idref"]]
                    for item in package_xml.findall(".//opf:spine/opf:itemref", namespace)
                ]
                self.assertEqual(spine_hrefs[0], "Text/cover.xhtml")
                self.assertEqual(spine_hrefs[1], "Text/title.xhtml")
                self.assertNotIn("nav.xhtml", spine_hrefs)

                toc = ElementTree.fromstring(archive.read("EPUB/toc.ncx"))
                toc_namespace = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
                labels = [
                    node.text
                    for node in toc.findall(
                        ".//ncx:navLabel/ncx:text",
                        toc_namespace,
                    )
                ]
                self.assertEqual(
                    labels,
                    [
                        "제1장 프롤로그 · 황혼 무렵",
                        "제2장 이름 없는 세계 01",
                        "제3화",
                        "책정보",
                    ],
                )

    def test_jpeg_cover_uses_stable_internal_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cover_path = Path(temp_dir) / "한글 표지 이름.jpeg"
            cover_path.write_bytes(b"\xff\xd8\xff\xe0test")
            cover_name, content = main.validate_cover_file(cover_path)

        self.assertEqual(cover_name, "Images/cover.jpg")
        self.assertTrue(content.startswith(b"\xff\xd8\xff"))

    def test_generated_epub_is_saved_next_to_selected_txt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "선택한 원고 1권.txt"
            input_path.write_text(SAMPLE_TEXT, encoding="utf-8")
            config = copy.deepcopy(self.config)
            config["input_file"] = str(input_path)
            config["cover_file"] = ""
            diagnostics_dir = temp_path / "diagnostics"

            with (
                patch.object(builder, "OUTPUT_DIR", diagnostics_dir),
                patch.object(builder, "OUTPUT_TXT", diagnostics_dir / "output.txt"),
            ):
                result = main.generate_from_config(config)

            expected_epub = input_path.with_suffix(".epub")
            self.assertEqual(result["output_epub"], expected_epub)
            self.assertTrue(expected_epub.exists())

    def test_epub_package_links_toc_and_xml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            output_epub = output_dir / "output.epub"

            main.create_epub(self.chapters, self.config, output_epub)

            with zipfile.ZipFile(output_epub) as archive:
                names = archive.namelist()
                title_page = archive.read("EPUB/Text/title.xhtml").decode("utf-8")
                volume = archive.read("EPUB/Text/volume.xhtml").decode("utf-8")
                chapter = archive.read("EPUB/Text/chapter_001.xhtml").decode("utf-8")
                bookinfo_page = archive.read("EPUB/Text/bookinfo.xhtml").decode("utf-8")
                package = archive.read("EPUB/content.opf").decode("utf-8")

                self.assertEqual(names.count("EPUB/Text/title.xhtml"), 1)
                self.assertEqual(names.count("EPUB/Text/volume.xhtml"), 1)
                self.assertEqual(names.count("EPUB/Text/bookinfo.xhtml"), 1)
                self.assertNotIn("EPUB/Fonts/Pretendard-Bold.otf", names)
                self.assertNotIn("EPUB/Fonts/OFL.txt", names)
                self.assertEqual(
                    len([name for name in names if name.startswith("EPUB/Text/chapter_")]),
                    3,
                )
                self.assertIn('../Styles/style.css', title_page)
                self.assertIn('../Styles/style.css', volume)
                self.assertIn('../Styles/style.css', chapter)
                self.assertIn('../Styles/style.css', bookinfo_page)
                self.assertIn('Styles/style.css', package)
                self.assertIn(main.create_book_identifier(self.config), package)
                self.assertIn("오벨리스크", title_page)
                self.assertIn("方尖碑", title_page)
                self.assertIn("일십사주", title_page)
                self.assertIn("❦", volume)
                self.assertIn("책정보", bookinfo_page)
                self.assertNotIn("{{", title_page + volume + bookinfo_page)
                self.assertIn("chapter-header--simple", chapter)
                self.assertIn('<h1 class="chapter-number">제1장</h1>', chapter)
                self.assertIn("chapter-subtitle", chapter)
                self.assertIn(
                    '<p class="scene-break scene-break--dots">·  ·  ·</p>',
                    chapter,
                )
                self.assertIn(
                    '<hr class="section-divider section-divider--short-line"/>',
                    chapter,
                )

                xml_files = [
                    name
                    for name in names
                    if name.endswith((".xhtml", ".opf", ".ncx"))
                ]
                for name in xml_files:
                    ElementTree.fromstring(archive.read(name))

                toc = ElementTree.fromstring(archive.read("EPUB/toc.ncx"))
                namespace = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
                labels = [
                    node.text
                    for node in toc.findall(".//ncx:navLabel/ncx:text", namespace)
                ]
                self.assertEqual(
                    labels,
                    [
                        "제1장 프롤로그 · 황혼 무렵",
                        "제2장 이름 없는 세계 01",
                        "제3화",
                        "책정보",
                    ],
                )

                package_xml = ElementTree.fromstring(archive.read("EPUB/content.opf"))
                opf_namespace = {"opf": "http://www.idpf.org/2007/opf"}
                manifest = {
                    item.attrib["id"]: item.attrib["href"]
                    for item in package_xml.findall(".//opf:manifest/opf:item", opf_namespace)
                }
                spine_hrefs = [
                    manifest[item.attrib["idref"]]
                    for item in package_xml.findall(".//opf:spine/opf:itemref", opf_namespace)
                ]
                self.assertEqual(spine_hrefs[0], "Text/title.xhtml")
                self.assertLess(spine_hrefs.index("Text/title.xhtml"), spine_hrefs.index("Text/volume.xhtml"))
                self.assertLess(spine_hrefs.index("Text/volume.xhtml"), spine_hrefs.index("Text/chapter_001.xhtml"))
                self.assertLess(spine_hrefs.index("Text/chapter_003.xhtml"), spine_hrefs.index("Text/bookinfo.xhtml"))

    def test_every_scene_and_volume_ornament_combination_builds_cleanly(self):
        chapters = [
            {
                "title": "제1장 조합 검사",
                "content": "첫 문장\n\n***\n\n둘째 문장\n\n*\n\n셋째 문장",
            }
        ]
        stylesheet = builder.STYLE_FILE.read_text(encoding="utf-8")
        self.assertNotIn("font-size: 0;", stylesheet)
        self.assertIn(".scene-break--short-line span", stylesheet)
        self.assertIn("padding: 1.6em 0", stylesheet)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            for scene_style, marker in main.SCENE_BREAK_STYLES.items():
                for decoration_style, decoration in main.VOLUME_DECORATIONS.items():
                    config = copy.deepcopy(self.config)
                    config["scene_break_style"] = scene_style
                    config["volume_decoration_style"] = decoration_style
                    output_epub = temp_path / f"{scene_style}-{decoration_style}.epub"
                    main.create_epub(chapters, config, output_epub)

                    with zipfile.ZipFile(output_epub) as archive:
                        names = archive.namelist()
                        chapter = archive.read("EPUB/Text/chapter_001.xhtml").decode("utf-8")
                        volume = archive.read("EPUB/Text/volume.xhtml").decode("utf-8")
                        toc = archive.read("EPUB/toc.ncx").decode("utf-8")

                        self.assertNotIn("{{", chapter + volume)
                        self.assertNotIn("EPUB/Fonts/Pretendard-Bold.otf", names)
                        self.assertIn("책정보", toc)
                        self.assertIn(decoration, volume)
                        if scene_style == "short-line":
                            self.assertEqual(
                                chapter.count('aria-hidden="true"'),
                                2,
                            )
                        else:
                            self.assertEqual(chapter.count(marker), 2)

                        for name in names:
                            if name.endswith((".xhtml", ".opf", ".ncx")):
                                ElementTree.fromstring(archive.read(name))


if __name__ == "__main__":
    unittest.main()
