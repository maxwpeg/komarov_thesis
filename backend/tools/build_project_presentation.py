from __future__ import annotations

import copy
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "outputs" / "Komarov_Project_Presentation_2026.pptx"
TEMPLATE_DIRS = [Path.home() / "YandexDisk-mskomarov@edu.hse.ru" / "pp"]

PRIMARY = "#153b7a"
PRIMARY_DARK = "#102d69"
ACCENT = "#f28e2b"
BG = "#f4f7fb"
TEXT = "#1f2937"
MUTED = "#5b6778"
LINE = "#d7dfeb"
SUCCESS = "#2f8f5b"
WARNING = "#d66b2c"


def find_template() -> Path:
    for folder in TEMPLATE_DIRS:
        candidates = sorted(folder.glob("project_proposal*.pptx"))
        if candidates:
            return candidates[0]
    raise FileNotFoundError("Template PPTX was not found in configured directories.")


def load_font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if mono:
        candidates = [
            Path("C:/Windows/Fonts/consola.ttf"),
            Path("C:/Windows/Fonts/cour.ttf"),
        ]
    elif bold:
        candidates = [
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ]
    else:
        candidates = [
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    image = image.convert("RGB")
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = image.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for block in text.split("\n"):
        words = block.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: str,
    spacing: int = 8,
) -> int:
    x1, y1, x2, y2 = box
    y = y1
    for line in wrap_text(draw, text, font, max(40, x2 - x1)):
        draw.text((x1, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x1, y), line, font=font)
        y += (bbox[3] - bbox[1]) + spacing
        if y > y2:
            break
    return y


def rounded_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str | None = None, width: int = 2) -> None:
    draw.rounded_rectangle(box, radius=24, fill=fill, outline=outline, width=width)


