from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from generate_text_program_docx import (
    add_change_log_page,
    add_heading,
    add_page_break,
    add_paragraph,
    add_toc,
    configure_document,
    set_run_font,
    set_table_borders,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "docs" / "RO_komarov.docx"
SCREENSHOTS_DIR = ROOT / "docs" / "screenshots"

PROGRAM_NAME_RU = (
    "Веб-приложение для проектирования пожарной сигнализации и автоматического "
    "формирования проектной документации"
)
PROGRAM_NAME_EN = (
    "Web Application for Fire Alarm Design and Automatic Generation of Design Documentation"
)
PROGRAM_SHORT_NAME = "PlanVision"
DOCUMENT_CODE_APPROVAL = "RU.17701729.08.03-01 34 01-1-ЛУ"
DOCUMENT_CODE_MAIN = "RU.17701729.08.03-01 34 01-1"
CITY_AND_YEAR = "Москва 2026"
STUDENT_GROUP = "БПИ225"
STUDENT_NAME = "М. С. Комаров"

SCREENSHOT_SPECS = {
    "login": {
        "path": SCREENSHOTS_DIR / "01_login.png",
        "caption": "Рисунок 1 – Страница авторизации",
        "width_cm": 12.0,
    },
    "projects": {
        "path": SCREENSHOTS_DIR / "02_projects.png",
        "caption": "Рисунок 2 – Страница списка проектов",
        "width_cm": 15.5,
    },
    "create_project": {
        "path": SCREENSHOTS_DIR / "03_create_project.png",
        "caption": "Рисунок 3 – Страница создания проекта",
        "width_cm": 11.5,
    },
    "equipment_catalog": {
        "path": SCREENSHOTS_DIR / "04_equipment_catalog.png",
        "caption": "Рисунок 4 – Страница каталога оборудования",
        "width_cm": 15.5,
    },
    "recognition_training": {
        "path": SCREENSHOTS_DIR / "05_recognition_training_crop.png",
        "caption": "Рисунок 5 – Страница центра дообучения распознавания",
        "width_cm": 14.5,
    },
    "users": {
        "path": SCREENSHOTS_DIR / "06_users.png",
        "caption": "Рисунок 6 – Страница управления пользователями",
        "width_cm": 15.0,
    },
    "project_detail": {
        "path": SCREENSHOTS_DIR / "07_project_detail.png",
        "caption": "Рисунок 7 – Страница карточки проекта",
        "width_cm": 10.5,
    },
    "floor_plan_editor": {
        "path": SCREENSHOTS_DIR / "08_floor_plan_editor.png",
        "caption": "Рисунок 8 – Страница редактора плана этажа",
        "width_cm": 15.5,
    },
}


def add_bullet(doc: Document, text: str):
    paragraph = add_paragraph(
        doc,
        f"• {text}",
        first_line_indent_cm=None,
        line_spacing=1.5,
    )
    paragraph.paragraph_format.left_indent = Pt(21)
    paragraph.paragraph_format.first_line_indent = Pt(-14)
    return paragraph


def add_screenshot(doc: Document, screenshot_key: str):
    spec = SCREENSHOT_SPECS.get(screenshot_key)
    if not spec:
        return
    image_path = spec["path"]
    if not image_path.exists():
        return

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(6)
    run = paragraph.add_run()
    run.add_picture(str(image_path), width=Cm(spec["width_cm"]))

    caption = doc.add_paragraph()
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.first_line_indent = None
    caption.paragraph_format.line_spacing = 1.0
    caption.paragraph_format.space_before = Pt(0)
    caption.paragraph_format.space_after = Pt(6)
    caption_run = caption.add_run(spec["caption"])
    set_run_font(caption_run, size=12, italic=True)


def add_approval_page(doc: Document):
    add_paragraph(doc, CITY_AND_YEAR, align=WD_ALIGN_PARAGRAPH.RIGHT, first_line_indent_cm=None)
    add_paragraph(
        doc,
        "ПРАВИТЕЛЬСТВО РОССИЙСКОЙ ФЕДЕРАЦИИ",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        first_line_indent_cm=None,
    )
    add_paragraph(
        doc,
        "ФЕДЕРАЛЬНОЕ ГОСУДАРСТВЕННОЕ АВТОНОМНОЕ ОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        first_line_indent_cm=None,
    )
    add_paragraph(
        doc,
        "ВЫСШЕГО ОБРАЗОВАНИЯ",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        first_line_indent_cm=None,
    )
    add_paragraph(
        doc,
        "«НАЦИОНАЛЬНЫЙ ИССЛЕДОВАТЕЛЬСКИЙ УНИВЕРСИТЕТ",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        first_line_indent_cm=None,
    )
    add_paragraph(
        doc,
        "«ВЫСШАЯ ШКОЛА ЭКОНОМИКИ»",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        first_line_indent_cm=None,
    )
    add_paragraph(doc, "", first_line_indent_cm=None)
    add_paragraph(doc, "Факультет компьютерных наук", align=WD_ALIGN_PARAGRAPH.CENTER, first_line_indent_cm=None)
    add_paragraph(
        doc,
        "Образовательная программа «Программная инженерия»",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        first_line_indent_cm=None,
    )

    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table, visible=False)
    left = table.cell(0, 0)
    right = table.cell(0, 1)
    left.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    right.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

    left.text = ""
    p = left.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run("СОГЛАСОВАНО")
    set_run_font(r, size=14, bold=True)
    for line in (
        "Руководитель выпускной квалификационной работы",
        "___________________ / __________________ /",
        "«___» _____________ 2026 г.",
    ):
        q = left.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.LEFT
        rr = q.add_run(line)
        set_run_font(rr, size=14)

    right.text = ""
    p = right.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run("УТВЕРЖДАЮ")
    set_run_font(r, size=14, bold=True)
    for line in (
        "Академический руководитель образовательной программы",
        "«Программная инженерия»",
        "___________________ / __________________ /",
        "«___» _____________ 2026 г.",
    ):
        q = right.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.LEFT
        rr = q.add_run(line)
        set_run_font(rr, size=14)

    for _ in range(6):
        add_paragraph(doc, "", first_line_indent_cm=None)

    add_paragraph(
        doc,
        PROGRAM_NAME_RU,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        first_line_indent_cm=None,
        uppercase=True,
    )
    add_paragraph(doc, "Руководство оператора", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, first_line_indent_cm=None)
    add_paragraph(doc, "ЛИСТ УТВЕРЖДЕНИЯ", align=WD_ALIGN_PARAGRAPH.CENTER, first_line_indent_cm=None)
    add_paragraph(doc, DOCUMENT_CODE_APPROVAL, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, first_line_indent_cm=None)
    add_paragraph(doc, "", first_line_indent_cm=None)
    add_paragraph(doc, "Исполнитель", align=WD_ALIGN_PARAGRAPH.LEFT, first_line_indent_cm=None)
    add_paragraph(
        doc,
        f"Студент группы {STUDENT_GROUP}                     ___________ / {STUDENT_NAME} /",
        align=WD_ALIGN_PARAGRAPH.LEFT,
        first_line_indent_cm=None,
    )
    add_paragraph(doc, "«___» _____________ 2026 г.", align=WD_ALIGN_PARAGRAPH.LEFT, first_line_indent_cm=None)


