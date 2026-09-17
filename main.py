"""CLI entrypoint and backward-compatible public API for EPUB Maker."""

from builder import (
    OUTPUT_DIR,
    OUTPUT_EPUB,
    OUTPUT_TXT,
    SECTION_DIVIDER_MARKER,
    SCENE_BREAK_MARKERS,
    count_postprocess_targets,
    create_cover_page,
    create_epub,
    generate_from_config,
    preprocess_text,
    render_chapter_header,
    split_chapter_display_title,
    split_chapters,
    text_to_html,
    validate_cover_file,
)
from config import (
    BOOK_CONFIG_FILE,
    CHAPTER_HEADER_STYLES,
    DEFAULT_CHAPTER_HEADER_STYLE,
    DEFAULT_SCENE_BREAK_STYLE,
    DEFAULT_SECTION_DIVIDER_STYLE,
    DEFAULT_VOLUME_DECORATION_STYLE,
    SCENE_BREAK_STYLES,
    SECTION_DIVIDER_STYLES,
    VOLUME_DECORATIONS,
    create_book_identifier,
    default_book_config,
    load_book_config,
    normalize_book_config,
    reset_book_config,
    resolve_user_path,
    save_book_config,
    validate_book_config,
)


def main():
    try:
        config = load_book_config()
        result = generate_from_config(config)
    except (ValueError, OSError, UnicodeError) as error:
        print(error)
        return

    chapters = result["chapters"]
    print(f"감지된 챕터: {len(chapters)}개")
    for index, chapter in enumerate(chapters, start=1):
        print(f"{index}. {chapter['title']}")

    print(f'장면 전환 자동 변환: {result["scene_breaks"]}개')
    print(f'구분선 자동 변환: {result["section_dividers"]}개')
    print()
    print("EPUB 생성 완료!")
    print(f'{result["output_epub"]} 파일을 확인하세요.')


if __name__ == "__main__":
    main()