def make_canvas(size: tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", size, BG)
    return image, ImageDraw.Draw(image)


def clone_child(parent: ET.Element | None, child: ET.Element | None) -> ET.Element | None:
    if parent is None or child is None:
        return None
    return copy.deepcopy(child)


def clear_children(element: ET.Element) -> None:
    for child in list(element):
        element.remove(child)


def set_text_body(tx_body: ET.Element, paragraphs: list[str]) -> None:
    proto_p = tx_body.find("a:p", NS)
    proto_ppr = clone_child(proto_p, proto_p.find("a:pPr", NS) if proto_p is not None else None)
    proto_r = proto_p.find("a:r", NS) if proto_p is not None else None
    proto_rpr = clone_child(proto_r, proto_r.find("a:rPr", NS) if proto_r is not None else None)
    proto_end = clone_child(proto_p, proto_p.find("a:endParaRPr", NS) if proto_p is not None else None)
    clear_children(tx_body)
    for text in paragraphs:
        p = ET.SubElement(tx_body, f"{{{NS['a']}}}p")
        if proto_ppr is not None:
            p.append(copy.deepcopy(proto_ppr))
        r = ET.SubElement(p, f"{{{NS['a']}}}r")
        if proto_rpr is not None:
            r.append(copy.deepcopy(proto_rpr))
        t = ET.SubElement(r, f"{{{NS['a']}}}t")
        if text.startswith(" ") or text.endswith(" "):
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = text
        if proto_end is not None:
            p.append(copy.deepcopy(proto_end))


SLIDE_TEXT = {
    1: {
        "Заголовок 1": [
            "Web Application for Automatic Creation of Security Systems Project Documentation",
        ],
        "Текст 2": [
            "Faculty of Computer Science",
            "Department of Software Engineering",
        ],
        "Текст 3": [
            "Komarov Maksim",
            "mskomarov@edu.hse.ru",
        ],
        "Текст 4": [
            "Moscow, 2026",
        ],
        "Текст 5": [
            "Komarov Maksim, BSE225",
            "Software Engineering",
            "Supervisor",
            "Videnin Sergei, Associate Professor, Doctor of Technical Sciences",
        ],
    },
    2: {
        "Заголовок 2": ["The problem"],
        "Текст 3": [
            "Documentation for fire alarm and evacuation systems is still prepared manually in many engineering companies.",
            "Engineers must satisfy both GOST document structure and SP 484 / SP 486 design logic.",
            "Existing CAD/BIM and vendor-specific tools do not provide a lightweight end-to-end workflow for raster floor plans, validation, and final PDF generation.",
            "This increases preparation time, duplicates calculations, and makes consistency between drawings, specifications, and reports harder to control.",
        ],
    },
    3: {
        "Заголовок 2": ["Existing solutions and gap"],
        "Текст 3": [
            "The proposal reviews nanoCAD BIM OPS, RUBEZH FireSec 3, AutoCAD MEP, and MagiCAD.",
            "These products mainly focus on CAD/BIM modeling or vendor-specific configuration.",
            "GOST-oriented documentation and compliance checks are only partially automated and often still require manual validation.",
            "The target niche is a web-based workflow that starts from uploaded plans and ends with validated documentation.",
        ],
    },
    5: {
        "Заголовок 2": ["Architecture"],
        "Текст 3": [
            "The solution is implemented as a full-stack web application with clear separation between UI, application services, persistence, and document rendering.",
            "FastAPI exposes routers for projects, floor plans, elements, recognition, step-by-step pipeline validation, and PDF generation.",
            "SQLite stores structured project data, while uploads, outputs, and debug artifacts are persisted as separate runtime assets.",
        ],
    },
    6: {
        "Заголовок 2": ["Validation pipeline"],
        "Текст 3": [
            "The processing workflow is decomposed into three validated stages: walls, openings, and rooms.",
            "Each stage has detect and commit endpoints; downstream steps become stale when upstream geometry changes.",
            "Confirmed wall lengths recalibrate the floor scale, and room metrics are recomputed from validated geometry.",
        ],
    },
    7: {
        "Заголовок 2": ["Interactive editor"],
        "Текст 3": [
            "The React + Konva editor lets engineers inspect the uploaded plan and adjust walls, doors, windows, rooms, dimensions, and fire alarms.",
            "The UI supports zoom, drag-and-drop editing, multi-selection, undo history, local drafts, and batch save.",
            "Recognition results, pipeline state, missing-wall validation alerts, and debug images are available directly in the workspace.",
        ],
    },
    8: {
        "Заголовок 2": ["Recognition and documentation"],
        "Текст 3": [
            "Recognition results are persisted as a dedicated record with machine-detected walls, openings, rooms, and OCR dimensions.",
            "User-defined room names are preserved across re-recognition using polygon IoU matching.",
            "The final generator creates GOST-compliant title pages and drawing sheets with room labels and fire alarm overlays.",
        ],
    },
    9: {
        "Заголовок 2": ["Technologies"],
        "Текст 3": [
            "Backend: Python, FastAPI, SQLAlchemy, SQLite, ReportLab, Pillow.",
            "Recognition and geometry: OpenCV, OCR-based dimensions, classical floor plan processing, optional YOLO integration.",
            "Frontend and quality: React 19, React Router, Konva, Axios, pytest integration tests, API smoke tests.",
        ],
    },
    10: {
        "Заголовок 2": ["Current progress"],
        "Текст 3": [
            "Implemented project CRUD, floor plan upload, and persistent project numbering.",
            "Built an interactive editor for walls, openings, rooms, dimensions, and fire alarms.",
            "Added a validated walls/openings/rooms pipeline with downstream invalidation logic and integration tests.",
            "Integrated recognition persistence, debug artifacts, and room-name preservation across re-runs.",
            "Delivered end-to-end PDF generation with smoke-test coverage.",
        ],
    },
    11: {
        "Заголовок 2": ["Next steps"],
        "Текст 3": [
            "Improve recognition quality on diverse scanned floor plans and extend debug tooling.",
            "Complete automatic generation of connection schemes, specifications, and power-consumption calculations.",
            "Refine expert UI ergonomics for bulk editing and validation-heavy workflows.",
            "Evaluate time savings, error reduction, and compliance quality on real engineering projects.",
            "Prepare the final documentation package and demo-ready public materials.",
        ],
    },
    12: {
        "Заголовок 2": ["References"],
        "Текст 3": [
            "GOST 19.201-78, GOST 19.404-79, and related documentation standards.",
            "SP 484.1311500.2020 and SP 486.1311500.2020.",
            "React framework: https://react.dev/",
            "FastAPI: https://fastapi.tiangolo.com/",
            "OpenCV: https://opencv.org/",
            "ReportLab: https://www.reportlab.com/",
            "nanoCAD BIM OPS, RUBEZH FireSec 3, AutoCAD MEP, and MagiCAD.",
        ],
    },
}


WORKFLOW_TABLE = [
    ["Workflow step", "Upload", "Walls", "Openings", "Rooms", "Fire alarms", "PDF"],
    ["Main input", "raster image", "binary plan", "validated walls", "validated openings", "room metrics", "project + plans"],
    ["Automatic step", "store file", "detect walls + OCR", "classify gaps", "segment rooms", "calculate devices", "render pages"],
    ["User action", "set metadata", "confirm lengths", "adjust wall links", "review room names", "review placement", "download package"],
    ["Persisted data", "FloorPlan", "Wall + Dimension", "Door + Window", "Room", "FireAlarm", "output file"],
    ["API support", "/floor-plans", "/pipeline/walls/*", "/pipeline/openings/*", "/pipeline/rooms/*", "/calculate-fire-alarms", "/generate-pdf"],
    ["Test coverage", "CRUD/API", "pipeline tests", "pipeline tests", "room metrics", "alarm tests", "pdf smoke"],
    ["Primary value", "source of truth", "scale calibration", "cleaner geometry", "named spaces", "device layout", "GOST package"],
]


def source_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def build_standards_banner(size: tuple[int, int]) -> Image.Image:
    image, draw = make_canvas(size)
    badge_font = load_font(42, bold=True)
    small_font = load_font(26)
    badges = [("GOST 19", PRIMARY), ("SP 484", ACCENT), ("SP 486", SUCCESS)]
    x = 40
    for label, color in badges:
        box = (x, 120, x + 320, 320)
        rounded_box(draw, box, fill="white", outline=color, width=5)
        draw.text((box[0] + 34, box[1] + 42), label, font=badge_font, fill=color)
        draw.text((box[0] + 34, box[1] + 112), "Design constraints", font=small_font, fill=MUTED)
        x += 360
    return image.convert("RGB")


def build_pdf_card(size: tuple[int, int], drawing_image: Image.Image) -> Image.Image:
    image, draw = make_canvas(size)
    paper = (48, 32, size[0] - 44, size[1] - 28)
    rounded_box(draw, paper, fill="white", outline=LINE, width=2)
    title_font = load_font(28, bold=True)
    body_font = load_font(18)
    mono_font = load_font(18, mono=True)
    draw.text((paper[0] + 28, paper[1] + 22), "Generated PDF package", font=title_font, fill=PRIMARY_DARK)
    draw.text((paper[0] + 28, paper[1] + 64), "Title pages • drawings • labels • devices", font=body_font, fill=MUTED)
    preview = fit_cover(drawing_image, (paper[2] - paper[0] - 56, 170))
    image.paste(preview, (paper[0] + 28, paper[1] + 102))
    draw.rounded_rectangle((paper[0] + 28, paper[1] + 288, paper[2] - 28, paper[1] + 350), radius=18, fill="#f8fafc")
    draw.text((paper[0] + 48, paper[1] + 306), "outputs/Project_<code>_<date>.pdf", font=mono_font, fill=PRIMARY_DARK)
    return image.convert("RGB")


def build_gap_landscape(size: tuple[int, int]) -> Image.Image:
    image, draw = make_canvas(size)
    title_font = load_font(30, bold=True)
    body_font = load_font(20)
    note_font = load_font(18)
    draw.text((34, 24), "Landscape of existing solutions", font=title_font, fill=PRIMARY_DARK)
    draw.text((34, 62), "Literature review: CAD/BIM and vendor tools cover only fragments of the workflow.", font=body_font, fill=MUTED)
    cards = [
        ("Manual workflow", "Drawings, calculations,\nreports prepared separately.", PRIMARY),
        ("CAD / BIM", "Strong modeling capabilities,\nbut heavy and not workflow-oriented.", PRIMARY),
        ("Vendor tools", "Good inside equipment ecosystems,\nbut often product-dependent.", ACCENT),
        ("This project", "Upload -> validate -> calculate ->\ngenerate GOST PDF.", ACCENT),
    ]
    positions = [
        (34, 112, 318, 286),
        (360, 112, 644, 286),
        (34, 304, 318, 430),
        (360, 304, 644, 430),
    ]
    for (title, body, outline), box in zip(cards, positions, strict=True):
        rounded_box(draw, box, fill="white" if title != "This project" else "#fff7ef", outline=outline, width=4)
        draw.text((box[0] + 20, box[1] + 18), title, font=load_font(22, bold=True), fill=PRIMARY_DARK)
        draw_wrapped_text(draw, (box[0] + 20, box[1] + 60, box[2] - 20, box[3] - 18), body, font=body_font, fill=TEXT, spacing=6)
    draw.rounded_rectangle((90, 392, 588, 432), radius=16, fill=PRIMARY_DARK)
    draw.text((112, 403), "Missing niche: web workflow from scanned plan to validated documentation.", font=note_font, fill="white")
    return image.convert("RGBA")


def build_architecture(size: tuple[int, int]) -> Image.Image:
    image, draw = make_canvas(size)
    title_font = load_font(18, bold=True)
    body_font = load_font(12)
    small_font = load_font(11)
    blocks = [
        ((20, 18, size[0] - 20, 58), "React UI", "ProjectList • ProjectDetail • FloorPlanEditor"),
        ((20, 76, size[0] - 20, 116), "FastAPI routers", "projects • floor plans • elements • recognition • pipeline • pdf"),
        ((20, 134, size[0] - 20, 174), "Services", "RecognitionService • PipelineService • PdfService • ElementService"),
        ((20, 192, size[0] - 20, 232), "Persistence", "SQLite • uploads/ • outputs/ • debug_output/"),
    ]
    for box, title, body in blocks:
        rounded_box(draw, box, fill="white", outline=LINE, width=2)
        draw.text((box[0] + 14, box[1] + 8), title, font=title_font, fill=PRIMARY_DARK)
        draw_wrapped_text(draw, (box[0] + 14, box[1] + 28, box[2] - 14, box[3] - 8), body, font=body_font, fill=TEXT, spacing=2)
    for top, bottom in zip(blocks, blocks[1:]):
        x = size[0] // 2
        y1 = top[0][3]
        y2 = bottom[0][1]
        draw.line((x, y1 + 4, x, y2 - 8), fill=ACCENT, width=4)
        draw.polygon([(x - 6, y2 - 8), (x + 6, y2 - 8), (x, y2 + 2)], fill=ACCENT)
    draw.rounded_rectangle((20, 254, size[0] - 20, size[1] - 18), radius=16, fill="#edf4ff")
    draw_wrapped_text(
        draw,
        (34, 268, size[0] - 34, size[1] - 28),
        "Legacy ReportLab rendering classes are reused for standards-compliant output.",
        font=small_font,
        fill=PRIMARY_DARK,
        spacing=2,
    )
    return image.convert("RGBA")


def build_pipeline(size: tuple[int, int]) -> Image.Image:
    image, draw = make_canvas(size)
    title_font = load_font(38, bold=True)
    step_font = load_font(24, bold=True)
    body_font = load_font(18)
    note_font = load_font(20)
    draw.text((46, 34), "Validated processing pipeline", font=title_font, fill=PRIMARY_DARK)
    steps = [
        ("1. Upload", "image + metadata", PRIMARY),
        ("2. Detect walls", "CV + OCR", PRIMARY),
        ("3. Commit walls", "scale calibration", ACCENT),
        ("4. Detect openings", "gap classification", PRIMARY),
        ("5. Commit openings", "wall binding", ACCENT),
        ("6. Detect rooms", "segmentation", PRIMARY),
        ("7. Commit rooms", "names + metrics", ACCENT),
        ("8. Fire alarms", "device layout", SUCCESS),
        ("9. PDF", "GOST package", SUCCESS),
    ]
    left = 42
    top = 146
    box_w = 178
    box_h = 160
    gap = 18
    for index, (title, body, color) in enumerate(steps):
        x1 = left + index * (box_w + gap)
        x2 = x1 + box_w
        box = (x1, top, x2, top + box_h)
        rounded_box(draw, box, fill="white", outline=color, width=4)
        draw.text((x1 + 18, top + 18), title, font=step_font, fill=color)
        draw_wrapped_text(draw, (x1 + 18, top + 64, x2 - 18, top + 130), body, font=body_font, fill=TEXT, spacing=6)
        if index < len(steps) - 1:
            y = top + box_h // 2
            draw.line((x2 + 6, y, x2 + gap - 8, y), fill=ACCENT, width=8)
            draw.polygon([(x2 + gap - 8, y), (x2 + gap - 24, y - 10), (x2 + gap - 24, y + 10)], fill=ACCENT)
    draw.rounded_rectangle((52, 368, size[0] - 52, 456), radius=22, fill="#fff7ef", outline=ACCENT, width=3)
    draw.text((84, 394), "If upstream geometry changes, downstream stages are marked stale and must be revalidated.", font=note_font, fill=PRIMARY_DARK)
    return image.convert("RGBA")


def build_editor_mock(size: tuple[int, int], floor_image: Image.Image) -> Image.Image:
    image, draw = make_canvas(size)
    browser = (26, 26, size[0] - 26, size[1] - 26)
    rounded_box(draw, browser, fill="white", outline=LINE, width=2)
    draw.rounded_rectangle((browser[0], browser[1], browser[2], browser[1] + 60), radius=24, fill=PRIMARY_DARK)
    draw.text((browser[0] + 30, browser[1] + 18), "Floor plan editor", font=load_font(26, bold=True), fill="white")
    toolbar_items = ["Select", "Wall", "Door", "Window", "Room", "Alarm", "Save"]
    x = browser[0] + 320
    for item in toolbar_items:
        width = 92 if item != "Window" else 108
        fill = "#2a5cb0" if item == "Save" else "#224a94"
        draw.rounded_rectangle((x, browser[1] + 14, x + width, browser[1] + 46), radius=12, fill=fill)
        draw.text((x + 14, browser[1] + 20), item, font=load_font(16, bold=(item == "Save")), fill="white")
        x += width + 12
    canvas_box = (browser[0] + 24, browser[1] + 84, browser[0] + 720, browser[3] - 24)
    sidebar = (browser[0] + 752, browser[1] + 84, browser[2] - 24, browser[3] - 24)
    rounded_box(draw, canvas_box, fill="#f8fafc", outline=LINE, width=2)
    rounded_box(draw, sidebar, fill="#f8fafc", outline=LINE, width=2)
    canvas_img = fit_cover(floor_image, (canvas_box[2] - canvas_box[0] - 24, canvas_box[3] - canvas_box[1] - 24))
    image.paste(canvas_img, (canvas_box[0] + 12, canvas_box[1] + 12))
    overlay = ImageDraw.Draw(image)
    room_boxes = [
        (canvas_box[0] + 84, canvas_box[1] + 86, canvas_box[0] + 272, canvas_box[1] + 262),
        (canvas_box[0] + 310, canvas_box[1] + 226, canvas_box[0] + 520, canvas_box[1] + 384),
    ]
    for idx, box in enumerate(room_boxes, start=1):
        overlay.rounded_rectangle(box, radius=20, outline="#a349a4", width=5)
        overlay.text((box[0] + 14, box[1] + 12), f"Room {idx}", font=load_font(18, bold=True), fill="#7a247f")
    alarms = [
        (canvas_box[0] + 268, canvas_box[1] + 154),
        (canvas_box[0] + 466, canvas_box[1] + 244),
        (canvas_box[0] + 558, canvas_box[1] + 148),
    ]
    for x0, y0 in alarms:
        overlay.ellipse((x0 - 18, y0 - 18, x0 + 18, y0 + 18), fill="#ffefef", outline="#cc3d3d", width=4)
        overlay.text((x0 - 9, y0 - 11), "A", font=load_font(18, bold=True), fill="#cc3d3d")
    section_font = load_font(22, bold=True)
    item_font = load_font(17)
    draw.text((sidebar[0] + 18, sidebar[1] + 16), "Pipeline", font=section_font, fill=PRIMARY_DARK)
    pills = [
        ("Walls", "validated", SUCCESS),
        ("Openings", "validated", SUCCESS),
        ("Rooms", "draft", WARNING),
        ("Recognition", "available", PRIMARY),
    ]
    y = sidebar[1] + 54
    for name, state, color in pills:
        draw.rounded_rectangle((sidebar[0] + 18, y, sidebar[2] - 18, y + 44), radius=14, fill="white", outline=LINE, width=2)
        draw.text((sidebar[0] + 34, y + 11), name, font=item_font, fill=TEXT)
        draw.rounded_rectangle((sidebar[2] - 142, y + 8, sidebar[2] - 28, y + 36), radius=12, fill=color)
        draw.text((sidebar[2] - 128, y + 11), state, font=load_font(15, bold=True), fill="white")
        y += 56
    draw.text((sidebar[0] + 18, y + 8), "Debug panel", font=section_font, fill=PRIMARY_DARK)
    y += 44
    for item in ["walls_binary.png", "openings_candidates.png", "rooms_overlay.png"]:
        draw.rounded_rectangle((sidebar[0] + 18, y, sidebar[2] - 18, y + 40), radius=12, fill="white", outline=LINE, width=2)
        draw.text((sidebar[0] + 34, y + 10), item, font=load_font(15, mono=True), fill=MUTED)
        y += 50
    return image.convert("RGBA")


def build_recognition_strip(size: tuple[int, int], floor_image: Image.Image, drawing_image: Image.Image) -> Image.Image:
    image, draw = make_canvas(size)
    card_w = (size[0] - 80) // 3
    cards = [
        (24, 24, 24 + card_w, size[1] - 24),
        (40 + card_w, 24, 40 + card_w * 2, size[1] - 24),
        (56 + card_w * 2, 24, size[0] - 24, size[1] - 24),
    ]
    labels = ["Source plan", "Structured recognition", "Generated documentation"]
    previews = [
        fit_cover(floor_image, (card_w - 32, size[1] - 92)),
        fit_cover(floor_image, (card_w - 32, size[1] - 92)),
        fit_cover(drawing_image, (card_w - 32, size[1] - 132)),
    ]
    for idx, box in enumerate(cards):
        rounded_box(draw, box, fill="white", outline=LINE, width=2)
        draw.text((box[0] + 18, box[1] + 16), labels[idx], font=load_font(22, bold=True), fill=PRIMARY_DARK)
        image.paste(previews[idx], (box[0] + 16, box[1] + 56))
    overlay = ImageDraw.Draw(image)
    mid = cards[1]
    overlay.rounded_rectangle((mid[0] + 72, mid[1] + 118, mid[0] + 250, mid[1] + 258), radius=18, outline="#a349a4", width=4)
    overlay.line((mid[0] + 94, mid[1] + 314, mid[0] + 270, mid[1] + 314), fill="#39ff14", width=6)
    overlay.line((mid[0] + 270, mid[1] + 314, mid[0] + 350, mid[1] + 396), fill="#39ff14", width=6)
    for cx, cy in [(mid[0] + 296, mid[1] + 196), (mid[0] + 350, mid[1] + 250)]:
        overlay.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill="#ffefef", outline="#cc3d3d", width=3)
    right = cards[2]
    overlay.rounded_rectangle((right[0] + 26, right[3] - 70, right[2] - 26, right[3] - 22), radius=16, fill="#f8fafc")
    overlay.text((right[0] + 40, right[3] - 58), "Title pages • drawing sheets • device labels", font=load_font(16), fill=MUTED)
    return image.convert("RGBA")


