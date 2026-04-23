"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
import re

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware

from backend.bootstrap import configure_logging, ensure_runtime_directories, register_pdf_fonts
from backend.config import settings
from backend.database import engine, init_db
from backend.errors import install_exception_handlers
from backend.modules.shared.health.service import HealthService
from backend.modules.shared.observability.middleware import RequestContextMiddleware
from backend.routers import (
    assets_router,
    auth_router,
    background_tasks_router,
    equipment_router,
    elements_router,
    floor_plans_router,
    pdf_router,
    pipeline_router,
    projects_router,
    recognition_router,
    recognition_training_router,
    users_router,
)
from backend.schemas import HealthRead
from backend.services.background_worker import worker_controller


logger = configure_logging()
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

API_TITLE = "API системы проектирования противопожарной защиты"
API_SUMMARY = "REST API для ведения проектов, поэтажных планов, оборудования, пайплайна распознавания и генерации PDF."
API_DESCRIPTION = (
    "API управляет проектами систем пожарной сигнализации и СОУЭ: хранит карточки проекта и оборудования, "
    "поддерживает пошаговую обработку планов этажей, позволяет редактировать общие проектные документы и "
    "генерировать комплект PDF-чертежей. Все описания в Swagger ориентированы на русскоязычного пользователя."
)
OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Аутентификация пользователей, вход в систему, завершение сессии и получение данных текущего пользователя.",
    },
    {
        "name": "users",
        "description": "Управление пользователями, ролями и паролями. Доступно только разработчикам.",
    },
    {
        "name": "system",
        "description": "Служебные эндпоинты для проверки доступности сервиса и готовности инфраструктуры.",
    },
    {
        "name": "projects",
        "description": "Управление карточками проектов: создание, просмотр, обновление и удаление.",
    },
    {
        "name": "floor-plans",
        "description": "Работа с планами этажей внутри проекта, загрузкой изображений и параметрами плана.",
    },
    {
        "name": "elements",
        "description": "CRUD-операции для геометрии и размещаемых элементов на плане: стены, проёмы, комнаты, "
        "извещатели, приборы, кабельные линии и связанные сущности.",
    },
    {
        "name": "pipeline",
        "description": "Пошаговый пайплайн распознавания и валидации плана: стены, проёмы, помещения и ЗКСПС.",
    },
    {
        "name": "equipment",
        "description": "Каталог оборудования и проектные привязки оборудования к ролям и объектам проекта.",
    },
    {
        "name": "recognition",
        "description": "Распознавание архитектурного плана, сохранение обратной связи и статистика обучения.",
    },
    {
        "name": "recognition-training",
        "description": "Управление примерами обучения, batch-curation, тренировочными запусками и активными моделями.",
    },
    {
        "name": "pdf",
        "description": "Проектные документы и генерация PDF-комплекта: общие данные, общие указания, спецификация, "
        "расчёт токопотребления и дополнительные сведения.",
    },
]
PARAMETER_DESCRIPTIONS = {
    "user_id": "Уникальный идентификатор пользователя.",
    "project_id": "Уникальный идентификатор проекта.",
    "floor_plan_id": "Уникальный идентификатор плана этажа.",
    "equipment_id": "Уникальный идентификатор позиции оборудования.",
    "wall_id": "Уникальный идентификатор стены.",
    "door_id": "Уникальный идентификатор двери.",
    "window_id": "Уникальный идентификатор окна.",
    "room_id": "Уникальный идентификатор помещения.",
    "dimension_id": "Уникальный идентификатор размерной линии.",
    "fire_alarm_id": "Уникальный идентификатор пожарного извещателя.",
    "soue_device_id": "Уникальный идентификатор устройства СОУЭ.",
    "instrument_id": "Уникальный идентификатор прибора или пульта.",
    "route_id": "Уникальный идентификатор кабельного маршрута.",
    "run_id": "Идентификатор тренировочного запуска распознавания.",
    "example_id": "Идентификатор примера обратной связи для обучения.",
    "skip": "Количество записей, которые нужно пропустить в начале выборки.",
    "limit": "Максимальное количество записей в ответе.",
    "include_elements": "Если `true`, вернуть план вместе со всеми размещёнными элементами.",
    "debug": "Если `true`, дополнительно включать отладочные артефакты и промежуточные результаты.",
    "system_type": "Тип сигнальной подсистемы: адресная, безадресная или общая.",
    "subsystem_type": "Подсистема кабельного маршрута: СПС или СОУЭ.",
    "step": "Этап пайплайна или обучения, к которому относится операция.",
    "tail": "Количество последних строк лога, которые нужно вернуть.",
    "sort_by": "Поле сортировки выборки.",
    "sort_dir": "Направление сортировки: `asc` или `desc`.",
    "search": "Строка поиска по доступным текстовым полям.",
    "changed_only": "Если `true`, вернуть только примеры, где пользователь менял результат распознавания.",
    "curation_status": "Статус модерации примера для обучения.",
    "file": "Загружаемый файл, который нужно сохранить на сервере.",
    "image": "Изображение оборудования для карточки каталога.",
    "name": "Пользовательское имя сущности.",
    "floor_number": "Номер этажа внутри проекта.",
    "scale_factor": "Масштаб плана в миллиметрах на пиксель.",
    "ceiling_height_mm": "Высота помещения в миллиметрах.",
}
FIELD_DESCRIPTIONS = {
    "id": "Уникальный идентификатор записи.",
    "project_id": "Идентификатор проекта, к которому относится сущность.",
    "floor_plan_id": "Идентификатор плана этажа, к которому относится сущность.",
    "name": "Наименование сущности, отображаемое пользователю.",
    "page_title": "Название листа или документа, которое попадёт в основную надпись и интерфейс.",
    "heading": "Основной заголовок печатного листа.",
    "local_sheet_title": "Локальное название листа для раздела документации.",
    "text": "Основной текст документа или поля.",
    "blocks": "Структурированные блоки текста документа.",
    "rows": "Строки таблицы или раздела документа.",
    "sections": "Разделы документа или таблицы.",
    "column_headers": "Заголовки колонок таблицы.",
    "categories": "Категории оборудования или строк расчёта.",
    "summary_rows": "Итоговые строки расчёта.",
    "warnings": "Список предупреждений, требующих внимания пользователя.",
    "message": "Человекочитаемое сообщение о результате операции.",
    "code": "Шифр проекта или код позиции.",
    "project_type": "Тип проекта или марка комплекта.",
    "number": "Порядковый номер внутри проекта или строки.",
    "year": "Год выпуска проекта или документа.",
    "contractor": "Подрядная организация.",
    "engineer": "Ответственный инженер.",
    "cpe": "Главный инженер проекта или ответственное лицо СРЕ/ГИП.",
    "checker": "Проверяющий документацию.",
    "facility": "Название объекта.",
    "facility_genitive": "Название объекта в родительном падеже.",
    "facility_instrumental": "Название объекта в творительном падеже.",
    "facility_address": "Адрес объекта.",
    "project_description": "Краткое описание проекта.",
    "stage": "Стадия проектирования.",
    "number_of_floors": "Количество этажей в проекте.",
    "created_at": "Дата и время создания записи.",
    "updated_at": "Дата и время последнего изменения записи.",
    "category": "Категория оборудования в каталоге.",
    "description": "Развёрнутое описание сущности.",
    "price": "Ориентировочная стоимость единицы оборудования.",
    "manufacturer": "Производитель оборудования.",
    "service_life_years": "Нормативный срок службы в годах.",
    "notes": "Произвольные примечания пользователя.",
    "specs": "Нормализованные технические характеристики оборудования.",
    "coverage_summary": "Краткая сводка по покрытию или характеристикам применения.",
    "compatible_equipment_ids": "Идентификаторы совместимых позиций оборудования.",
    "selections": "Привязка ролей проекта к конкретным позициям оборудования.",
    "items": "Коллекция элементов в ответе.",
    "table_caption": "Подпись над таблицей.",
    "table_title": "Название таблицы.",
    "final_text": "Итоговый абзац, который будет выведен в PDF.",
    "computed_values": "Автоматически рассчитанные числовые значения.",
    "gip_name": "Фамилия и инициалы ГИП для листа общих данных.",
    "statement_text": "Текст заявления или пояснения под таблицей.",
    "is_empty": "Признак того, что документ пока не заполнен пользователем.",
    "wall_id": "Идентификатор стены, к которой привязан проём или размер.",
    "room_id": "Идентификатор помещения, к которому относится элемент.",
    "x": "Координата X в пикселях на плане.",
    "y": "Координата Y в пикселях на плане.",
    "x1": "Координата X первой точки.",
    "y1": "Координата Y первой точки.",
    "x2": "Координата X второй точки.",
    "y2": "Координата Y второй точки.",
    "width": "Ширина элемента в пикселях.",
    "height": "Высота элемента в пикселях.",
    "scale_factor": "Масштаб плана в миллиметрах на пиксель.",
    "ceiling_height_mm": "Высота помещений на плане в миллиметрах.",
    "thickness": "Толщина в миллиметрах.",
    "rotation_deg": "Угол поворота в градусах.",
    "system_type": "Тип сигнальной системы.",
    "subsystem_type": "Подсистема кабельной линии.",
    "equipment_id": "Идентификатор связанной карточки оборудования.",
    "device_type": "Тип устройства на плане.",
    "device_model": "Модель устройства.",
    "zone": "Текстовый номер зоны или шлейфа.",
    "loop_number": "Номер шлейфа или линии.",
    "device_number": "Порядковый номер устройства в шлейфе.",
    "pipeline_state": "Полное состояние пошагового пайплайна для плана.",
    "detail": "Текстовое пояснение ошибки или ответа.",
    "recognition_id": "Идентификатор запуска распознавания.",
    "issue_tags": "Список тегов проблем, выбранных пользователем.",
    "step_revision": "Ревизия шага пайплайна, к которой относится обратная связь.",
}
SCHEMA_DESCRIPTIONS = {
    "ProjectCreate": "Данные для создания нового проекта.",
    "ProjectUpdate": "Частичное обновление карточки проекта.",
    "ProjectRead": "Карточка проекта, возвращаемая API.",
    "FloorPlanCreate": "Данные для создания плана этажа.",
    "FloorPlanUpdate": "Частичное обновление параметров плана этажа.",
    "FloorPlanRead": "Полное представление плана этажа.",
    "EquipmentItemCreate": "Данные для создания позиции в каталоге оборудования.",
    "EquipmentItemUpdate": "Частичное обновление карточки оборудования.",
    "EquipmentItemRead": "Карточка оборудования, возвращаемая API.",
    "EquipmentSpecificationRead": "Сохранённая или автоматически построенная спецификация оборудования проекта.",
    "EquipmentSpecificationUpdate": "Редактируемое представление спецификации оборудования проекта.",
    "PowerConsumptionCalculationRead": "Расчёт токопотребления системы с автопересчётом итогов.",
    "PowerConsumptionCalculationUpdate": "Редактируемые поля расчёта токопотребления проекта.",
    "GeneralInstructionsRead": "Раздел «Общие указания», подготовленный к рендеру в PDF.",
    "GeneralInstructionsUpdate": "Редактируемое содержимое раздела «Общие указания».",
    "GeneralDataRead": "Раздел «Общие данные» с таблицами и текстами для PDF.",
    "GeneralDataUpdate": "Редактируемое содержимое раздела «Общие данные».",
    "AdditionalInfoRead": "Дополнительные сведения проекта, которые могут быть добавлены в конец PDF.",
    "AdditionalInfoUpdate": "Пользовательский текст дополнительных сведений.",
    "RecognitionTrainingRunCreateRequest": "Параметры запуска новой тренировки модели распознавания.",
}
RESPONSE_DESCRIPTIONS = {
    "200": "Операция выполнена успешно.",
    "201": "Сущность успешно создана.",
    "204": "Операция выполнена успешно, тело ответа отсутствует.",
    "400": "Запрос отклонён из-за ошибки в пользовательских данных.",
    "404": "Запрошенная сущность не найдена.",
    "409": "Операция не может быть выполнена из-за конфликта состояния.",
    "422": "Валидация не пройдена или данные противоречат бизнес-правилам.",
    "500": "Внутренняя ошибка сервера.",
}
OBJECT_LABEL_MAP = {
    "project": "проект",
    "projects": "проекты",
    "project equipment": "оборудование проекта",
    "project equipment selections": "привязки оборудования проекта",
    "equipment": "оборудование",
    "equipment specification": "спецификацию оборудования",
    "general data": "общие данные",
    "general instructions": "общие указания",
    "additional info": "дополнительные сведения",
    "power consumption calculation": "расчёт токопотребления",
    "floor plan": "план этажа",
    "floor plans": "планы этажей",
    "wall": "стену",
    "walls": "стены",
    "door": "дверь",
    "doors": "двери",
    "window": "окно",
    "windows": "окна",
    "room": "помещение",
    "rooms": "помещения",
    "dimension": "размер",
    "dimensions": "размеры",
    "fire alarm": "пожарный извещатель",
    "fire alarms": "пожарные извещатели",
    "soue device": "устройство СОУЭ",
    "soue devices": "устройства СОУЭ",
    "signal instrument": "прибор",
    "signal instruments": "приборы",
    "cable route": "кабельный маршрут",
    "cable routes": "кабельные маршруты",
    "walls feedback": "обратную связь по стенам",
    "openings feedback": "обратную связь по проёмам",
    "step feedback": "обратную связь по этапу",
    "recognition feedback stats": "статистику обратной связи",
    "recognition training overview": "сводку по обучению распознавания",
    "recognition training example": "пример обучения",
    "recognition training examples": "примеры обучения",
    "recognition training run": "запуск обучения",
    "recognition training runs": "запуски обучения",
    "recognition training active models": "активные модели обучения",
    "recognition training run log": "лог запуска обучения",
    "zkspc": "ЗКСПС",
    "zkspc zones": "зоны ЗКСПС",
}
OBJECT_TOKEN_MAP = {
    "project": "проекта",
    "projects": "проекты",
    "floor": "плана",
    "plan": "этажа",
    "save": "сохранение",
    "equipment": "оборудования",
    "general": "общих",
    "data": "данных",
    "instructions": "указаний",
    "additional": "дополнительных",
    "info": "сведений",
    "power": "токопотребления",
    "consumption": "системы",
    "calculation": "расчёта",
    "fire": "пожарных",
    "alarms": "извещателей",
    "alarm": "извещателя",
    "soue": "СОУЭ",
    "devices": "устройств",
    "device": "устройства",
    "signal": "сигнальных",
    "instrument": "приборов",
    "instruments": "приборов",
    "cable": "кабельных",
    "routes": "маршрутов",
    "route": "маршрута",
    "feedback": "обратной связи",
    "overview": "обзора",
    "training": "обучения",
    "run": "запуска",
    "runs": "запусков",
    "log": "лога",
    "active": "активных",
    "models": "моделей",
    "batch": "пакета",
    "merge": "объединения",
    "walls": "стен",
    "openings": "проёмов",
    "rooms": "помещений",
    "windows": "окон",
    "doors": "дверей",
    "zkspc": "ЗКСПС",
    "zones": "зон",
}