def add_title_page(doc: Document):
    add_paragraph(doc, CITY_AND_YEAR, align=WD_ALIGN_PARAGRAPH.RIGHT, first_line_indent_cm=None)
    add_paragraph(doc, "", first_line_indent_cm=None)
    add_paragraph(
        doc,
        f"УТВЕРЖДЕН    {DOCUMENT_CODE_APPROVAL}",
        align=WD_ALIGN_PARAGRAPH.LEFT,
        bold=True,
        first_line_indent_cm=None,
    )
    add_paragraph(doc, "", first_line_indent_cm=None)
    add_paragraph(
        doc,
        PROGRAM_NAME_RU,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        first_line_indent_cm=None,
        uppercase=True,
    )
    add_paragraph(doc, "Руководство оператора", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, first_line_indent_cm=None)
    add_paragraph(doc, DOCUMENT_CODE_MAIN, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, first_line_indent_cm=None)
    add_paragraph(doc, "Листов ____", align=WD_ALIGN_PARAGRAPH.CENTER, first_line_indent_cm=None)


def add_purpose_section(doc: Document):
    add_heading(doc, "1 НАЗНАЧЕНИЕ ПРОГРАММЫ")
    add_heading(doc, "1.1 Наименование программы")
    add_paragraph(doc, f"Наименование программы – «{PROGRAM_NAME_RU}».")
    add_paragraph(doc, f"Наименование программы на английском языке – «{PROGRAM_NAME_EN}».")
    add_paragraph(doc, f"Краткое наименование программы – «{PROGRAM_SHORT_NAME}».")

    add_heading(doc, "1.2 Краткая характеристика области применения программы")
    add_paragraph(
        doc,
        "Программа предназначена для автоматизации проектирования систем пожарной "
        "сигнализации и связанных подсистем на основе поэтажных планов зданий. "
        "Она используется для ведения карточек проектов, загрузки планов этажей, "
        "автоматического и полуавтоматического распознавания архитектурных элементов, "
        "размещения инженерного оборудования и формирования итоговой проектной документации.",
    )
    add_paragraph(
        doc,
        "С точки зрения оператора программа представляет собой веб-приложение с "
        "авторизацией пользователей и ролевым разграничением доступа. После входа "
        "пользователь получает доступ к рабочему пространству проекта, где может создавать "
        "новые проекты, редактировать информацию об объекте, загружать планы этажей, "
        "выполнять шаги pipeline, работать с каталогом оборудования и генерировать PDF-комплект.",
    )
    add_paragraph(
        doc,
        "Программа ориентирована на инженеров-проектировщиков, преподавателей и студентов, "
        "работающих с проектной документацией по системам пожарной защиты. Для пользователя "
        "с ролью developer дополнительно доступны функции управления учетными записями и "
        "центр дообучения распознавания.",
    )