def build_stack(size: tuple[int, int]) -> Image.Image:
    image, draw = make_canvas(size)
    title_font = load_font(34, bold=True)
    label_font = load_font(22, bold=True)
    item_font = load_font(18)
    draw.text((44, 34), "Technology stack", font=title_font, fill=PRIMARY_DARK)
    layers = [
        ("Frontend", ["React 19", "React Router", "Konva", "Axios"], PRIMARY),
        ("API", ["FastAPI", "Pydantic", "routers", "dependencies"], "#2758a0"),
        ("Domain", ["pipeline", "recognition", "fire alarms", "PDF services"], ACCENT),
        ("Persistence", ["SQLAlchemy", "SQLite", "uploads/", "outputs/"], SUCCESS),
        ("CV / Rendering", ["OpenCV", "OCR", "ReportLab", "Pillow", "optional YOLO"], "#7a3ca6"),
    ]
    top = 114
    for index, (label, items, color) in enumerate(layers):
        box = (58, top + index * 222, size[0] - 58, top + index * 222 + 182)
        rounded_box(draw, box, fill="white", outline=color, width=4)
        draw.text((box[0] + 26, box[1] + 18), label, font=label_font, fill=color)
        x = box[0] + 24
        y = box[1] + 70
        for item in items:
            pill_w = max(140, int(draw.textlength(item, font=item_font)) + 34)
            if x + pill_w > box[2] - 24:
                x = box[0] + 24
                y += 46
            draw.rounded_rectangle((x, y, x + pill_w, y + 34), radius=14, fill=BG)
            draw.text((x + 16, y + 8), item, font=item_font, fill=TEXT)
            x += pill_w + 14
    return image.convert("RGBA")


