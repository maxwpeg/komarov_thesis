# Бэкенд проекта

## 1. Назначение

Данный репозиторий содержит серверную часть приложения для проектирования систем пожарной сигнализации и СОУЭ. Бэкенд отвечает за хранение проектов, обработку планов этажей, подбор оборудования, генерацию PDF-документации, обучение распознавания и фоновые задачи.

## 2. Состав репозитория

В бэкенд-репозитории должны оставаться следующие части проекта:

- `backend/` - основное FastAPI-приложение, роутеры, сервисы, схемы и модули предметной области.
- `alembic/` и `alembic.ini` - миграции базы данных.
- `floorplan/` - модуль распознавания и обработки планов.
- `tools/` - служебные скрипты для воркера, обучения и экспорта данных.
- `tests/` - тесты серверной части.
- корневые файлы `Project.py`, `DrawingPage.py`, `Page.py`, `TitlePage.py`, `SpecificationPage.py`, `GeneralDataPage.py`, `GeneralInstructionsPage.py`, `ConventionalSymbolsPage.py`, `PowerConsumptionCalculationPage.py`, `AdditionalInfoPage.py`, `ConnectionDiagramPage.py`, `StructuralSchemePage.py`, `consts.py` - слой генерации PDF.
- `GOST_A.TTF`, `GOST_A_Bold.ttf` - шрифты для PDF.
- `backend/requirements.txt`, `pyproject.toml`, `pytest.ini`, `.env.example`, `.gitignore` - конфигурация запуска и разработки.

Папка `floorplan-ui/` относится к фронтенду и при разделении переносится в отдельный репозиторий.

## 3. Требования

- Python 3.12.
- SQLite для локального запуска или другая база через `DATABASE_URL`.
- Tesseract OCR, если используется OCR-распознавание.
- Установленные зависимости из `backend/requirements.txt`.

## 4. Переменные окружения

Основные переменные задаются в файле `.env`.

| Переменная | Назначение |
| --- | --- |
| `DATABASE_URL` | строка подключения к базе данных. Если не задана, используется `floor_plans.db` |
| `CORS_ALLOWED_ORIGINS` | адреса фронтенда через запятую |
| `ASSET_PUBLIC_BASE_URL` | публичный адрес бэкенда для ссылок на PDF и изображения |
| `BOOTSTRAP_DEVELOPER_USERNAME` | логин первого администратора |
| `BOOTSTRAP_DEVELOPER_PASSWORD` | пароль первого администратора |
| `RUN_INLINE_WORKER` | запуск фонового воркера внутри API-процесса: `1` или `0` |

## 5. Локальный запуск

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
copy .env.example .env
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Если фоновые задачи запускаются отдельным процессом:

```powershell
python tools\run_background_worker.py
```

## 6. Проверка

```powershell
python -m pytest
```

Для быстрой проверки основных доработанных разделов:

```powershell
python -m pytest tests\test_pdf_smoke.py tests\test_general_data_page.py tests\test_structural_scheme.py tests\test_api.py tests\test_auth_api.py
```

## 7. Инструкция по разделению на два репозитория

1. Создать два пустых репозитория:
   - `fire-alarm-backend`;
   - `fire-alarm-frontend`.
2. В репозиторий `fire-alarm-backend` перенести текущее содержимое корня проекта, кроме папки `floorplan-ui/`.
3. Не переносить в backend-репозиторий сгенерированные данные:
   - `.venv/`;
   - `.pytest_cache/`;
   - `.tmp_playwright/`;
   - `.tmp_pypdf/`;
   - `.playwright-browsers/`;
   - `uploads/`;
   - `outputs/`;
   - `debug_output/`;
   - `storage_objects/`;
   - `floor_plans.db`;
   - `__pycache__/`;
   - файлы логов.
4. В репозиторий `fire-alarm-frontend` перенести содержимое папки `floorplan-ui/` так, чтобы `package.json` находился в корне frontend-репозитория.
5. В backend-репозитории настроить `.env`:

```env
CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
ASSET_PUBLIC_BASE_URL=http://127.0.0.1:8000
```

6. Во frontend-репозитории создать `.env`, если фронтенд и бэкенд находятся на разных адресах:

```env
REACT_APP_API_BASE_URL=http://127.0.0.1:8000
```

7. Запустить backend на порту `8000`.
8. Запустить frontend на порту `3000`.
9. Проверить авторизацию, список проектов, загрузку плана этажа, генерацию PDF и открытие PDF в новой вкладке.

## 8. Важные замечания

- Корневые PDF-файлы нельзя переносить только в папку `backend/` без изменения импортов. Сейчас они являются частью backend-репозитория.
- Фронтенд использует cookie-авторизацию, поэтому при разных доменах нужно правильно настроить CORS и параметры cookie.
- Загруженные файлы и PDF являются рабочими данными, а не исходным кодом. Их не следует хранить в Git.