def add_execution_conditions(doc: Document):
    add_heading(doc, "2 УСЛОВИЯ ВЫПОЛНЕНИЯ ПРОГРАММЫ")
    add_heading(doc, "2.1 Рекомендуемый состав аппаратурных и программных средств в среде для локальной разработки, демонстрации и тестирования")
    add_paragraph(
        doc,
        "Для устойчивой работы программы рекомендуется использовать персональный компьютер "
        "или ноутбук, удовлетворяющий следующим требованиям:",
    )
    add_bullet(doc, "операционная система Windows 10/11, Ubuntu 22.04+ или macOS 12+;")
    add_bullet(doc, "не менее 4 логических ядер процессора;")
    add_bullet(doc, "оперативная память не менее 8 ГБ;")
    add_bullet(doc, "свободное место на диске не менее 10 ГБ;")
    add_bullet(doc, "разрешение экрана не менее 1920×1080;")
    add_bullet(doc, "установленный Python 3.12 или совместимая версия Python 3.11+;")
    add_bullet(doc, "установленный Node.js 16+ и пакетный менеджер npm;")
    add_bullet(doc, "современный браузер Google Chrome, Microsoft Edge или Mozilla Firefox;")
    add_bullet(doc, "установленный Tesseract OCR для сценариев, связанных с распознаванием размерных подписей;")
    add_bullet(doc, "доступ к файловой системе для чтения и сохранения изображений, PDF и служебных файлов проекта.")
    add_paragraph(
        doc,
        "В рекомендованном сценарии backend запускается локально на порту 8000, а "
        "frontend – на порту 3000. Для работы OCR и PDF-генерации в корне проекта должны "
        "сохраняться файлы шрифтов GOST_A.TTF и GOST_A_Bold.ttf, уже входящие в состав репозитория.",
    )

    add_heading(doc, "2.2 Минимальный состав аппаратурных и программных средств в эксплуатационной среде")
    add_paragraph(
        doc,
        "Минимально достаточный эксплуатационный контур для текущей версии программы может "
        "быть развернут на одной рабочей станции без выделенной внешней СУБД. Достаточны "
        "следующие ресурсы и программные средства:",
    )
    add_bullet(doc, "операционная система Windows 10/11, Linux или macOS;")
    add_bullet(doc, "2 логических ядра процессора;")
    add_bullet(doc, "оперативная память не менее 4 ГБ;")
    add_bullet(doc, "свободное место на диске не менее 5 ГБ;")
    add_bullet(doc, "Python 3.11+, Node.js 16+, npm и современный браузер;")
    add_bullet(doc, "локальная база данных SQLite, создаваемая программой автоматически;")
    add_bullet(doc, "Tesseract OCR – при необходимости использования функций OCR и автоматического распознавания размеров.")
    add_paragraph(
        doc,
        "Отдельная промышленная схема развёртывания в репозитории на текущий момент не "
        "фиксируется. Поэтому для демонстрационной и учебной эксплуатации в настоящем "
        "документе в качестве минимальной среды рассматривается локальный одноузловой "
        "контур, поддерживаемый проектом непосредственно.",
    )


