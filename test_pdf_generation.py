"""
Тестовый скрипт для проверки генерации PDF с новой структурой страниц.
"""
from Project import Project
from consts import DEFAULT_CREDS_DICT
import datetime

# Подготовка тестовых данных
test_creds = DEFAULT_CREDS_DICT.copy()
test_creds["Facility"] = "Тестовый объект"
test_creds["Contractor"] = "ООО \"Флагман-СБ\""

# Имитация данных планов этажей с элементами (стены, двери, окна)
test_floor_plans = [
    {
        "id": 1,
        "name": "План 1 этажа",
        "floor_number": 1,
        "original_image_path": "uploads/floor_plan_1.png",
        "image_width": 800,
        "image_height": 600,
        "walls": [
            {"id": 1, "x1": 100, "y1": 100, "x2": 700, "y2": 100, "thickness": 200},
            {"id": 2, "x1": 700, "y1": 100, "x2": 700, "y2": 500, "thickness": 200},
            {"id": 3, "x1": 700, "y1": 500, "x2": 100, "y2": 500, "thickness": 200},
            {"id": 4, "x1": 100, "y1": 500, "x2": 100, "y2": 100, "thickness": 200},
        ],
        "doors": [
            {"id": 1, "x": 350, "y": 100, "width": 80, "height": 10, "rotation": 0},
        ],
        "windows": [
            {"id": 1, "x": 700, "y": 250, "width": 60, "height": 5, "rotation": 90},
        ],
        "fire_alarms": [
            {"id": 1, "x": 400, "y": 300, "device_type": "ИП212"},
        ]
    }
]

# Создаем проект
project = Project(
    project_type="ПС",
    number=100,
    year=datetime.datetime.now().year,
    creds=test_creds,
    number_of_floors=len(test_floor_plans),
    floor_plans_data=test_floor_plans
)

# Генерируем PDF
print("Генерация PDF с отрисовкой элементов...")
project.launch()
project.save()

print(f"PDF успешно создан: {project._c._filename}")
print(f"Всего страниц: {project.number_of_pages}")
print(f"Каждый план этажа отрисован трижды (ЗКСПС, СПС, СОУЭ) с элементами!")

