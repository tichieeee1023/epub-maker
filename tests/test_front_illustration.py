import base64
import copy
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import builder
import config
import gui

SMALL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FrontIllustrationTests(unittest.TestCase):
    def setUp(self):
        self.config = config.default_book_config()
        self.config.update({
            "input_file": "unused.txt",
            "title": "테스트 작품",
            "original_title": "原題",
            "author_korean": "저자",
            "include_translation_notice": False,
            "include_reader_notice": False,
        })
        self.chapters = [{"title": "제1장", "content": "본문입니다."}]

    def contents(self, epub_file):
        with zipfile.ZipFile(epub_file) as archive:
            names = archive.namelist()
            opf = ET.fromstring(archive.read("EPUB/content.opf"))
            ns = {"opf": "http://www.idpf.org/2007/opf"}
            manifest = {
                item.attrib["id"]: item.attrib
                for item in opf.findall(".//opf:manifest/opf:item", ns)
            }
            spine = [
                manifest[item.attrib["idref"]]["href"]
                for item in opf.findall(".//opf:spine/opf:itemref", ns)
            ]
            return names, manifest, spine, {
                name: archive.read(name) for name in names if
                name.endswith((".xhtml", ".css", ".png", ".jpg"))
            }

    def test_default_is_disabled_and_old_json_is_compatible(self):
        self.assertEqual(self.config["front_illustration_file"], "")
        old = copy.deepcopy(self.config)
        old.pop("front_illustration_file")
        self.assertEqual(config.normalize_book_config(old)["front_illustration_file"], "")
        forms = gui.config_to_form_values(old)
        self.assertIn("front_illustration_file", forms)
        self.assertEqual(forms["front_illustration_file"], "")

    def test_illustration_page_immediately_follows_cover(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            cover = folder / "cover.png"
            illustration = folder / "도입 삽화.png"
            cover.write_bytes(SMALL_PNG)
            illustration.write_bytes(SMALL_PNG)
            options = copy.deepcopy(self.config)
            options.update({
                "cover_file": str(cover),
                "front_illustration_file": str(illustration),
            })
            epub_path = folder / "sample.epub"
            builder.create_epub(self.chapters, options, epub_path)
            names, manifest, spine, content = self.contents(epub_path)

            self.assertEqual(
                spine[:4],
                ["Text/cover.xhtml", "Text/illustration.xhtml",
                 "Text/title.xhtml", "Text/volume.xhtml"],
            )
            self.assertEqual(names.count("EPUB/Text/illustration.xhtml"), 1)
            self.assertIn("EPUB/Images/cover.png", names)
            self.assertIn("EPUB/Images/front_illustration.png", names)
            self.assertEqual(content["EPUB/Images/front_illustration.png"], SMALL_PNG)
            img = next(x for x in manifest.values() if x["href"] == "Images/front_illustration.png")
            self.assertEqual(img["media-type"], "image/png")
            page = content["EPUB/Text/illustration.xhtml"]
            ET.fromstring(page)
            self.assertIn(b'../Images/front_illustration.png', page)
            self.assertIn(b'../Styles/illustration.css', page)
            self.assertIn(b'max-height: 90vh', content["EPUB/Styles/illustration.css"])

    def test_no_image_means_no_extra_page_or_resource(self):
        with tempfile.TemporaryDirectory() as temp:
            epub_path = Path(temp) / "no-image.epub"
            builder.create_epub(self.chapters, self.config, epub_path)
            names, _manifest, spine, _content = self.contents(epub_path)
            self.assertNotIn("EPUB/Text/illustration.xhtml", names)
            self.assertNotIn("EPUB/Styles/illustration.css", names)
            self.assertEqual(spine[0], "Text/title.xhtml")

    def test_without_cover_illustration_is_before_title(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            illustration = folder / "img.jpg"
            illustration.write_bytes(b"\xff\xd8\xff\xe0sample")
            opts = copy.deepcopy(self.config)
            opts["front_illustration_file"] = str(illustration)
            epub_path = folder / "illustrated.epub"
            builder.create_epub(self.chapters, opts, epub_path)
            names, manifest, spine, _content = self.contents(epub_path)
            self.assertEqual(spine[:2], ["Text/illustration.xhtml", "Text/title.xhtml"])
            self.assertIn("EPUB/Images/front_illustration.jpg", names)
            item = next(x for x in manifest.values() if x["href"] == "Images/front_illustration.jpg")
            self.assertEqual(item["media-type"], "image/jpeg")

    def test_invalid_and_missing_images_produce_friendly_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name, data, expected in (
                ("broken.png", b"not png", "PNG"),
                ("broken.gif", b"GIF89a", "JPG"),
            ):
                p = folder / name
                p.write_bytes(data)
                opts = copy.deepcopy(self.config)
                opts["front_illustration_file"] = str(p)
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ValueError, expected):
                        builder.create_epub(self.chapters, opts, folder / "bad.epub")
            opts = copy.deepcopy(self.config)
            opts["front_illustration_file"] = str(folder / "missing.png")
            with self.assertRaisesRegex(ValueError, "삽화 파일이 없습니다"):
                builder.create_epub(self.chapters, opts, folder / "bad.epub")

    def test_gui_form_roundtrip_preserves_illustration_path(self):
        options = copy.deepcopy(self.config)
        options["front_illustration_file"] = "C:/Books/삽화 이미지.png"
        form = gui.config_to_form_values(options)
        rebuilt = gui.form_values_to_config(form, options)
        self.assertEqual(rebuilt["front_illustration_file"], "C:/Books/삽화 이미지.png")


if __name__ == "__main__":
    unittest.main()
