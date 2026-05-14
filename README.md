# Komarov Thesis App

Проект разделен на две запускаемые папки:

- `backend/` - FastAPI API, миграции, распознавание планов, PDF-генерация, аудит, фоновые задачи, тесты и backend-инструменты.
- `frontend/` - React-приложение с `package.json` прямо в корне папки.

Рабочие данные не входят в исходный код: `floor_plans.db`, `uploads/`, `outputs/`, `debug_output/`, `storage_objects/`, `.env`, кэши и временные файлы остаются локальными. После переноса старую базу и файлы можно использовать через `DATA_DIR=..` в `backend/.env`.

## Запуск

Backend:

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Фоновый worker:

```powershell
cd backend
python tools/run_background_worker.py
```

Frontend:

```powershell
cd frontend
npm install
npm start
```

## Docker

Перед первым запуском Docker seed уже можно подготовить из текущих локальных данных:

```powershell
python backend/tools/export_docker_seed.py
```

После этого вся система поднимается одной командой из корня репозитория:

```powershell
docker compose up -d
```

Сервисы в составе compose:

- `frontend` - Nginx со статической сборкой React, доступен на `http://localhost:3000`.
- `backend` - FastAPI/Uvicorn, доступен на `http://localhost:8000`.
- `postgres` - PostgreSQL с named volume `postgres_data`.
- `db-seed` - одноразовый импорт seed-базы SQLite в PostgreSQL при первом запуске.
- `storage-init` - одноразовое копирование seed-файлов в named volume `app_data`.

`docker compose down` останавливает контейнеры и сохраняет данные в volumes. `docker compose down -v` удаляет volumes; при следующем `docker compose up -d` база и файловое хранилище снова инициализируются из seed-снимка. Последующие проекты, пользователи, оборудование и PDF, созданные на конкретном устройстве, остаются индивидуальными для его Docker volumes.

Если нужно изменить стандартный набор данных для новых установок, обновите локальные данные обычным запуском приложения и повторно выполните:

```powershell
python backend/tools/export_docker_seed.py
```

## Технологические решения

- PDF формируется через `reportlab`; этот слой оставлен без замены.
- Пароли хэшируются через PBKDF2, без перехода на другую схему в этой итерации.
- По умолчанию используется SQLite. Для PostgreSQL-совместимого запуска можно задать `DATABASE_URL`.
- Роль `developer` является текущим эквивалентом администратора: управление пользователями, аудит, дообучение, корзина проектов и служебные операции доступны ей.

## Возможности

- Проекты, планы этажей, элементы, оборудование и поэтапный pipeline распознавания.
- Административный аудит: `/api/audit`, фильтры и экспорт CSV/JSON.
- Фоновые задачи с прогрессом, стадиями и повторным запуском failed-задач.
- PDF-документы проекта сохраняются как версии с датой, автором, параметрами и ссылкой скачивания.
- Списки проектов поддерживают фильтры по автору, статусу, объекту, номеру и датам.

## Ограничения

- Загрузка планов этажей в текущей версии рассчитана на изображения, минимальный размер - `200x200` пикселей.
- PDF-файлы поддерживаются как артефакты и документы оборудования, но не как импортируемый план этажа.
- Редактор планов в этой итерации функционально не менялся.

## Проверки

Backend:

```powershell
cd backend
python -m compileall backend floorplan tools
python -m pytest -q
```

Frontend:

```powershell
cd frontend
npm.cmd test -- --watch=false --runInBand
npm.cmd run build
```
