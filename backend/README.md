# Backend

Серверная часть приложения для проектирования пожарной сигнализации и СОУЭ.
Запускается из корня папки `backend/`.

## Структура

- `backend/` - FastAPI-пакет: роутеры, сервисы, схемы, авторизация, аудит и доменные модули.
- `pdf_documents/` - слой формирования PDF-документов на `reportlab`.
- `floorplan/` - алгоритмы распознавания и обработки планов этажей.
- `assets/fonts/` - шрифты `GOST_A.TTF` и `GOST_A_Bold.ttf` для PDF.
- `assets/models/` - локальные модели распознавания `yolov8n-seg.pt` и `yolo26n.pt`.
- `alembic/` и `alembic.ini` - миграции базы данных.
- `tools/` - фоновые и служебные скрипты; `tools/manual_checks/` - ручные проверочные скрипты.
- `tests/` - backend-тесты.
- `notebooks/` - исследовательские ноутбуки.
- `uploads/`, `outputs/`, `debug_output/`, `storage_objects/`, `floor_plans.db` - рабочие данные локального запуска.

## Локальный запуск

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Фоновый worker запускается из этого же корня:

```powershell
python tools/run_background_worker.py
```

Backend читает `.env` из папки `backend/`. Для работы со старыми runtime-данными после
разделения проекта задайте `DATA_DIR=..` или перенесите `floor_plans.db`, `uploads/`,
`outputs/`, `debug_output/` и `storage_objects/` вручную.

## Конфигурация

- `DATABASE_URL` задает подключение к базе. Если переменная не задана, используется SQLite-файл в runtime-папке.
- `BOOTSTRAP_DEVELOPER_USERNAME`, `BOOTSTRAP_DEVELOPER_FULL_NAME`, `BOOTSTRAP_DEVELOPER_PASSWORD` нужны при первом запуске на пустой базе.
- `developer` - текущая административная роль.
- Пароли хэшируются PBKDF2.
- PDF формируется через `reportlab`.

## Проверки

```powershell
python -m compileall backend floorplan pdf_documents tools
python -m pytest -q
```