def add_execution_section(doc: Document):
    add_heading(doc, "3 ВЫПОЛНЕНИЕ ПРОГРАММЫ")

    add_heading(doc, "3.1 Подготовка к первому запуску")
    add_paragraph(
        doc,
        "Перед первым запуском оператор или сопровождающий специалист должен развернуть "
        "зависимости backend и frontend. В корневой директории проекта выполняются "
        "следующие действия:",
    )
    add_bullet(doc, "создание виртуального окружения командой `python -m venv venv`;")
    add_bullet(doc, "активация окружения в Windows командой `venv\\Scripts\\activate`;")
    add_bullet(doc, "переход в каталог `backend` и установка серверных зависимостей командой `pip install -r requirements.txt`;")
    add_bullet(doc, "переход в каталог `frontend` и установка клиентских зависимостей командой `npm install`;")
    add_bullet(doc, "при необходимости OCR – установка Tesseract OCR и настройка пути к исполняемому файлу;")
    add_bullet(doc, "подготовка файла `.env` на основе `.env.example` с указанием учетных данных первого разработчика.")
    add_paragraph(
        doc,
        "В файле `.env` задаются значения `BOOTSTRAP_DEVELOPER_USERNAME`, "
        "`BOOTSTRAP_DEVELOPER_FULL_NAME` и `BOOTSTRAP_DEVELOPER_PASSWORD`. "
        "При первом старте backend эти данные используются для автоматического создания "
        "первой учетной записи с ролью developer.",
    )

    add_heading(doc, "3.2 Порядок запуска серверной и клиентской частей")
    add_paragraph(
        doc,
        "Для запуска серверной части оператор из корня проекта выполняет команду "
        "`python main.py`. После старта приложение поднимает HTTP-сервис по адресу "
        "`http://localhost:8000`, инициализирует базу данных, создает рабочие каталоги "
        "`uploads`, `outputs` и `debug_output`, а также выполняет bootstrap первого "
        "разработчика, если в системе еще нет пользователей.",
    )
    add_paragraph(
        doc,
        "Для запуска клиентской части оператор переходит в каталог `frontend` и "
        "выполняет команду `npm start`. После сборки development-окружения приложение "
        "становится доступным по адресу `http://localhost:3000` и использует backend API "
        "на порту 8000 через прокси или прямые HTTP-запросы.",
    )
    add_paragraph(
        doc,
        "Для проверки работоспособности API можно дополнительно открыть адрес "
        "`http://localhost:8000/docs`, где автоматически формируется интерактивная "
        "OpenAPI-документация. Ее удобно использовать для диагностики, однако обычная "
        "эксплуатация программы осуществляется через web-интерфейс клиента.",
    )

    add_heading(doc, "3.3 Вход в систему и рабочая навигация")
    add_paragraph(
        doc,
        "Если сессия отсутствует, пользователь автоматически перенаправляется на страницу "
        "входа `/login`. На ней требуется указать логин и пароль. После успешной авторизации "
        "система открывает главное рабочее пространство и показывает краткое сообщение о "
        "начале сессии.",
    )
    add_paragraph(
        doc,
        "Состав навигационного меню зависит от роли пользователя. Для инженера доступны "
        "разделы «Проекты», «Новый проект» и «Оборудование». Для разработчика дополнительно "
        "открываются разделы «Дообучение» и «Пользователи». В правой части панели навигации "
        "показываются полное имя пользователя, его роль и кнопка завершения сессии.",
    )
    add_screenshot(doc, "login")

    add_heading(doc, "3.4 Создание проекта и работа с карточкой проекта")
    add_paragraph(
        doc,
        "Для создания нового проекта оператор выбирает пункт «Новый проект» и заполняет "
        "форму, включающую сведения об объекте, типе проекта, адресе, подрядчике, инженере "
        "и других реквизитах. После сохранения система создает карточку проекта и "
        "перенаправляет пользователя на страницу детальной работы с ним.",
    )
    add_paragraph(
        doc,
        "На странице проекта оператор может редактировать основные реквизиты, просматривать "
        "список этажей, загружать новые планы, переходить к вспомогательным разделам "
        "документации и запускать формирование PDF-комплекта. Для разработчика дополнительно "
        "может быть доступно назначение владельца проекта из числа активных инженеров.",
    )
    add_screenshot(doc, "projects")
    add_screenshot(doc, "create_project")
    add_screenshot(doc, "project_detail")

    add_heading(doc, "3.5 Загрузка плана этажа")
    add_paragraph(
        doc,
        "Добавление плана этажа выполняется на странице проекта кнопкой загрузки плана. "
        "Текущий интерфейс проверяет, что загружаемый файл является изображением и имеет "
        "размер не менее 200×200 пикселей. При нарушении этих условий оператор получает "
        "сообщение о невозможности загрузки файла.",
    )
    add_paragraph(
        doc,
        "При создании плана система сохраняет номер этажа, название, масштабный коэффициент, "
        "высоту помещений и файл исходного изображения. После успешной загрузки оператор "
        "может открыть план в редакторе для детальной работы.",
    )

    add_heading(doc, "3.6 Работа в редакторе плана и выполнение шагов pipeline")
    add_paragraph(
        doc,
        "Редактор плана является основной рабочей страницей программы. В нем оператор "
        "может просматривать исходное изображение, масштабировать холст, выбирать и "
        "перемещать графические элементы, добавлять стены, двери, окна, помещения, "
        "извещатели, устройства СОУЭ, приборы и кабельные трассы.",
    )
    add_paragraph(
        doc,
        "В редакторе поддерживается пошаговый pipeline обработки плана. В общем сценарии "
        "оператор может инициировать распознавание стен, затем проемов, затем помещений и "
        "других связанных сущностей, проверять результаты, вносить корректировки и "
        "подтверждать шаги. После подтверждения данные сохраняются на backend и становятся "
        "частью общего состояния проекта.",
    )
    add_paragraph(
        doc,
        "Для ускорения работы доступны клавиатурные команды. В частности, Shift помогает "
        "ограничивать углы рисования стен, Ctrl+Z используется для отмены, Delete – для "
        "удаления выбранного элемента, а Ctrl+S – для сохранения изменений. При работе "
        "с проектными документами оператор также может открывать предварительные просмотры "
        "общих данных, общих указаний, спецификации, расчета токопотребления и "
        "дополнительных сведений.",
    )
    add_screenshot(doc, "floor_plan_editor")

    add_heading(doc, "3.7 Работа с каталогом оборудования и проектными привязками")
    add_paragraph(
        doc,
        "Раздел «Оборудование» предназначен для ведения каталога изделий, используемых при "
        "проектировании. Оператор может создавать карточки оборудования, изменять их "
        "параметры, загружать изображения, паспортные PDF-файлы и ярлыки, а также удалять "
        "позиции, если они не используются в проекте.",
    )
    add_paragraph(
        doc,
        "На странице проекта оператор может привязывать элементы каталога к ролям внутри "
        "проекта: детекторам, ручным извещателям, кабелю, устройствам СОУЭ, приборам и "
        "прочим компонентам. Эти сведения используются при формировании спецификаций и "
        "других листов документации.",
    )
    add_screenshot(doc, "equipment_catalog")

    add_heading(doc, "3.8 Формирование PDF-комплекта")
    add_paragraph(
        doc,
        "Генерация итоговой документации выполняется на странице проекта кнопкой "
        "«Сгенерировать PDF». Во время формирования интерфейс показывает состояние процесса, "
        "а по завершении инициирует скачивание готового файла. В состав комплекта могут "
        "входить титульные листы, общие данные, общие указания, чертежи по системам, "
        "спецификация, расчет токопотребления и дополнительные сведения.",
    )
    add_paragraph(
        doc,
        "Если в проекте отсутствуют обязательные данные, оператор должен сначала заполнить "
        "соответствующие поля на этапе подготовки проекта. При отсутствии шрифтов или других "
        "необходимых файлов PDF-генерация может завершиться ошибкой, которая отображается "
        "в интерфейсе и фиксируется на стороне backend.",
    )

    add_heading(doc, "3.9 Дообучение распознавания и управление пользователями")
    add_paragraph(
        doc,
        "Раздел «Дообучение» доступен только пользователю с ролью developer. В нем "
        "собираются исправленные оператором примеры распознавания, проводится их модерация, "
        "формируются batch-наборы и запускаются тренировочные процессы. Оператор-разработчик "
        "может просматривать примеры, фильтровать их, исключать шумные данные и отслеживать "
        "логи запусков обучения.",
    )
    add_paragraph(
        doc,
        "Раздел «Пользователи» также доступен только разработчику. Через него создаются "
        "новые учетные записи, изменяются роли и статус активности, а также выполняется "
        "сброс паролей. Интерфейс не позволяет деактивировать последнего активного "
        "разработчика, что защищает систему от блокировки административного доступа.",
    )
    add_screenshot(doc, "recognition_training")
    add_screenshot(doc, "users")

    add_heading(doc, "3.10 Завершение работы")
    add_paragraph(
        doc,
        "Для завершения сеанса оператор использует кнопку «Выйти» в правой части верхней "
        "навигационной панели. При выходе серверная сессия инвалидируется, auth-cookie "
        "очищается, а пользователь возвращается на страницу входа. После завершения работы "
        "рекомендуется штатно остановить backend и frontend в терминалах, если программа "
        "использовалась локально.",
    )


