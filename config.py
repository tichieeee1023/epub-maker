import copy
import json
import sys
import uuid
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else SOURCE_DIR
BOOK_CONFIG_FILE = APP_DIR / "book.json"

DEFAULT_CHAPTER_HEADER_STYLE = "simple"
DEFAULT_SCENE_BREAK_STYLE = "dots"
DEFAULT_SECTION_DIVIDER_STYLE = "short-line"
DEFAULT_VOLUME_DECORATION_STYLE = "leaf"
CHAPTER_HEADER_STYLES = {"simple", "spaced", "subtitle", "inline"}
SCENE_BREAK_STYLES = {
    "dots": "·  ·  ·",
    "bullet": "•",
    "short-line": "\u00a0",
    "none": "\u00a0",
}
SECTION_DIVIDER_STYLES = {"short-line", "medium-line", "dotted", "double-line"}
VOLUME_DECORATIONS = {
    "leaf": "❧",
    "floral": "❦",
    "dot": "•",
    "fantasy": "☾",
    "infinite": "∞",
    "oriental": "☯︎",
    "romance": "♥︎",
    "none": "\u00a0",
}

DEFAULT_CONFIG = {
    "input_file": "",
    "cover_file": "",
    "include_translation_notice": True,
    "include_reader_notice": True,
    "chapter_header_style": DEFAULT_CHAPTER_HEADER_STYLE,
    "scene_break_style": DEFAULT_SCENE_BREAK_STYLE,
    "section_divider_style": DEFAULT_SECTION_DIVIDER_STYLE,
    "volume_decoration_style": DEFAULT_VOLUME_DECORATION_STYLE,
    "title": "",
    "original_title": "",
    "korean_title": "",
    "english_title": "",
    "author_korean": "",
    "volume": {
        "number": 1,
        "original_title": "",
        "korean_title": "",
    },
    "serialization": {
        "site": "晋江文学城",
        "url": "",
    },
}


def default_book_config():
    return copy.deepcopy(DEFAULT_CONFIG)


def reset_book_config():
    """Return cleared GUI values while keeping normal first-run defaults separate."""
    config = default_book_config()
    config["serialization"]["site"] = ""
    return config


def nested_value(config, path):
    value = config
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"book.json 필수 항목이 없습니다: {path}")
        value = value[key]
    return value


def merge_defaults(config, defaults=None):
    defaults = default_book_config() if defaults is None else defaults
    merged = copy.deepcopy(defaults)

    for key, value in config.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_defaults(value, merged[key])
        else:
            merged[key] = value

    merged.pop("identifier", None)
    # Remove the deleted legacy field when an older book.json is loaded.
    merged.pop("author_original", None)
    return merged


def normalize_book_config(config):
    if not isinstance(config, dict):
        raise ValueError("book.json의 최상위 값은 객체여야 합니다.")

    normalized = merge_defaults(config)
    # 기존 설정의 최소형은 제거된 스타일이므로 가장 가까운 담백형으로 이전한다.
    if normalized["chapter_header_style"] == "minimal":
        normalized["chapter_header_style"] = DEFAULT_CHAPTER_HEADER_STYLE
    if normalized["scene_break_style"] == "diamond":
        normalized["scene_break_style"] = DEFAULT_SCENE_BREAK_STYLE
    if normalized["scene_break_style"] == "asterisks":
        normalized["scene_break_style"] = "short-line"
    if normalized["volume_decoration_style"] in {"diamond", "sparkle"}:
        normalized["volume_decoration_style"] = DEFAULT_VOLUME_DECORATION_STYLE
    if normalized["volume_decoration_style"] == "asterisk":
        normalized["volume_decoration_style"] = "dot"
    if normalized["chapter_header_style"] not in CHAPTER_HEADER_STYLES:
        raise ValueError("챕터 헤더 스타일을 목록에서 선택해주세요.")
    if normalized["scene_break_style"] not in SCENE_BREAK_STYLES:
        raise ValueError("장면 전환 스타일을 목록에서 선택해주세요.")
    if normalized["section_divider_style"] not in SECTION_DIVIDER_STYLES:
        raise ValueError("구분선 스타일을 목록에서 선택해주세요.")
    if normalized["volume_decoration_style"] not in VOLUME_DECORATIONS:
        raise ValueError("권 시작 장식을 목록에서 선택해주세요.")
    for key in ("include_translation_notice", "include_reader_notice"):
        if not isinstance(normalized[key], bool):
            raise ValueError("안내 페이지 설정은 참/거짓 값이어야 합니다.")
    return normalized


def validate_book_config(config):
    validated = normalize_book_config(config)

    required_text_fields = (
        ("title", "작품명을 입력해주세요."),
        ("original_title", "원제를 입력해주세요."),
        ("author_korean", "저자를 입력해주세요."),
    )
    for path, message in required_text_fields:
        value = nested_value(validated, path)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(message)

    volume_number = nested_value(validated, "volume.number")
    if isinstance(volume_number, bool) or not isinstance(volume_number, int):
        raise ValueError("권 번호를 숫자로 입력해주세요.")
    if volume_number < 1:
        raise ValueError("권 번호는 1 이상이어야 합니다.")

    if not isinstance(validated["serialization"]["url"], str):
        raise ValueError("연재처 URL을 확인해주세요.")
    if not isinstance(validated["input_file"], str) or not validated["input_file"].strip():
        raise ValueError("TXT 파일을 선택해주세요.")
    if not isinstance(validated["cover_file"], str):
        raise ValueError("표지 이미지 경로를 확인해주세요.")

    return validated


def create_book_identifier(config):
    identity_source = "|".join(
        (
            config["title"].strip(),
            config["original_title"].strip(),
            config["author_korean"].strip(),
            str(config["volume"]["number"]),
        )
    )
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, identity_source)}"


def load_book_config(config_path=BOOK_CONFIG_FILE):
    if not config_path.exists():
        config = default_book_config()
        save_book_config(config, config_path)
        return config

    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"설정 파일 문법 오류: {error.lineno}행 {error.colno}열"
        ) from error

    return normalize_book_config(raw_config)


def save_book_config(config, config_path=BOOK_CONFIG_FILE):
    normalized = normalize_book_config(config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized


def resolve_user_path(path_value):
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else APP_DIR / path