def _humanize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip()


def _translate_object_label(value: str) -> str:
    label = _humanize_name(value).lower()
    if label in OBJECT_LABEL_MAP:
        return OBJECT_LABEL_MAP[label]
    return " ".join(OBJECT_TOKEN_MAP.get(token, token) for token in label.split())


def _build_summary(route_name: str, method: str) -> str:
    custom = {
        "root": "Проверить доступность корневого эндпоинта API",
        "health_live": "Проверить, что сервис отвечает на запросы",
        "health_ready": "Проверить готовность сервиса к работе",
    }
    if route_name in custom:
        return custom[route_name]

    parts = route_name.split("_")
    if not parts:
        return f"{method.upper()} операция API"

    verb = parts[0]
    object_label = _translate_object_label("_".join(parts[1:])) or "данные"
    verb_map = {
        "create": "Создать",
        "list": "Получить список",
        "get": "Получить",
        "update": "Обновить",
        "delete": "Удалить",
        "generate": "Сгенерировать",
        "detect": "Запустить поиск",
        "commit": "Подтвердить",
        "submit": "Отправить",
        "activate": "Активировать",
        "process": "Запустить обработку",
        "save": "Сохранить",
        "upload": "Загрузить",
        "attach": "Привязать",
        "remove": "Убрать",
        "bulk": "Массово обновить",
        "batch": "Пакетно сохранить",
        "auto": "Автоматически построить",
        "merge": "Объединить",
        "recalculate": "Пересчитать",
        "calculate": "Рассчитать",
    }
    summary_verb = verb_map.get(verb, method.upper())
    return f"{summary_verb} {object_label}".strip()


