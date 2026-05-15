import requests
import json
import os

# Create test project
project_data = {
    "name": "Test Project",
    "project_type": "ПС",
    "contractor": "Test Contractor",
    "engineer": "Test Engineer",
    "cpe": "Test CPE",
    "checker": "Test Checker",
    "facility": "Test Facility",
    "facility_address": "Test Address",
    "project_description": "Test Description",
    "stage": "«Р»",
    "number_of_floors": 1
}

# Create project
response = requests.post("http://localhost:8000/api/projects", json=project_data)
if response.status_code == 200:
    project = response.json()
    project_id = project["id"]
    print(f"Created project with ID: {project_id}")

    # Create floor plan with image upload
    test_image_path = "uploads/floor_plan_1_1_1768302866.045689.jpeg"
    if os.path.exists(test_image_path):
        with open(test_image_path, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            data = {
                "project_id": project_id,
                "floor_number": 1,
                "name": "Test Floor Plan"
            }
            response = requests.post("http://localhost:8000/api/floor-plans", data=data, files=files)
    else:
        # Create without image
        floor_plan_data = {
            "project_id": project_id,
            "floor_number": 1,
            "name": "Test Floor Plan"
        }
        response = requests.post("http://localhost:8000/api/floor-plans", data=floor_plan_data)
else:
    print(f"Project creation failed: {response.status_code} - {response.text}")