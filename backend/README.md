# Backend

Серверная часть приложения для проектирования пожарной сигнализации и СОУЭ. Запускается из корня папки `backend/`.

## Структура

- `backend/` - FastAPI-пакет: роутеры, сервисы, схемы, авторизация, аудит и доменные модули.
- `alembic/` и `alembic.ini` - миграции базы данных.
- `floorplan/` - распознавание и обработка планов этажей.
- `tools/` - фоновые и служебные скрипты.
- `tests/` - backend-тесты.
- `*.py` в корне этой папки - слой PDF-генерации, от которого зависят `backend/pdf_generator.py` и тесты.
- `GOST_A.TTF`, `GOST_A_Bold.ttf` - шрифты для PDF.
- `yolov8n-seg.pt`, `yolo26n.pt` - локальные модели распознавания.

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

Backend читает `.env` из папки `backend/`. Для работы со старыми runtime-данными после разделения проекта задайте `DATA_DIR=..` или перенесите `floor_plans.db`, `uploads/`, `outputs/`, `debug_output/` и `storage_objects/` вручную.

## Конфигурация

- `DATABASE_URL` задает подключение к базе. Если переменная не задана, используется SQLite-файл в runtime-папке.
- `BOOTSTRAP_DEVELOPER_USERNAME`, `BOOTSTRAP_DEVELOPER_FULL_NAME`, `BOOTSTRAP_DEVELOPER_PASSWORD` нужны при первом запуске на пустой базе.
- `developer` - текущая административная роль.
- Пароли хэшируются PBKDF2.
- PDF формируется через `reportlab`.

## API И Поведение

- `/api/audit` - журнал аудита для `developer`, с фильтрами по пользователю, сущности, действию и периоду.
- `/api/audit/export` - экспорт аудита в `csv` или `json`.
- `/api/background-tasks` - список фоновых задач с `progress_percent` и `progress_stage`.
- `/api/background-tasks/{task_id}/retry` - повтор failed-задачи.
- `/api/projects` - фильтры по автору, статусу, объекту, номеру и датам.
- `/api/projects/{project_id}/pdf-versions` - версии PDF-документов проекта.

## Загрузки

Планы этажей принимаются как изображения. Backend проверяет тип файла, размер файла и минимальное разрешение `200x200` пикселей. PDF-файлы не импортируются как планы этажей в текущей версии; они используются для документов и артефактов, где это поддержано отдельными endpoint-ами.

## Проверки

```powershell
python -m compileall backend floorplan tools
python -m pytest -q
```

## Frontend

Клиент находится в соседней папке `../frontend`:

```powershell
cd ..\frontend
npm install
npm start
```

Backend разрешает локальный frontend по адресам `http://127.0.0.1:3000` и `http://localhost:3000` через `CORS_ALLOWED_ORIGINS`.