def add_operator_messages(doc: Document):
    add_heading(doc, "4 СООБЩЕНИЯ ОПЕРАТОРУ")

    add_heading(doc, "4.1 Общий формат служебных и диагностических сообщений")
    add_paragraph(
        doc,
        "На стороне frontend оператор видит как информационные статусы интерфейса, так и "
        "ошибки, полученные от backend. Во время ожидания данных могут выводиться сообщения "
        "вида «Проверяем сессию...», «Загрузка проекта...», «Загрузка пользователей...», "
        "«Сохранение...», «Вход...» и аналогичные. Они не являются ошибками и обозначают, "
        "что операция еще выполняется.",
    )
    add_paragraph(
        doc,
        "Ошибки, сформированные сервером, передаются в JSON-формате с полями `code` и "
        "`detail`. Поле `code` содержит машинное обозначение ошибки, а поле `detail` – "
        "человекочитаемое описание. Клиентская часть отображает оператору в первую очередь "
        "значение `detail`, а при его отсутствии может показать текст по коду ошибки либо "
        "статус HTTP-запроса.",
    )

    add_heading(doc, "4.2 auth_required и session_expired")
    add_paragraph(
        doc,
        "Сообщения `auth_required` и `session_expired` означают, что пользователь не "
        "авторизован или его серверная сессия истекла. В этом случае оператор должен "
        "повторно выполнить вход в систему. При возникновении этих сообщений во время "
        "работы интерфейс переводит пользователя на страницу авторизации.",
    )

    add_heading(doc, "4.3 invalid_credentials и user_inactive")
    add_paragraph(
        doc,
        "Сообщение `invalid_credentials` указывает на неправильный логин или пароль. "
        "Оператор должен проверить введенные учетные данные и повторить попытку входа. "
        "Сообщение `user_inactive` означает, что учетная запись отключена; в этом случае "
        "требуется обращение к разработчику или администратору, имеющему доступ к разделу "
        "управления пользователями.",
    )

    add_heading(doc, "4.4 developer_role_required и project_access_denied")
    add_paragraph(
        doc,
        "Сообщение `developer_role_required` возникает при попытке доступа инженера к "
        "разделам, предназначенным только для разработчика, например к управлению "
        "пользователями или дообучению. Сообщение `project_access_denied` означает, что "
        "текущий пользователь не имеет прав на выбранный проект. В обоих случаях оператору "
        "необходимо обратиться к пользователю с ролью developer либо открыть другой проект, "
        "доступный в его контуре ответственности.",
    )

    add_heading(doc, "4.5 project_not_found, floor_plan_not_found, user_not_found и equipment_item_not_found")
    add_paragraph(
        doc,
        "Эти сообщения означают, что запрошенная сущность отсутствует в базе данных или уже "
        "удалена. Оператору следует обновить список проектов, этажей, пользователей или "
        "оборудования, после чего повторить операцию. Если ошибка возникает повторно, "
        "следует проверить, не был ли объект удален другим пользователем.",
    )

    add_heading(doc, "4.6 floor_plan_image_missing, recognition_failed и recognition_not_completed")
    add_paragraph(
        doc,
        "Сообщение `floor_plan_image_missing` означает отсутствие исходного изображения "
        "плана, необходимого для распознавания. Сообщение `recognition_failed` означает "
        "ошибку в процессе обработки изображения. Сообщение `recognition_not_completed` "
        "указывает, что попытка выполнить действия над результатом распознавания была "
        "предпринята до завершения самого распознавания. В этих ситуациях оператор должен "
        "проверить наличие загруженного файла, повторить запуск шага и, при необходимости, "
        "перезагрузить страницу редактора.",
    )

    add_heading(doc, "4.7 pipeline_step_not_validated")
    add_paragraph(
        doc,
        "Сообщение `pipeline_step_not_validated` возникает, когда оператор пытается перейти "
        "к действиям, требующим завершения и подтверждения предыдущего шага pipeline. "
        "Например, отправка примера на дообучение невозможна, если соответствующий шаг еще "
        "не утвержден. Оператор должен вернуться к нужному этапу, проверить результат и "
        "выполнить его сохранение или подтверждение.",
    )

    add_heading(doc, "4.8 opening_outside_wall, wall_not_found_for_opening, instrument_required и cable_routes_incomplete")
    add_paragraph(
        doc,
        "Эти сообщения относятся к предметным ограничениям модели данных. "
        "`opening_outside_wall` и `wall_not_found_for_opening` означают, что проем "
        "размещен некорректно относительно стены. `instrument_required` сообщает, что "
        "оператор пытается сохранить шаг приборов без хотя бы одного прибора. "
        "`cable_routes_incomplete` указывает, что не все устройства привязаны к кабельным "
        "маршрутам. В этих случаях требуется исправить геометрию или недостающие привязки "
        "и затем повторить сохранение.",
    )

    add_heading(doc, "4.9 username_already_exists, last_active_developer_required, equipment_item_in_use и project_equipment_in_use")
    add_paragraph(
        doc,
        "Сообщение `username_already_exists` возникает при попытке создать пользователя с "
        "уже занятым логином. `last_active_developer_required` запрещает отключение "
        "последнего активного разработчика. `equipment_item_in_use` и "
        "`project_equipment_in_use` означают, что удаляемое оборудование уже используется "
        "в проекте или связано с другими сущностями. Оператор должен изменить данные с "
        "учетом этих ограничений, а не повторять ту же операцию без изменений.",
    )

    add_heading(doc, "4.10 recognition_active_model_missing и сообщения подсистемы дообучения")
    add_paragraph(
        doc,
        "Сообщение `recognition_active_model_missing` означает отсутствие активной модели "
        "или пути к ее checkpoint-файлу. Сообщения семейства `recognition_training_*` "
        "возникают при ошибках подготовки batch-наборов, отсутствии экспортированных "
        "изображений, пустом выборе примеров, недоступности базовой модели или сбоях "
        "запуска обучения. Для устранения этих ситуаций оператор-разработчик должен "
        "проверить наличие файлов в `outputs`, корректность конфигурации окружения и "
        "валидность выбранных примеров обучения.",
    )

    add_heading(doc, "4.11 Общие рекомендации при внутренних ошибках")
    add_paragraph(
        doc,
        "Если интерфейс сообщает о внутренней ошибке сервера или выводит текст вида "
        "`Request failed with status ...`, оператору следует зафиксировать, на каком шаге "
        "возникла проблема, при необходимости обновить страницу и повторить действие. "
        "Если ошибка воспроизводится, необходимо обратиться к разработчику и передать ему "
        "текст сообщения, время возникновения и выполняемую операцию. Это позволит "
        "соотнести сбой с серверным журналом и быстрее выявить причину.",
    )


