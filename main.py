from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json
import io
import json
from PIL import Image
from ultralytics import YOLO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Загружаем обученную модель
model = YOLO("yolov8n-seg.pt")

class Annotation(BaseModel):
    objects: list

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    contents = await file.read()
    img = Image.open(io.BytesIO(contents)).convert("RGB")

    results = model.predict(img, imgsz=640)
    objects = []

    for result in results:
        boxes = result.boxes
        for i, box in enumerate(boxes):
            xyxy = box.xyxy[0].tolist()
            cls = int(box.cls)
            label = model.names[cls]
            objects.append({
                "id": i,
                "type": label,
                "x": xyxy[0],
                "y": xyxy[1],
                "width": xyxy[2] - xyxy[0],
                "height": xyxy[3] - xyxy[1],
            })
    print(objects)
    return {"objects": objects}

@app.post("/feedback")
async def feedback(annotation: Annotation):
    with open("user_feedback.json", "w") as f:
        json.dump(annotation.dict(), f, indent=2)
    return {"status": "saved"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