def build_assets(media_dir: Path) -> None:
    floor_image = source_image(ROOT / "1.jpeg")
    placed_image = source_image(ROOT / "uploads" / "333.jpg")
    assets = {
        "image6.jpeg": build_standards_banner((1200, 600)),
        "image7.jpeg": fit_cover(floor_image, (3840, 2400)),
        "image8.jpeg": build_pdf_card((626, 414), placed_image),
        "image9.png": build_gap_landscape((677, 446)),
        "image10.png": build_architecture((487, 351)),
        "image11.png": build_pipeline((1896, 1428)),
        "image12.png": build_editor_mock((1078, 490), floor_image),
        "image13.png": build_recognition_strip((1712, 432), floor_image, placed_image),
        "image14.png": build_stack((1380, 1392)),
    }
    for name, image in assets.items():
        path = media_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            image.convert("RGB").save(path, quality=92)
        else:
            image.save(path)


def replace_slide_text(slide_xml: Path, mapping: dict[str, list[str]]) -> None:
    tree = ET.parse(slide_xml)
    root = tree.getroot()
    for shape in root.findall(".//p:sp", NS):
        name_node = shape.find("p:nvSpPr/p:cNvPr", NS)
        tx_body = shape.find("p:txBody", NS)
        if name_node is None or tx_body is None:
            continue
        name = name_node.attrib.get("name")
        if name in mapping:
            set_text_body(tx_body, mapping[name])
    tree.write(slide_xml, xml_declaration=True, encoding="utf-8")


