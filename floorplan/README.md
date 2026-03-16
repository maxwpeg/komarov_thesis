# Floor Plan Analyzer

Модуль для автоматического распознавания дверей, окон и стен на 2D планах зданий на основе классического компьютерного зрения.

**Без использования нейросетей** — только OpenCV и базовая геометрия.

## Особенности

- ✅ Детекция стен как пар параллельных линий
- ✅ Поиск проёмов (разрывов) в стенах
- ✅ Классификация проёмов как двери или окна на основе внутренних маркеров
  - **Двери**: одна перпендикулярная стене "засечка" в центре gap
  - **Окна**: 2-3 линии параллельные стене
- ✅ Экспорт в JSON с координатами и доверительностью
- ✅ Опциональная визуализация с отладочными изображениями
- ✅ Обработка перспективы, наклона, бинаризация
- ✅ CLI интерфейс
- ✅ Unit-тесты

## Установка

### Требования
- Python 3.10+
- pip

### Шаги установки

```bash
# 1. Перейти в директорию проекта
cd path/to/floorplan

# 2. Установить зависимости
pip install -r floorplan/requirements.txt

# 3. (Опционально) Установить в режиме разработки
pip install -e .
```

## Использование

### Базовый пример (CLI)

```bash
python -m floorplan.main --input floor.jpg --out result.json
```

### С отладочными изображениями

```bash
python -m floorplan.main \
  --input floor.jpg \
  --out result.json \
  --debug debug_output \
  --overlay floor_result.png \
  --verbose
```

### Параметры CLI

```
--input, -i FILE       Путь к входному изображению (jpg/png) [обязательный]
--out, -o FILE         Путь к выходному JSON файлу [обязательный]
--debug, -d DIR        Сохранить промежуточные изображения в директорию
--overlay FILE         Сохранить визуализацию с результатами
--verbose, -v          Подробный вывод
```

### Программный интерфейс (API)

```python
from floorplan import FloorPlanProcessor

# Создать процессор
processor = FloorPlanProcessor(debug=False)

# Обработать изображение
result = processor.process("floor.jpg", debug_dir="debug_output")

# Получить результаты
print(f"Стен обнаружено: {len(result.walls)}")
print(f"Проёмов обнаружено: {len(result.openings)}")

# Проверить каждый проём
for opening in result.openings:
    print(f"  {opening.type.value}: стена #{opening.wall_id}, уверенность {opening.confidence:.2f}")

# Сохранить в JSON
result.save_json("result.json")

# Получить словарь
data = result.to_dict()
```

## Формат выходного JSON

```json
{
  "image": {
    "width": 1024,
    "height": 768
  },
  "walls": [
    {
      "id": 0,
      "midline": [100, 200, 500, 200],
      "thickness_px": 20,
      "angle_deg": 0,
      "confidence": 0.95
    }
  ],
  "openings": [
    {
      "type": "door",
      "wall_id": 0,
      "bbox": [200, 180, 280, 220],
      "confidence": 0.85,
      "center": [240, 200],
      "marker": [[240, 185], [240, 215]],
      "metadata": {"markers_found": 1, "marker": [240, 185, 240, 215]}
    },
    {
      "type": "window",
      "wall_id": 0,
      "bbox": [320, 180, 400, 220],
      "confidence": 0.78,
      "center": [360, 200],
      "lines": [[[330, 200], [390, 200]], [[340, 200], [380, 200]]],
      "metadata": {"lines_found": 2, "lines": [...]}
    }
  ]
}
```

## Структура проекта

```
floorplan/
├── __init__.py           # Главный модуль
├── types.py              # Dataclass структуры данных
├── preprocess.py         # Обработка изображений
├── walls.py              # Детекция стен
├── openings.py           # Поиск дверей и окон
├── visualize.py          # Визуализация результатов
├── main.py               # CLI и главный pipeline
├── requirements.txt      # Зависимости
└── tests/
    ├── __init__.py
    └── test_floorplan.py # Unit-тесты
```

## Алгоритм

### 1. Предобработка (preprocess.py)

- **Rectify**: Найти границы листа, исправить перспективу
- **Deskew**: Выровнять наклон по доминирующим линиям (Hough)
- **Binarize**: Адаптивный threshold для преодоления неравномерного освещения

### 2. Детекция стен (walls.py)

