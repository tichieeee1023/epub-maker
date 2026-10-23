import re
from html import escape
from pathlib import Path

from ebooklib import epub

from config import (
    APP_DIR,
    DEFAULT_SCENE_BREAK_STYLE,
    DEFAULT_SECTION_DIVIDER_STYLE,
    RESOURCE_DIR,
    SCENE_BREAK_STYLES,
    VOLUME_DECORATIONS,
    create_book_identifier,
    resolve_user_path,
    validate_book_config,
)


OUTPUT_DIR = APP_DIR / "output"
OUTPUT_TXT = OUTPUT_DIR / "output.txt"
OUTPUT_EPUB = OUTPUT_DIR / "output.epub"
STYLE_FILE = RESOURCE_DIR / "styles" / "style.css"
COVER_STYLE_FILE = RESOURCE_DIR / "styles" / "cover.css"
COVER_TEMPLATE_FILE = RESOURCE_DIR / "templates" / "cover.xhtml"
TITLE_TEMPLATE_FILE = RESOURCE_DIR / "templates" / "title.xhtml"
VOLUME_TEMPLATE_FILE = RESOURCE_DIR / "templates" / "volume.xhtml"
BOOKINFO_TEMPLATE_FILE = RESOURCE_DIR / "templates" / "bookinfo.xhtml"
TRANSLATION_NOTICE_FILE = RESOURCE_DIR / "templates" / "translation_notice.xhtml"
READER_NOTICE_FILE = RESOURCE_DIR / "templates" / "reader_notice.xhtml"
NOTICE_STYLE_FILE = RESOURCE_DIR / "styles" / "notice.css"

SCENE_BREAK_MARKERS = frozenset({"*", "***"})
SECTION_DIVIDER_MARKER = "---"
BLANK_SCENE_BREAK_MARKER = "__EPUB_MAKER_BLANK_SCENE_BREAK__"
SOURCE_DOT_BREAK_RE = re.compile(r"[·•∙](?:[ \t]*[·•∙]){0,9}")
CHAPTER_HEADING_LINE = re.compile(
    r"^#[ \t]*제\d+(?:장|화)(?:[ \t]*[:：][ \t]*[^\r\n]+|[ \t]+[^\r\n]+)?[ \t]*$"
)


def mark_blank_scene_breaks(text, detection="off"):
    """Protect intentional blank-line runs BEFORE dialogue cleanup collapses them.

    detection is the number of *empty lines*, not newline characters.
    The default 'off' preserves existing behavior. One empty line is
    ambiguous with normal paragraph spacing and must be explicitly enabled.
    """
    if detection == "off":
        return text

    threshold = int(detection)
    lines = text.splitlines()
    result = []
    i = 0
    while i < len(lines):
        if lines[i].strip():
            result.append(lines[i])
            i += 1
            continue
        start = i
        while i < len(lines) and not lines[i].strip():
            i += 1
        count = i - start
        before = lines[start - 1].strip() if start else ""
        after = lines[i].strip() if i < len(lines) else ""
        special = SCENE_BREAK_MARKERS | {SECTION_DIVIDER_MARKER, BLANK_SCENE_BREAK_MARKER}
        if (
            count >= threshold
            and before and after
            and not CHAPTER_HEADING_LINE.fullmatch(before)
            and not CHAPTER_HEADING_LINE.fullmatch(after)
            and before not in special and after not in special
        ):
            result.append(BLANK_SCENE_BREAK_MARKER)
        else:
            result.extend(lines[start:i])
    return "\n".join(result)