def add_sources(doc: Document):
    add_heading(doc, "5 СПИСОК ИСТОЧНИКОВ")
    sources = [
        "1) ГОСТ 19.101–77 Виды программ и программных документов. // Единая система программной документации.",
        "2) ГОСТ 19.103–77 Обозначения программ и программных документов. // Единая система программной документации.",
        "3) ГОСТ 19.104–78 Основные надписи. // Единая система программной документации.",
        "4) ГОСТ 19.105–78 Общие требования к программным документам. // Единая система программной документации.",
        "5) ГОСТ 19.106–78 Требования к программным документам, выполненным печатным способом. // Единая система программной документации.",
        "6) ГОСТ 19.505–79 Руководство оператора. Требования к содержанию и оформлению. // Единая система программной документации.",
        "7) FastAPI. [Электронный ресурс]. URL: https://fastapi.tiangolo.com/ (дата обращения: 22.04.2026).",
        "8) React. [Электронный ресурс]. URL: https://react.dev/ (дата обращения: 22.04.2026).",
        "9) SQLAlchemy. [Электронный ресурс]. URL: https://www.sqlalchemy.org/ (дата обращения: 22.04.2026).",
        "10) Tesseract OCR. [Электронный ресурс]. URL: https://github.com/tesseract-ocr/tesseract (дата обращения: 22.04.2026).",
        "11) OpenCV. [Электронный ресурс]. URL: https://opencv.org/ (дата обращения: 22.04.2026).",
        "12) ReportLab. [Электронный ресурс]. URL: https://www.reportlab.com/ (дата обращения: 22.04.2026).",
        "13) Локальный репозиторий проекта komarov_thesis. Исходный код, настройки и документация проекта.",
    ]
    for item in sources:
        add_paragraph(doc, item, first_line_indent_cm=None)