def _build_description(summary: str, operation: dict[str, object]) -> str:
    tag = (operation.get("tags") or ["system"])[0]
    tag_description = next((item["description"] for item in OPENAPI_TAGS if item["name"] == tag), "")
    parameters = [param.get("name") for param in operation.get("parameters", []) if isinstance(param, dict)]
    parameter_note = ""
    if parameters:
        readable_params = ", ".join(f"`{name}`" for name in parameters)
        parameter_note = f" Для выполнения операции используются параметры: {readable_params}."
    request_note = " Тело запроса обязательно и описано в схеме ниже." if operation.get("requestBody") else ""
    return (
        f"{summary}. {tag_description}{parameter_note}{request_note} "
        "Ответ соответствует схеме, указанной в секции `Responses`."
    ).strip()


def _augment_openapi(app: FastAPI) -> dict[str, object]:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=API_TITLE,
        version="1.0.0",
        summary=API_SUMMARY,
        description=API_DESCRIPTION,
        routes=app.routes,
        tags=OPENAPI_TAGS,
        contact={"name": "Команда проекта", "email": "support@example.local"},
    )
    route_names: dict[tuple[str, str], str] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods or []:
                route_names[(route.path_format, method.lower())] = route.name

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            route_name = route_names.get((path, method), "")
            if not operation.get("summary") or not CYRILLIC_RE.search(str(operation.get("summary", ""))):
                operation["summary"] = _build_summary(route_name or f"{method}_{path}", method)
            if not operation.get("description") or not CYRILLIC_RE.search(str(operation.get("description", ""))):
                operation["description"] = _build_description(str(operation["summary"]), operation)
            for parameter in operation.get("parameters", []):
                if not isinstance(parameter, dict) or parameter.get("description"):
                    continue
                description = PARAMETER_DESCRIPTIONS.get(str(parameter.get("name")))
                if description is None and str(parameter.get("name")).endswith("_id"):
                    description = f"Уникальный идентификатор сущности `{parameter.get('name')}`."
                if description:
                    parameter["description"] = description
            if operation.get("requestBody") and not operation["requestBody"].get("description"):
                operation["requestBody"]["description"] = (
                    f"Тело запроса для операции «{str(operation['summary']).lower()}»."
                )
            for status_code, response in operation.get("responses", {}).items():
                if (
                    isinstance(response, dict)
                    and (
                        not response.get("description")
                        or not CYRILLIC_RE.search(str(response.get("description", "")))
                    )
                ):
                    response["description"] = RESPONSE_DESCRIPTIONS.get(status_code, "Ответ операции API.")

    for schema_name, schema_body in schema.get("components", {}).get("schemas", {}).items():
        if not schema_body.get("description") or not CYRILLIC_RE.search(str(schema_body.get("description", ""))):
            schema_body["description"] = SCHEMA_DESCRIPTIONS.get(
                schema_name,
                f"Схема API `{schema_name}`.",
            )
        for field_name, field_schema in schema_body.get("properties", {}).items():
            if (
                isinstance(field_schema, dict)
                and (
                    not field_schema.get("description")
                    or not CYRILLIC_RE.search(str(field_schema.get("description", "")))
                )
            ):
                description = FIELD_DESCRIPTIONS.get(field_name)
                if description:
                    field_schema["description"] = description

    app.openapi_schema = schema
    return schema


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_runtime_directories()
    try:
        register_pdf_fonts()
    except FileNotFoundError:
        logger.warning("PDF fonts are unavailable; PDF generation may fail", exc_info=True)
    if settings.run_inline_worker:
        worker_controller.start()
    yield
    if settings.run_inline_worker:
        worker_controller.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title=API_TITLE,
        summary=API_SUMMARY,
        description=API_DESCRIPTION,
        version="1.0.0",
        contact={"name": "Команда проекта", "email": "support@example.local"},
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    health_service = HealthService(engine=engine, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware, logger=logger)

    install_exception_handlers(app)
    app.include_router(assets_router)
    app.include_router(auth_router)
    app.include_router(background_tasks_router)
    app.include_router(projects_router)
    app.include_router(equipment_router)
    app.include_router(floor_plans_router)
    app.include_router(elements_router)
    app.include_router(pipeline_router)
    app.include_router(recognition_router)
    app.include_router(recognition_training_router)
    app.include_router(users_router)
    app.include_router(pdf_router)

    app.openapi = lambda: _augment_openapi(app)

    @app.get(
        "/",
        response_model=HealthRead,
        tags=["system"],
        summary="Проверить доступность корневого эндпоинта API",
        description="Быстрая проверка того, что приложение запущено и отвечает на HTTP-запросы.",
        response_description="Служебный ответ о доступности API.",
    )
    def root() -> HealthRead:
        return health_service.live()

    @app.get(
        "/health/live",
        response_model=HealthRead,
        tags=["system"],
        summary="Проверить живость сервиса",
        description="Используется внешними системами мониторинга, чтобы понять, отвечает ли процесс приложения.",
        response_description="Служебный ответ о доступности процесса.",
    )
    def health_live() -> HealthRead:
        return health_service.live()

    @app.get(
        "/health/ready",
        tags=["system"],
        summary="Проверить готовность сервиса",
        description="Проверяет готовность приложения к выполнению рабочих запросов, включая доступность базы данных.",
        response_description="Сводка о готовности приложения и его зависимостей.",
    )
    def health_ready() -> dict[str, object]:
        return health_service.ready()

    return app


app = create_app()
