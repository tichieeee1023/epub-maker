import copy
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

import builder
import config as settings


WORK_FIELDS = (
    ("title", "작품명 *"),
    ("original_title", "원제 *"),
    ("korean_title", "한글명 / 별칭"),
    ("english_title", "영문명"),
    ("author_korean", "저자 *"),
    ("serialization.site", "연재처"),
    ("serialization.url", "연재처 URL"),
)

VOLUME_FIELDS = (
    ("volume.number", "권수 *"),
    ("volume.original_title", "권 원문 제목"),
    ("volume.korean_title", "권 번역 제목"),
)

FIELD_SPECS = WORK_FIELDS + VOLUME_FIELDS

STYLE_SPECS = (
    (
        "chapter_header_style",
        "챕터 헤더",
        {
            "A. 담백형": "simple",
            "B. 자간 강조형": "spaced",
            "C. 부제 포함형": "subtitle",
            "D. 나란히형": "inline",
        },
    ),
    (
        "scene_break_style",
        "장면 전환",
        {
            "·  ·  ·": "dots",
            "• 작은 점": "bullet",
            "짧은 회색 실선": "short-line",
            "장식 없음": "none",
        },
    ),
    (
        "section_divider_style",
        "구분선",
        {
            "짧은 선": "short-line",
            "중간 선": "medium-line",
            "점선": "dotted",
            "이중선": "double-line",
        },
    ),
    (
        "volume_decoration_style",
        "권 시작 장식",
        {
            "• 현대 · 미니멀": "dot",
            "☾ 판타지 · 초승달": "fantasy",
            "❧ 고전 · 잎 장식": "leaf",
            "∞ 무한류 · 무한 기호": "infinite",
            "☯ 동양풍 · 태극": "oriental",
            "❦ 로맨스 · 꽃 장식": "floral",
            "♥ 로맨스 · 하트": "romance",
            "장식 없음": "none",
        },
    ),
)

COLORS = {
    "app": "#EEF0F2",
    "panel": "#F6F7F8",
    "card": "#FFFFFF",
    "preview_bg": "#E3E6E9",
    "page": "#FFFDF8",
    "border": "#D9DEE3",
    "text": "#25292D",
    "muted": "#747D86",
    "accent": "#667D91",
    "accent_hover": "#52697D",
}

FONT_FAMILY = "Malgun Gothic"


