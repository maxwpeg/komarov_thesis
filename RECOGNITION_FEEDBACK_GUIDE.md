# Recognition Feedback Loop

## Workflow

1. Пользователь запускает распознавание архитектуры.
2. Пользователь исправляет стены, двери, окна, помещения и размеры.
3. После подтверждения шагов `walls`, `openings` и `rooms` в редакторе доступна кнопка отправки исправленного результата.
4. Backend сохраняет один актуальный `RecognitionFeedbackSample` на один `recognition_id`.
5. Оператор периодически экспортирует невыгруженные примеры в batch-датасет.
6. Экспортированный batch используется во внешнем контуре обучения и валидации.

## Что попадает в sample

- исходное изображение плана;
- исходный `recognition_result` последнего запуска;
- исправленный снапшот текущего сохраненного состояния `walls`, `doors`, `windows`, `rooms`, `dimensions`;
- служебные поля `status`, `submitted_at`, `exported_at`, `export_batch_id`.

## Export

Команда:

```bash
python tools/export_recognition_feedback.py
```

Опции:

- `--batch-id <value>`: задать свой идентификатор пачки;
- `--output-root <path>`: переопределить корневую директорию экспорта.

Результат:

- `outputs/recognition_feedback/<batch_id>/images/`
- `outputs/recognition_feedback/<batch_id>/annotations/`
- `outputs/recognition_feedback/<batch_id>/manifest.jsonl`

## Retraining Loop

1. Копим `approved` samples.
2. Экспортируем новую batch-пачку.
3. Обучаем внешнюю модель на экспортированном наборе.
4. Сравниваем новую модель с baseline на holdout-наборе.
5. После ручной проверки качества продвигаем новую модель в прод.