def replace_table(slide_xml: Path, values: list[list[str]]) -> None:
    tree = ET.parse(slide_xml)
    root = tree.getroot()
    table = root.find(".//a:tbl", NS)
    if table is None:
        raise ValueError(f"No table found in {slide_xml}")
    rows = table.findall("a:tr", NS)
    for row_idx, row in enumerate(rows):
        cells = row.findall("a:tc", NS)
        row_values = values[row_idx] if row_idx < len(values) else []
        for col_idx, cell in enumerate(cells):
            tx_body = cell.find("a:txBody", NS)
            if tx_body is None:
                continue
            value = row_values[col_idx] if col_idx < len(row_values) else ""
            set_text_body(tx_body, value.split("\n") if value else [""])
    tree.write(slide_xml, xml_declaration=True, encoding="utf-8")


def add_final_slide_message(slide_xml: Path) -> None:
    tree = ET.parse(slide_xml)
    root = tree.getroot()
    sp_tree = root.find("p:cSld/p:spTree", NS)
    if sp_tree is None:
        raise ValueError("Final slide has no shape tree")

    def make_shape(shape_id: int, name: str, x: int, y: int, cx: int, cy: int, paragraphs: list[str], *, font_size: int, bold: bool) -> ET.Element:
        sp = ET.Element(f"{{{NS['p']}}}sp")
        nv = ET.SubElement(sp, f"{{{NS['p']}}}nvSpPr")
        ET.SubElement(nv, f"{{{NS['p']}}}cNvPr", {"id": str(shape_id), "name": name})
        ET.SubElement(nv, f"{{{NS['p']}}}cNvSpPr")
        ET.SubElement(nv, f"{{{NS['p']}}}nvPr")
        sp_pr = ET.SubElement(sp, f"{{{NS['p']}}}spPr")
        xfrm = ET.SubElement(sp_pr, f"{{{NS['a']}}}xfrm")
        ET.SubElement(xfrm, f"{{{NS['a']}}}off", {"x": str(x), "y": str(y)})
        ET.SubElement(xfrm, f"{{{NS['a']}}}ext", {"cx": str(cx), "cy": str(cy)})
        ET.SubElement(sp_pr, f"{{{NS['a']}}}prstGeom", {"prst": "rect"})
        tx = ET.SubElement(sp, f"{{{NS['p']}}}txBody")
        ET.SubElement(tx, f"{{{NS['a']}}}bodyPr", {"anchor": "ctr"})
        ET.SubElement(tx, f"{{{NS['a']}}}lstStyle")
        for paragraph in paragraphs:
            p = ET.SubElement(tx, f"{{{NS['a']}}}p")
            ppr = ET.SubElement(p, f"{{{NS['a']}}}pPr", {"algn": "ctr"})
            ET.SubElement(ppr, f"{{{NS['a']}}}buNone")
            r = ET.SubElement(p, f"{{{NS['a']}}}r")
            ET.SubElement(
                r,
                f"{{{NS['a']}}}rPr",
                {"lang": "en-US", "sz": str(font_size), "b": "1" if bold else "0"},
            )
            ET.SubElement(r, f"{{{NS['a']}}}t").text = paragraph
            ET.SubElement(
                p,
                f"{{{NS['a']}}}endParaRPr",
                {"lang": "en-US", "sz": str(font_size), "b": "1" if bold else "0"},
            )
        return sp

    sp_tree.append(make_shape(2, "Title 1", 1500000, 2050000, 9800000, 1200000, ["Thank you"], font_size=2600, bold=True))
    sp_tree.append(make_shape(3, "Text 2", 2200000, 3450000, 8400000, 900000, ["Questions?"], font_size=1800, bold=False))
    tree.write(slide_xml, xml_declaration=True, encoding="utf-8")


def rewrite_presentation(extracted_root: Path) -> None:
    ppt_root = extracted_root / "ppt"
    for slide_no, mapping in SLIDE_TEXT.items():
        replace_slide_text(ppt_root / "slides" / f"slide{slide_no}.xml", mapping)
    replace_table(ppt_root / "slides" / "slide4.xml", WORKFLOW_TABLE)
    add_final_slide_message(ppt_root / "slides" / "slide13.xml")
    build_assets(ppt_root / "media")


def repackage(source_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(source_dir).as_posix())


def main() -> None:
    template = find_template()
    with tempfile.TemporaryDirectory() as tmp_dir:
        work_dir = Path(tmp_dir)
        with zipfile.ZipFile(template) as zf:
            zf.extractall(work_dir)
        rewrite_presentation(work_dir)
        repackage(work_dir, OUTPUT_PATH)
    print(f"Generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