def preprocess_text(text):
    patterns = [
        r'(["“][^"”]*\.["”])',
        r'(["“][^"”]*\?["”])',
        r'(["“][^"”]*!["”])',
        r'(["“][^"”]*……["”])',
        r'(["“][^"”]*,["”])',
    ]

    for pattern in patterns:
        text = re.sub(pattern, lambda match: match.group(1) + "\n", text)

    text = re.sub(r'다\.\s+(?=["“])', "다.\n", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def split_chapters(text):
    """#제1장 또는 #제1장 소제목 형식만 실제 챕터로 인식한다."""
    pattern = re.compile(
        r"^#[ \t]*(제\d+(?:장|화)(?:[ \t]*[:：][ \t]*[^\r\n]+|[ \t]+[^\r\n]+)?)\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    chapters = []

    # 첫 챕터 앞의 미인식 원고는 첫 챕터에 포함해 데이터 유실을 막는다.
    opening_text = text[:matches[0].start()].strip() if matches else ""

    for index, match in enumerate(matches):
        content_start = match.end()
        content_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )
        chapters.append(
            {
                "title": match.group(1).strip(),
                "content": (
                    (opening_text + "\n\n" if index == 0 and opening_text else "")
                    + text[content_start:content_end].strip()
                ),
            }
        )

    return chapters


def text_to_html(
    content,
    scene_break_style=DEFAULT_SCENE_BREAK_STYLE,
    section_divider_style=DEFAULT_SECTION_DIVIDER_STYLE,
    triple_star_style="same",
    blank_break_style="space",
):
    html_parts = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == BLANK_SCENE_BREAK_MARKER:
            if blank_break_style == "space":
                html_parts.append('<p class="scene-break scene-break--blank-space">&#160;</p>')
            else:
                style = blank_break_style
                if style == "short-line":
                    html_parts.append(
                        '<p class="scene-break scene-break--short-line">'
                        '<span aria-hidden="true"></span></p>'
                    )
                else:
                    marker = "❧" if style == "leaf" else SCENE_BREAK_STYLES[style]
                    html_parts.append(
                        f'<p class="scene-break scene-break--{style}">{marker}</p>'
                    )
        elif SOURCE_DOT_BREAK_RE.fullmatch(line):
            html_parts.append(
                f'<p class="scene-break scene-break--source-dots">{escape(line)}</p>'
            )
        elif line in SCENE_BREAK_MARKERS:
            style = triple_star_style if line == "***" and triple_star_style != "same" else scene_break_style
            if style == "short-line":
                html_parts.append(
                    '<p class="scene-break scene-break--short-line">'
                    '<span aria-hidden="true"></span></p>'
                )
            else:
                marker = "❧" if style == "leaf" else SCENE_BREAK_STYLES[style]
                html_parts.append(
                    f'<p class="scene-break scene-break--{style}">{marker}</p>'
                )
        elif line == SECTION_DIVIDER_MARKER:
            html_parts.append(
                '<hr class="section-divider '
                f'section-divider--{section_divider_style}" />'
            )
        else:
            html_parts.append(f"<p>{escape(line)}</p>")

    return "\n".join(html_parts)


def split_chapter_display_title(title):
    match = re.fullmatch(r"(제\d+(?:장|화))(?:[ \t]*[:：][ \t]*(.+)|[ \t]+(.+))?", title)
    if not match:
        return title, ""
    return match.group(1), (match.group(2) or match.group(3) or "").strip()


def render_chapter_header(title, chapter_header_style):
    chapter_number, subtitle = split_chapter_display_title(title)

    if chapter_header_style == "inline":
        subtitle_html = ""
        if subtitle:
            subtitle_html = (
                f'<span class="chapter-subtitle">{escape(subtitle)}</span>'
            )
        return f"""
    <header class="chapter-header chapter-header--inline">
        <span class="chapter-number">{escape(chapter_number)}</span>
        {subtitle_html}
        <div class="chapter-rule"></div>
    </header>
    """

    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<p class="chapter-subtitle">{escape(subtitle)}</p>'

    return f"""
    <header class="chapter-header chapter-header--{chapter_header_style}">
        <h1 class="chapter-number">{escape(chapter_number)}</h1>
        {subtitle_html}
        <div class="chapter-rule"></div>
    </header>
    """


def count_postprocess_targets(chapters):
    scene_breaks = 0
    section_dividers = 0

    for chapter in chapters:
        for raw_line in chapter["content"].splitlines():
            line = raw_line.strip()
            if line in SCENE_BREAK_MARKERS or SOURCE_DOT_BREAK_RE.fullmatch(line):
                scene_breaks += 1
            elif line == SECTION_DIVIDER_MARKER:
                section_dividers += 1

    return scene_breaks, section_dividers


def template_values(config):
    volume = config["volume"]
    serialization = config["serialization"]
    return {
        "{{ book_title }}": escape(config["title"]),
        "{{ book_original_title }}": escape(config["original_title"]),
        "{{ book_korean_title }}": escape(config["korean_title"]),
        "{{ book_english_title }}": escape(config["english_title"]),
        "{{ author_korean }}": escape(config["author_korean"]),
        "{{ serialization_site }}": escape(serialization["site"]),
        "{{ serialization_url }}": escape(serialization["url"]),
        "{{ volume_number }}": str(volume["number"]),
        "{{ volume_number_padded }}": f'{volume["number"]:02}',
        "{{ volume_original_title }}": escape(volume["original_title"]),
        "{{ volume_korean_title }}": escape(volume["korean_title"]),
        "{{ volume_decoration }}": VOLUME_DECORATIONS[config["volume_decoration_style"]],
    }


def render_template(template_path, config):
    template = template_path.read_text(encoding="utf-8")
    for placeholder, value in template_values(config).items():
        template = template.replace(placeholder, value)
    return template


def add_stylesheet_link(document):
    document.add_link(
        href="../Styles/style.css",
        rel="stylesheet",
        type="text/css",
    )


def add_cover_stylesheet_link(document):
    document.add_link(
        href="../Styles/cover.css",
        rel="stylesheet",
        type="text/css",
    )


def validate_cover_file(cover_path):
    if not cover_path.exists():
        raise ValueError(f"표지 파일이 없습니다: {cover_path}")

    suffix = cover_path.suffix.lower()
    content = cover_path.read_bytes()
    if suffix in {".jpg", ".jpeg"}:
        if not content.startswith(b"\xff\xd8\xff"):
            raise ValueError("표지 이미지 형식을 확인해주세요. 올바른 JPEG가 아닙니다.")
        return "Images/cover.jpg", content
    if suffix == ".png":
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("표지 이미지 형식을 확인해주세요. 올바른 PNG가 아닙니다.")
        return "Images/cover.png", content

    raise ValueError("표지 이미지 형식을 확인해주세요. JPG, JPEG, PNG만 지원합니다.")


def create_cover_page(book, config, cover_name, cover_content, cover_style):
    book.set_cover(cover_name, cover_content, create_page=False)
    book.add_item(cover_style)

    template = COVER_TEMPLATE_FILE.read_text(encoding="utf-8")
    template = template.replace("{{ cover_image_href }}", f"../{cover_name}")
    template = template.replace("{{ book_title }}", escape(config["title"]))

    cover_page = epub.EpubHtml(
        uid="cover",
        title="표지",
        file_name="Text/cover.xhtml",
        lang="ko",
    )
    cover_page.content = template
    add_cover_stylesheet_link(cover_page)
    book.add_item(cover_page)
    book.guide.append({"type": "cover", "title": "표지", "item": cover_page})
    return cover_page


def create_epub(chapters, config, output_epub=None):
    config = validate_book_config(config)
    volume_number = config["volume"]["number"]
    output_path = Path(output_epub) if output_epub is not None else OUTPUT_EPUB
    book = epub.EpubBook()
    book.set_identifier(create_book_identifier(config))
    book.set_title(f'{config["title"]} {volume_number}권')
    book.set_language("ko")
    book.add_author(config["author_korean"])

    style = epub.EpubItem(
        uid="style_default",
        file_name="Styles/style.css",
        media_type="text/css",
        content=STYLE_FILE.read_text(encoding="utf-8"),
    )
    book.add_item(style)

    cover_style = epub.EpubItem(
        uid="style_cover",
        file_name="Styles/cover.css",
        media_type="text/css",
        content=COVER_STYLE_FILE.read_text(encoding="utf-8"),
    )

    cover_page = None
    cover_value = config.get("cover_file", "").strip()
    if cover_value:
        cover_path = resolve_user_path(cover_value)
        cover_name, cover_content = validate_cover_file(cover_path)
        cover_page = create_cover_page(
            book,
            config,
            cover_name,
            cover_content,
            cover_style,
        )

    title_page = epub.EpubHtml(
        title=f'{config["title"]} {volume_number}권',
        file_name="Text/title.xhtml",
        lang="ko",
    )
    title_page.content = render_template(TITLE_TEMPLATE_FILE, config)
    add_stylesheet_link(title_page)
    book.add_item(title_page)

    volume_page = epub.EpubHtml(
        title=f"제{volume_number}권",
        file_name="Text/volume.xhtml",
        lang="ko",
    )
    volume_page.content = render_template(VOLUME_TEMPLATE_FILE, config)
    add_stylesheet_link(volume_page)
    book.add_item(volume_page)

    notice_pages = []
    if config.get("include_translation_notice", True) or config.get("include_reader_notice", True):
        notice_style = epub.EpubItem(
            uid="style_notice",
            file_name="Styles/notice.css",
            media_type="text/css",
            content=NOTICE_STYLE_FILE.read_text(encoding="utf-8"),
        )
        book.add_item(notice_style)
        for enabled, template_file, page_title, page_name in (
            (config.get("include_translation_notice", True), TRANSLATION_NOTICE_FILE, "번역 안내", "translation_notice.xhtml"),
            (config.get("include_reader_notice", True), READER_NOTICE_FILE, "이용자 유의사항", "reader_notice.xhtml"),
        ):
            if not enabled:
                continue
            notice_page = epub.EpubHtml(
                title=page_title,
                file_name=f"Text/{page_name}",
                lang="ko",
            )
            notice_page.content = template_file.read_text(encoding="utf-8")
            notice_page.add_link(href="../Styles/notice.css", rel="stylesheet", type="text/css")
            book.add_item(notice_page)
            notice_pages.append(notice_page)

    epub_chapters = []
    for index, chapter_data in enumerate(chapters, start=1):
        title = chapter_data["title"]
        chapter = epub.EpubHtml(
            title=title,
            file_name=f"Text/chapter_{index:03}.xhtml",
            lang="ko",
        )
        chapter.content = f"""
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head><title>{escape(title)}</title></head>
        <body>
            {render_chapter_header(title, config["chapter_header_style"])}
            {text_to_html(
                chapter_data["content"],
                config["scene_break_style"],
                config["section_divider_style"],
                config["triple_star_style"],
                config["blank_break_style"],
            )}
        </body>
        </html>
        """
        add_stylesheet_link(chapter)
        book.add_item(chapter)
        epub_chapters.append(chapter)

    bookinfo_page = epub.EpubHtml(
        title="책정보",
        file_name="Text/bookinfo.xhtml",
        lang="ko",
    )
    bookinfo_page.content = render_template(BOOKINFO_TEMPLATE_FILE, config)
    add_stylesheet_link(bookinfo_page)
    book.add_item(bookinfo_page)

    book.toc = tuple(notice_pages + epub_chapters + [bookinfo_page])
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    front_matter = [title_page, volume_page]
    if cover_page is not None:
        front_matter.insert(0, cover_page)
    book.spine = front_matter + notice_pages + epub_chapters + [bookinfo_page]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book, {})
    return output_path


def generate_from_config(config):
    config = validate_book_config(config)
    input_path = resolve_user_path(config["input_file"])
    if not input_path.exists():
        raise ValueError(f"TXT 파일이 없습니다: {input_path}")
    if input_path.suffix.lower() != ".txt":
        raise ValueError("TXT 파일을 선택해주세요.")

    text = input_path.read_text(encoding="utf-8")
    text = mark_blank_scene_breaks(text, config["blank_break_detection"])
    processed_text = preprocess_text(text)
    chapters = split_chapters(processed_text)
    if not chapters:
        raise ValueError("챕터를 찾지 못했습니다. #제1장 형식인지 확인해주세요.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TXT.write_text(processed_text.replace(BLANK_SCENE_BREAK_MARKER, "[공백 장면전환]"), encoding="utf-8")
    output_epub = input_path.with_suffix(".epub")
    create_epub(chapters, config, output_epub)

    scene_breaks, section_dividers = count_postprocess_targets(chapters)
    return {
        "chapters": chapters,
        "scene_breaks": scene_breaks,
        "section_dividers": section_dividers,
        "blank_breaks": sum(c["content"].splitlines().count(BLANK_SCENE_BREAK_MARKER) for c in chapters),
        "output_epub": output_epub,
    }
