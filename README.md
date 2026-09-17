# EPUB Maker

TXT 소설을 전처리하고 표지, 작품/권수 페이지, 권 시작 페이지, 장별 XHTML, TOC, 책정보 페이지를 포함한 EPUB을 생성합니다.

## 실행

GUI로 실행:

```powershell
.\.venv\Scripts\python.exe gui.py
```

또는 `run_gui.bat`을 더블클릭합니다.

GUI는 CustomTkinter 기반의 좌우 2단 화면입니다. 왼쪽에서 TXT·표지·작품정보·권정보·내지 스타일을 설정하면 오른쪽 전자책 페이지에 선택한 TXT의 첫 번째 챕터 앞부분이 표시됩니다. 장면 전환과 구분선도 실제 원고의 위치에서 선택한 디자인으로 바뀝니다. `EPUB 만들기`를 누르면 TXT와 같은 폴더에 EPUB이 생성됩니다.

`내지 디자인` 영역의 드롭다운에서 챕터 헤더, 장면 전환, 구분선, 권 시작 장식을 선택할 수 있습니다. 선택값도 다른 작품 정보와 함께 자동 저장됩니다.

작품 정보의 필수값은 작품명, 원제, 저자이며 권 정보에서는 권수만 필수입니다. 한글명/별칭, 영문명, 연재처와 URL, 권 원문·번역 제목은 비워 둘 수 있습니다. 새 설정의 연재처에는 `晋江文学城`이 미리 입력되며 `초기화`를 누르면 이 값도 지워집니다.

선택한 JPG/JPEG/PNG 표지는 EPUB 내부의 `Images/cover.jpg` 또는 `Images/cover.png`로 등록됩니다. 표지 XHTML은 실제 읽기 순서의 첫 페이지이며 EPUB2 cover metadata와 guide, EPUB3 `cover-image` 속성을 함께 생성합니다.

CLI로 실행:

프로젝트 폴더에서 다음 명령을 실행합니다.

```powershell
python main.py
```

가상환경의 Python을 직접 사용할 수도 있습니다.

```powershell
.\.venv\Scripts\python.exe main.py
```

EPUB은 선택한 TXT와 같은 폴더에 같은 이름으로 저장됩니다.

- `소설 1권.txt` → `소설 1권.epub`

전처리 확인용 TXT만 프로젝트의 `output/output.txt`에 저장됩니다. EPUB 고유 식별자는 작품명, 원제, 저자, 권수를 기반으로 자동 생성되므로 직접 입력하지 않습니다.

## 프로젝트 구조

```text
main.py       CLI 진입점
gui.py        CustomTkinter 화면과 실시간 미리보기
builder.py    TXT 전처리와 EPUB 생성 엔진
config.py     설정 저장, 복원, 검증
book.json     GUI가 관리하는 최근 입력값
styles/       EPUB 내지 CSS
templates/    EPUB XHTML 템플릿
```

사용자는 Python이나 `book.json`을 직접 수정하지 않습니다. GUI 입력값은 자동 저장되며 프로그램을 다시 열면 복원됩니다. `초기화` 버튼은 저장된 입력값과 파일 선택만 기본값으로 되돌리며 원본 TXT, 표지, 생성된 EPUB은 삭제하지 않습니다. `book.json`이 없으면 기본 설정 파일을 자동 생성합니다.

실제 장으로 인식되는 기본 제목은 `#제1장`, `#제2장`, `#제3화` 형식입니다. `# 제1장 프롤로그 · 황혼 무렵`처럼 장 번호 뒤에 소제목이 있으면 소제목까지 본문 제목과 TOC에 반영됩니다. 기존 원고 호환을 위해 `# 제001장`처럼 `#` 뒤에 공백이 있거나 숫자 앞에 0이 붙은 형식도 인식합니다. `# [작품 소개]`와 일반 해시태그는 장으로 인식하지 않습니다. 한 줄 전체가 `*` 또는 `***`이면 장면 전환으로, `---`이면 구분선으로 변환됩니다.

## Sigil 후처리 자동화

EPUB을 생성할 때 다음과 같이 장별 XHTML로 변환됩니다.

```text
* 또는 ***  →  선택한 장면 전환 요소
---          →  선택한 구분선
```

앞뒤 공백은 허용하지만 기호가 한 줄 전체를 차지할 때만 변환합니다. `문장 *** 중간`, `문장---중간`, `**`는 일반 본문으로 유지합니다. 위아래 간격과 모양은 `styles/style.css`의 `.scene-break`, `.section-divider`에서 수정할 수 있습니다.

## 내지 스타일 선택

GUI의 `내지 스타일` 카드에서 챕터 헤더, 장면 전환, 구분선을 선택합니다.

기본값은 담백형, 점 3개, 짧은 얇은 선, 고전 잎 장식(❧)입니다. 장면 전환은 점 3개·작은 점·짧은 회색 실선 또는 없음 중에서 고릅니다. 권 시작 장식은 현대(•), 판타지(☾), 고전(❧), 무한류(∞), 동양풍(☯), 로맨스(❦/♥) 프리셋을 제공합니다. `subtitle`을 선택하면 `제2장 이름 없는 세계 01`을 장 번호와 부제로 위아래 분리하고, `inline`을 선택하면 두 요소를 나란히 표시합니다. 전체 제목은 TOC에 그대로 유지됩니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## EXE 패키징 준비

`epub_maker.spec`에는 CustomTkinter 리소스와 `styles/`, `templates/` 포함 설정이 들어 있습니다. 현재 Windows 빌드는 Tcl/Tk가 안정적으로 묶이는 Python 3.13 전용 빌드 환경을 사용합니다.

```powershell
py install 3.13 -y
py -3.13 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv-build\Scripts\python.exe -m PyInstaller --clean --noconfirm epub_maker.spec
```

완성 파일은 `dist\EPUB Maker.exe`입니다. EXE 옆에 최근 설정용 `book.json`이 자동 생성됩니다.