def ui_font(size=12, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def get_nested_value(config, path):
    value = config
    for key in path.split("."):
        value = value[key]
    return value


def set_nested_value(config, path, value):
    keys = path.split(".")
    target = config
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


def config_to_form_values(config):
    normalized = settings.normalize_book_config(config)
    values = {
        "input_file": normalized.get("input_file", ""),
        "cover_file": normalized.get("cover_file", ""),
    }
    for path, _label in FIELD_SPECS:
        values[path] = str(get_nested_value(normalized, path))
    for key, _label, options in STYLE_SPECS:
        selected_value = normalized[key]
        values[key] = next(
            label for label, value in options.items() if value == selected_value
        )
    return values


def form_values_to_config(values, base_config):
    config = copy.deepcopy(base_config)
    config.pop("identifier", None)
    config["input_file"] = values["input_file"].strip()
    config["cover_file"] = values["cover_file"].strip()

    for path, _label in FIELD_SPECS:
        value = values[path].strip()
        if path == "volume.number":
            if not value.isdecimal():
                raise ValueError("권 번호를 숫자로 입력해주세요.")
            value = int(value)
        set_nested_value(config, path, value)

    for key, label, options in STYLE_SPECS:
        selected_label = values[key]
        if selected_label not in options:
            raise ValueError(f"{label} 스타일을 목록에서 선택해주세요.")
        config[key] = options[selected_label]

    return settings.normalize_book_config(config)


def selected_style_value(values, key):
    for style_key, _label, options in STYLE_SPECS:
        if style_key == key:
            return options.get(values[key], next(iter(options.values())))
    raise KeyError(key)


def display_file_name(path_value, empty_text):
    path_value = path_value.strip()
    return Path(path_value).name if path_value else empty_text


def load_first_chapter_preview(path_value):
    if not path_value.strip():
        return None

    input_path = settings.resolve_user_path(path_value)
    if not input_path.exists() or input_path.suffix.lower() != ".txt":
        raise ValueError("선택한 TXT 파일을 찾을 수 없습니다.")

    text = input_path.read_text(encoding="utf-8")
    chapters = builder.split_chapters(builder.preprocess_text(text))
    if not chapters:
        raise ValueError("미리보기용 챕터를 찾지 못했습니다.")
    return chapters[0]


class ReaderPreview(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["preview_bg"], corner_radius=18)
        self.preview_values = None
        self.preview_chapter = None
        self.preview_message = "TXT를 선택하면 첫 챕터가 표시됩니다."

        ctk.CTkLabel(
            self,
            text="실시간 미리보기 · 작품/권수 중심",
            font=ui_font(15, "bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=22, pady=(18, 10))

        self.canvas = tk.Canvas(
            self,
            bg=COLORS["preview_bg"],
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.canvas.bind("<Configure>", lambda _event: self.redraw())

    def set_content(self, values, chapter=None, message=""):
        self.preview_values = values
        self.preview_chapter = chapter
        self.preview_message = message
        self.redraw()

    def redraw(self):
        if not self.preview_values:
            return

        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 360)
        height = max(canvas.winfo_height(), 560)
        gap = 16
        title_height = min(460, (height - gap - 24) * 0.72)
        header_height = min(180, height - title_height - gap - 24)
        preview_width = min(width - 28, title_height * 0.68, 390)
        left = (width - preview_width) / 2
        top = 12

        self._draw_page_frame(left, top, preview_width, title_height)
        self._draw_title_page(left, top, preview_width, title_height)

        header_top = top + title_height + gap
        self._draw_page_frame(left, header_top, preview_width, header_height)
        self._draw_chapter_header(left, header_top, preview_width, header_height)

    def _draw_page_frame(self, left, top, width, height):
        self.canvas.create_rectangle(
            left + 4,
            top + 5,
            left + width + 4,
            top + height + 5,
            fill="#CDD2D7",
            outline="",
        )
        self.canvas.create_rectangle(
            left,
            top,
            left + width,
            top + height,
            fill=COLORS["page"],
            outline=COLORS["border"],
            width=1,
        )

    def _draw_title_page(self, left, top, width, height):
        values = self.preview_values
        center_x = left + width / 2
        scale = max(0.78, min(1.0, height / 460))
        original_title = values["original_title"].strip() or "원제"
        korean_title = values["korean_title"].strip()
        work_title = values["title"].strip() or "작품명"
        english_title = values["english_title"].strip()
        volume = values["volume.number"].strip() or "1"
        author = values["author_korean"].strip() or "작가명"

        y = top + height * 0.19
        self.canvas.create_text(
            center_x,
            y,
            text=original_title,
            width=width * 0.82,
            fill="#4A4A4A",
            font=(FONT_FAMILY, round(16 * scale)),
            justify="center",
        )
        if korean_title:
            y += 29 * scale
            self.canvas.create_text(
                center_x,
                y,
                text=korean_title,
                width=width * 0.82,
                fill="#777777",
                font=(FONT_FAMILY, round(12 * scale)),
                justify="center",
            )

        y += 48 * scale
        self.canvas.create_line(
            center_x - 24 * scale,
            y,
            center_x + 24 * scale,
            y,
            fill="#AAAAAA",
        )
        y += 48 * scale
        self.canvas.create_text(
            center_x,
            y,
            text=work_title,
            width=width * 0.84,
            fill="#222222",
            font=(FONT_FAMILY, round(23 * scale), "bold"),
            justify="center",
        )
        if english_title:
            y += 34 * scale
            self.canvas.create_text(
                center_x,
                y,
                text=english_title,
                width=width * 0.82,
                fill="#777777",
                font=(FONT_FAMILY, round(10 * scale)),
                justify="center",
            )

        y += 58 * scale
        self.canvas.create_text(
            center_x,
            y,
            text=f"{volume}권",
            fill="#222222",
            font=(FONT_FAMILY, round(15 * scale), "bold"),
        )
        y += 52 * scale
        self.canvas.create_text(
            center_x,
            y,
            text=author,
            width=width * 0.82,
            fill="#555555",
            font=(FONT_FAMILY, round(12 * scale)),
            justify="center",
        )

    def _draw_chapter_header(self, left, top, width, height):
        center_x = left + width / 2
        self.canvas.create_text(
            left + 12,
            top + 13,
            text="본문 첫 페이지 · 헤더",
            anchor="w",
            fill=COLORS["muted"],
            font=(FONT_FAMILY, 9),
        )
        if self.preview_chapter is None:
            self.canvas.create_text(
                center_x,
                top + height * 0.58,
                text=self.preview_message,
                width=width * 0.78,
                fill=COLORS["muted"],
                font=(FONT_FAMILY, 9),
                justify="center",
            )
            return

        chapter_style = selected_style_value(
            self.preview_values, "chapter_header_style"
        )
        chapter_number, chapter_subtitle = builder.split_chapter_display_title(
            self.preview_chapter["title"]
        )
        if chapter_style == "spaced":
            number_match = re.fullmatch(r"제(\d+)(장|화)", chapter_number)
            if number_match:
                chapter_number = f"제 {number_match.group(1)} {number_match.group(2)}"

        y = top + 48
        title_text = chapter_number
        if chapter_style == "inline" and chapter_subtitle:
            title_text = f"{chapter_number}  {chapter_subtitle}"
        self.canvas.create_text(
            center_x,
            y,
            text=title_text,
            width=width * 0.8,
            fill=COLORS["text"],
            font=(FONT_FAMILY, 13 if chapter_style == "inline" else 15, "bold"),
            justify="center",
        )
        y += 28

        if chapter_style == "subtitle" and chapter_subtitle:
            self.canvas.create_text(
                center_x,
                y,
                text=chapter_subtitle,
                width=width * 0.8,
                fill="#596068",
                font=(FONT_FAMILY, 9),
                justify="center",
            )
            y += 36
        else:
            y += 14

        self.canvas.create_line(
            center_x - 21,
            y,
            center_x + 21,
            y,
            fill="#A8ADB2",
        )


class EpubMakerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("EPUB Maker")
        self.geometry("1100x760")
        self.minsize(920, 640)
        self.configure(fg_color=COLORS["app"])
        self.option_add("*Font", (FONT_FAMILY, 10))
        self.grid_columnconfigure(0, weight=11)
        self.grid_columnconfigure(1, weight=9)
        self.grid_rowconfigure(0, weight=1)

        try:
            self.base_config = settings.load_book_config()
        except (ValueError, OSError) as error:
            messagebox.showwarning(
                "설정 불러오기",
                f"최근 설정을 불러오지 못했습니다. 기본값으로 시작합니다.\n\n{error}",
                parent=self,
            )
            self.base_config = settings.default_book_config()

        initial_values = config_to_form_values(self.base_config)
        self.variables = {
            key: tk.StringVar(master=self, value=value)
            for key, value in initial_values.items()
        }
        self.status_variable = tk.StringVar(master=self, value="최근 입력값을 불러왔습니다.")
        self.file_display_variables = {
            "input_file": tk.StringVar(master=self),
            "cover_file": tk.StringVar(master=self),
        }
        self.autosave_job = None
        self.preview_source_path = None
        self.preview_chapter = None
        self.preview_message = "TXT를 선택하면 첫 챕터가 표시됩니다."
        self._update_file_labels()

        self._build_left_panel()
        self.preview = ReaderPreview(self)
        self.preview.grid(row=0, column=1, sticky="nsew", padx=(6, 18), pady=18)

        for variable in self.variables.values():
            variable.trace_add("write", self._on_value_changed)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._update_preview)

    def _build_left_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=18)
        panel.grid(row=0, column=0, sticky="nsew", padx=(18, 6), pady=18)
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 12))
        ctk.CTkLabel(
            header,
            text="EPUB Maker",
            font=ui_font(24, "bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="TXT와 표지를 선택하고 내지 디자인을 완성하세요.",
            font=ui_font(12),
            text_color=COLORS["muted"],
        ).pack(anchor="w", pady=(4, 0))

        scroll = ctk.CTkScrollableFrame(
            panel,
            fg_color="transparent",
            corner_radius=0,
        )
        scroll.grid(row=1, column=0, sticky="nsew", padx=14)
        scroll.grid_columnconfigure(0, weight=1)

        self._build_fields_card(scroll, 0, "작품 정보", WORK_FIELDS)
        self._build_fields_card(scroll, 1, "권 정보", VOLUME_FIELDS)
        self._build_files_card(scroll, 2)
        self._build_styles_card(scroll, 3)

        action = ctk.CTkFrame(panel, fg_color="transparent")
        action.grid(row=2, column=0, sticky="ew", padx=22, pady=(12, 20))
        action.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(
            action,
            text="초기화",
            width=94,
            height=46,
            corner_radius=12,
            fg_color="#E3E7EA",
            hover_color="#D5DBE0",
            text_color=COLORS["text"],
            font=ui_font(13, "bold"),
            command=self._reset_settings,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(
            action,
            text="EPUB 만들기",
            height=46,
            corner_radius=12,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            font=ui_font(15, "bold"),
            command=self._generate_epub,
        ).grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(
            action,
            textvariable=self.status_variable,
            text_color=COLORS["muted"],
            font=ui_font(11),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _card(self, parent, row, title):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=row, column=0, sticky="ew", padx=4, pady=(0, 12))
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            card,
            text=title,
            font=ui_font(14, "bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 8))
        return card

    def _build_fields_card(self, parent, row, title, fields):
        card = self._card(parent, row, title)
        for field_row, (path, label) in enumerate(fields, start=1):
            ctk.CTkLabel(
                card,
                text=label,
                width=108,
                anchor="w",
                text_color=COLORS["muted"],
                font=ui_font(12),
            ).grid(row=field_row, column=0, sticky="w", padx=(16, 8), pady=5)
            ctk.CTkEntry(
                card,
                textvariable=self.variables[path],
                height=34,
                corner_radius=8,
                border_color=COLORS["border"],
                font=ui_font(12),
            ).grid(row=field_row, column=1, sticky="ew", padx=(0, 16), pady=5)
        ctk.CTkLabel(card, text="").grid(
            row=len(fields) + 1,
            column=0,
            pady=2,
        )

    def _build_files_card(self, parent, row):
        card = self._card(parent, row, "파일 선택")
        file_rows = (
            ("input_file", "TXT 파일 선택", self._select_txt),
            ("cover_file", "표지 이미지 선택", self._select_cover),
        )
        for file_row, (key, label, command) in enumerate(file_rows, start=1):
            ctk.CTkButton(
                card,
                text=label,
                width=132,
                height=34,
                corner_radius=8,
                fg_color="#E8EDF1",
                hover_color="#DCE4EA",
                text_color=COLORS["text"],
                font=ui_font(12),
                command=command,
            ).grid(row=file_row, column=0, padx=(16, 10), pady=6)
            ctk.CTkLabel(
                card,
                textvariable=self.file_display_variables[key],
                anchor="w",
                text_color=COLORS["muted"],
                font=ui_font(11),
            ).grid(row=file_row, column=1, sticky="ew", padx=(0, 16), pady=6)
        ctk.CTkLabel(card, text="").grid(row=3, column=0, pady=2)

    def _build_styles_card(self, parent, row):
        card = self._card(parent, row, "내지 스타일")
        for style_row, (key, label, options) in enumerate(STYLE_SPECS, start=1):
            ctk.CTkLabel(
                card,
                text=label,
                width=108,
                anchor="w",
                text_color=COLORS["muted"],
                font=ui_font(12),
            ).grid(row=style_row, column=0, sticky="w", padx=(16, 8), pady=6)
            ctk.CTkOptionMenu(
                card,
                variable=self.variables[key],
                values=tuple(options.keys()),
                height=34,
                corner_radius=8,
                fg_color="#E8EDF1",
                button_color="#D3DDE5",
                button_hover_color="#C4D1DB",
                text_color=COLORS["text"],
                dropdown_fg_color=COLORS["card"],
                font=ui_font(12),
                dropdown_font=ui_font(12),
            ).grid(row=style_row, column=1, sticky="ew", padx=(0, 16), pady=6)
        ctk.CTkLabel(card, text="").grid(row=len(STYLE_SPECS) + 1, column=0, pady=2)

    def _select_txt(self):
        selected = filedialog.askopenfilename(
            parent=self,
            title="TXT 원고 선택",
            filetypes=(("텍스트 파일", "*.txt"),),
        )
        if selected:
            self.variables["input_file"].set(selected)

    def _select_cover(self):
        selected = filedialog.askopenfilename(
            parent=self,
            title="표지 이미지 선택",
            filetypes=(
                ("표지 이미지", "*.jpg *.jpeg *.png"),
                ("JPG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
            ),
        )
        if selected:
            self.variables["cover_file"].set(selected)

    def _form_values(self):
        return {key: variable.get() for key, variable in self.variables.items()}

    def _current_config(self):
        return form_values_to_config(self._form_values(), self.base_config)

    def _on_value_changed(self, *_args):
        self._update_file_labels()
        self._update_preview()
        if self.autosave_job is not None:
            self.after_cancel(self.autosave_job)
        self.autosave_job = self.after(500, self._autosave)

    def _update_file_labels(self):
        self.file_display_variables["input_file"].set(
            display_file_name(
                self.variables["input_file"].get(),
                "TXT 파일을 선택해주세요.",
            )
        )
        self.file_display_variables["cover_file"].set(
            display_file_name(
                self.variables["cover_file"].get(),
                "표지 없이 생성",
            )
        )

    def _update_preview(self):
        if not hasattr(self, "preview"):
            return

        path_value = self.variables["input_file"].get().strip()
        if path_value != self.preview_source_path:
            self.preview_source_path = path_value
            try:
                self.preview_chapter = load_first_chapter_preview(path_value)
                self.preview_message = (
                    "" if self.preview_chapter else "TXT를 선택하면 첫 챕터가 표시됩니다."
                )
            except (ValueError, OSError, UnicodeError) as error:
                self.preview_chapter = None
                self.preview_message = str(error)

        self.preview.set_content(
            self._form_values(),
            self.preview_chapter,
            self.preview_message,
        )

    def _reset_settings(self):
        confirmed = messagebox.askyesno(
            "설정 초기화",
            "입력한 작품 정보와 최근 파일 선택을 초기화할까요?\n\n"
            "원본 TXT, 표지 이미지, 생성한 EPUB 파일은 삭제되지 않습니다.",
            parent=self,
        )
        if not confirmed:
            return

        defaults = settings.reset_book_config()
        default_values = config_to_form_values(defaults)
        self.base_config = defaults
        for key, value in default_values.items():
            self.variables[key].set(value)
        self.base_config = settings.save_book_config(defaults)
        self.status_variable.set("설정을 초기화했습니다.")

    def _autosave(self):
        self.autosave_job = None
        try:
            config = self._current_config()
            self.base_config = settings.save_book_config(config)
            self.status_variable.set("입력값이 자동 저장되었습니다.")
        except (ValueError, OSError):
            self.status_variable.set("입력 중입니다. 완성된 값부터 자동 저장됩니다.")

    def _generate_epub(self):
        try:
            config = self._current_config()
            config = settings.validate_book_config(config)
            self.base_config = settings.save_book_config(config)
            result = builder.generate_from_config(config)
        except (ValueError, OSError, UnicodeError) as error:
            messagebox.showerror("EPUB 생성 실패", str(error), parent=self)
            self.status_variable.set("입력값과 선택한 파일을 확인해주세요.")
            return
        except Exception as error:
            messagebox.showerror(
                "EPUB 생성 실패",
                f"EPUB 생성 중 오류가 발생했습니다.\n\n{error}",
                parent=self,
            )
            self.status_variable.set("EPUB 생성 중 오류가 발생했습니다.")
            return

        output_path = Path(result["output_epub"])
        message = (
            "EPUB 생성 완료\n\n"
            f"챕터 {len(result['chapters'])}개 · "
            f"장면 전환 {result['scene_breaks']}개 · "
            f"구분선 {result['section_dividers']}개\n\n"
            f"{output_path}"
        )
        self.status_variable.set(f"완료: {output_path.name}")
        messagebox.showinfo("EPUB 생성 완료", message, parent=self)

    def _on_close(self):
        if self.autosave_job is not None:
            self.after_cancel(self.autosave_job)
        self._autosave()
        self.destroy()


def main():
    app = EpubMakerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