def add_appendix(doc: Document):
    add_heading(doc, "ПРИЛОЖЕНИЕ 1 ТЕРМИНОЛОГИЯ")
    terms = [
        "План этажа – цифровое представление поэтажного плана здания, используемое системой как основа для проектирования.",
        "Pipeline – последовательность этапов обработки плана, включающая распознавание, проверку, корректировку и сохранение результата.",
        "OCR – технология оптического распознавания символов, применяемая для извлечения размерных подписей с изображения плана.",
        "СПС – система пожарной сигнализации.",
        "СОУЭ – система оповещения и управления эвакуацией.",
        "ЗКСПС – зона контроля системы пожарной сигнализации.",
        "Bootstrap-пользователь – первый пользователь с ролью developer, создаваемый системой автоматически по данным из файла `.env`.",
        "Каталог оборудования – раздел программы, содержащий карточки изделий и их технические характеристики.",
        "PDF-комплект – автоматически сформированный набор листов проектной документации в формате PDF.",
        "Дообучение распознавания – процесс накопления исправленных примеров и запуска обучения модели на этих данных.",
    ]
    for term in terms:
        add_paragraph(doc, term, first_line_indent_cm=None)


def build_document() -> Document:
    doc = Document()
    configure_document(doc)
    doc.core_properties.author = STUDENT_NAME
    doc.core_properties.title = f"{PROGRAM_NAME_RU}. Руководство оператора"
    doc.core_properties.subject = "Программная документация"

    add_approval_page(doc)
    add_page_break(doc)
    add_title_page(doc)
    add_page_break(doc)

    add_heading(doc, "СОДЕРЖАНИЕ")
    toc_paragraph = doc.add_paragraph()
    toc_paragraph.paragraph_format.first_line_indent = None
    toc_paragraph.paragraph_format.line_spacing = 1.5
    add_toc(toc_paragraph)

    add_page_break(doc)
    add_purpose_section(doc)
    add_execution_conditions(doc)
    add_execution_section(doc)
    add_operator_messages(doc)
    add_sources(doc)
    add_page_break(doc)
    add_appendix(doc)
    add_page_break(doc)
    add_change_log_page(doc)
    return doc


def main():
    doc = build_document()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT_PATH)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