- `detect_wall_segments()`: Найти линии (HoughLinesP), объединить коллинеарные
- `pair_parallel_lines()`: Найти пары параллельных линий, создать Wall объекты
- Wall представляется центральной осью (midline) + толщина (thickness_px)

### 3. Поиск проёмов (openings.py)

- `find_gaps_along_wall()`: Профилировать интенсивность вдоль оси стены, найти gap (пропуски)
- `classify_opening()`: Анализировать линейные сегменты внутри ROI gap
  - Дверь: 1 перпендикулярный сегмент (засечка)
  - Окно: 2-3 параллельных сегмента
- `remove_duplicate_openings()`: NMS по IoU

### 4. Экспорт

Результат сохраняется в JSON с полной информацией о координатах, типах и уверенностью.

## Параметры конфигурации

Все пороги находятся в классах `Config` каждого модуля:

- `preprocess.Config`: Canny, морфология, адаптивный threshold
- `WallConfig`: Hough параметры, кластеризация углов, толщина стен
- `OpeningConfig`: Размеры gap, размеры маркеров дверей/окон

Чтобы настроить для вашего набора данных, отредактируйте эти константы.

## Запуск тестов

```bash
# Установить pytest
pip install pytest

# Запустить все тесты
pytest floorplan/tests/ -v

# Запустить конкретный тест
pytest floorplan/tests/test_floorplan.py::TestLineSegmentGeometry -v
```

## Примеры

### Пример 1: Базовая обработка

```bash
python -m floorplan.main \
  --input examples/floor.jpg \
  --out results/floor_result.json
```

### Пример 2: С визуализацией и отладкой

```bash
python -m floorplan.main \
  --input examples/floor.jpg \
  --out results/floor_result.json \
  --overlay results/floor_visualization.png \
  --debug results/debug \
  --verbose
```

### Пример 3: Обработка нескольких файлов

```python
from floorplan import FloorPlanProcessor
from pathlib import Path

processor = FloorPlanProcessor()

for image_path in Path("input_images").glob("*.jpg"):
    try:
        result = processor.process(str(image_path))
        result.save_json(f"output/{image_path.stem}.json")
        print(f"✓ {image_path.name}")
    except Exception as e:
        print(f"✗ {image_path.name}: {e}")
```

## Отладочные изображения

При указании `--debug`, сохраняются:

- `01_preprocessed.png` — после выпрямления и выравнивания
- `02_binary.png` — бинаризованное изображение (черные стены на белом фоне)
- `03_walls.png` — обнаруженные стены со своими ID
- `04_gaps.png` — обнаруженные проёмы с типами
- `05_overlay.png` — финальная визуализация поверх исходного изображения

## Ограничения и известные проблемы

1. **Перспектива**: Хорошо работает при умеренной перспективе (фото под углом ~30-45°)
2. **Качество изображения**: Требуется достаточно четкого контраста между стенами и пустым пространством
3. **Рукописные пометки**: Может интерпретировать как часть стены, используйте `--debug` для проверки
4. **Кривые стены**: детектор ориентирован на прямые линии, кривые стены не поддерживаются
5. **Очень тонкие/толстые стены**: Параметры WallConfig.DISTANCE_TOLERANCE могут потребовать коррекции

## Производительность

На типичном плане (1200x900 px):
- Preprocessing: ~100 ms
- Wall detection: ~50 ms
- Gap detection: ~100 ms
- Classification: ~50 ms
- **Итого**: ~300 ms на современном CPU

## Контакты и лицензия

Модуль разработан как часть системы анализа планов зданий.
Используется классическое CV (OpenCV) без машинного обучения.

## Требования к входным изображениям

- **Формат**: JPG, PNG
- **Разрешение**: 800x600 - 2400x1800 px (оптимально ~1500px по длинной стороне)
- **Качество**: Четкие линии стен, хороший контраст
- **Источник**: Фото на смартфон, сканы PDF, цифровые чертежи
- **Ориентация**: Любая (расчет проводится автоматически)

## Поддерживаемые нотации на планах

✅ **Стены**: Две параллельные линии толщиной 5-150 px  
✅ **Двери**: Разрыв в стене + перпендикулярная засечка в центре  
✅ **Окна**: Разрыв в стене + 2-3 линии параллельные стене  

❌ Скругленные углы (rooms)  
❌ Дуги/полукруги в дверях  
❌ Цветные помечания уникальных пространств
